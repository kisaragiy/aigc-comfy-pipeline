"""诊断集 v1 — 管线失败模式压测（P0-1/P0-2）

设计依据（一手官方对标）：
  - GenEval (arXiv 2310.11513): single/two object, counting, colors, position, color attribution
    论文原文结论: 现代 T2I 仍弱于 "spatial relations and attribute binding"
  - T2I-CompBench++ (NeurIPS'23/TPAMI, 被 DALL-E 3 与 PixArt-α 采用): 属性绑定/2D-3D空间/数量/非空间关系/复杂组合
  - PartiPrompts (Google Parti): category × challenge aspect 矩阵
  + 本地已知弱点（D阶段实测）: 远景手崩 / 画面内文字 / 极端透视未实测

铁律：
  1. prompt 原样送模型（不过 Ollama 改写）——否则测的不是管线符合度
  2. 每题必须有可二值判定（PASS/FAIL）的 expect，不用七维美学分
  3. 固定 seed，可复现；同题多 seed 排除单次抽样运气

用法：
  python scripts/diag_suite.py --dry-run          # 只打印计划
  python scripts/diag_suite.py --only D1 --seeds 111111   # 单类单seed 试跑
  python scripts/diag_suite.py                    # 全量 30题 × 2seed = 60张
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))  # agents 内部用扁平 import（from comfy_utils import ...）

import requests  # noqa: E402

from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402
from go_knives_lora import build_sdxl_clean_workflow  # noqa: E402

# 与实际管线一致的质量前缀 / 负向词（测管线而非裸模型）
# ⚠️ 2026-08-30 实测修正：原前缀含 "clean lineart"（商业流程的去脏词），
#   在极简 prompt 下会主导画面 → 出纯线稿/设定稿（无上色），使 D3 颜色属性绑定整类失效。
#   证据: workspace/diag/_contaminated/D1-1_111111.png (线稿+孤立马尾部件), D1-2_111111.png (线稿)
#   → 符合度测试基线只用最小干扰质量词，风格控制词移入负向防御。
QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
NEG = (
    "worst quality, low quality, normal quality, blurry, jpeg artifacts, lowres, "
    "bad anatomy, bad hands, ugly, deformed, bad proportions, extra limbs, fused fingers, "
    "missing fingers, extra fingers, mutated hands, poorly drawn face, bad eyes, cross-eyed, "
    "signature, watermark, username, text, error, extra digit, fewer digits, cropped, "
    "monochrome, grayscale, "
    # 防线稿/设定稿模式（2026-08-30 实测新增）
    "lineart, sketch, unfinished, uncolored, character sheet, reference sheet, multiple views"
)
# D6 测画面内文字：负向词里的 text/watermark 会打架 → 该类去掉 text 相关负向
NEG_TEXT_OK = NEG.replace(", signature, watermark, username, text, error", ", signature, watermark, username, error")

# 分辨率：按题目需要（记录在案，便于复现）
R_WIDE = (1216, 832)    # 多人/左右空间
R_FULL = (768, 1344)    # 全身/肢体
R_SQ = (896, 896)       # 特写
R_LAND = (1344, 768)    # 远景/场景

SUITE: list[dict] = [
    # ---------- D1 数量（GenEval counting / CompBench numeracy）----------
    dict(id="D1-1", cat="D1_数量", res=R_WIDE,
         prompt="three girls standing in a row, full body, simple background",
         expect="画面恰好 3 个女孩（不多不少，无融合/半身多余人）"),
    dict(id="D1-2", cat="D1_数量", res=R_WIDE,
         prompt="two girls sitting face to face at a cafe table",
         expect="恰好 2 人，面对面而坐"),
    dict(id="D1-3", cat="D1_数量", res=R_LAND,
         prompt="five teacups on a wooden table, nobody in frame",
         expect="恰好 5 个茶杯，且无人物"),
    dict(id="D1-4", cat="D1_数量", res=R_FULL,
         prompt="a girl holding two swords, one in each hand, full body",
         expect="恰好 2 把剑，每只手一把"),
    dict(id="D1-5", cat="D1_数量", res=R_LAND,
         prompt="four cats sitting on a wooden fence",
         expect="恰好 4 只猫"),
    # ---------- D2 空间关系（GenEval position / CompBench 2D+3D spatial）----------
    dict(id="D2-1", cat="D2_空间", res=R_WIDE,
         prompt="black haired girl on the left reading a book, brown haired girl on the right standing with hands on hips",
         expect="左=黑发在读书，右=棕发站立叉腰（左右不可互换）"),
    dict(id="D2-2", cat="D2_空间", res=R_LAND,
         prompt="a girl standing in the foreground, a train passing in the background",
         expect="人在前景清晰，电车在后景（前后层次正确）"),
    dict(id="D2-3", cat="D2_空间", res=R_LAND,
         prompt="a cat under the table, a handbag on top of the table",
         expect="猫在桌下，包在桌上（上下关系不可颠倒）"),
    dict(id="D2-4", cat="D2_空间", res=R_FULL,
         prompt="a girl standing in front of a large clock tower, looking at camera",
         expect="人在钟楼前方（人不被塔遮挡/不悬浮）"),
    dict(id="D2-5", cat="D2_空间", res=R_WIDE,
         prompt="two girls, the taller girl standing behind the shorter girl",
         expect="高个在后、矮个在前（遮挡关系正确）"),
    # ---------- D3 属性绑定（GenEval color attribution ★最典型 AI 病）----------
    dict(id="D3-1", cat="D3_属性绑定", res=R_FULL,
         prompt="a girl wearing a red jacket, blue skirt and white thighhighs, full body",
         expect="外套红/裙蓝/袜白 三色各归其位，无串色"),
    dict(id="D3-2", cat="D3_属性绑定", res=R_WIDE,
         prompt="black haired girl with red framed glasses next to brown haired girl with blue framed glasses",
         expect="黑发戴红框、棕发戴蓝框（跨角色属性不可串）"),
    dict(id="D3-3", cat="D3_属性绑定", res=R_FULL,
         prompt="a girl holding a yellow umbrella and carrying a green bag",
         expect="伞黄/包绿（道具颜色不串）"),
    dict(id="D3-4", cat="D3_属性绑定", res=R_SQ,
         prompt="close-up of a girl with green eyes and a purple hair ribbon",
         expect="瞳绿/发带紫（相邻部位颜色不串）"),
    dict(id="D3-5", cat="D3_属性绑定", res=R_LAND,
         prompt="a white cat and a black dog sitting together on grass",
         expect="猫白/狗黑（不可换色/不可融合成一只）"),
    # ---------- D4 手部肢体（本地已知弱点，D阶段实测远景手崩）----------
    dict(id="D4-1", cat="D4_手部肢体", res=R_FULL,
         prompt="a girl holding a sword with both hands in front of her, full body",
         expect="双手各5指、握柄合理，无融合/多指"),
    dict(id="D4-2", cat="D4_手部肢体", res=R_SQ,
         prompt="close-up of a girl making a V sign with her right hand near her face",
         expect="V字手势成立，恰好2指伸出，其余收拢"),
    dict(id="D4-3", cat="D4_手部肢体", res=R_WIDE,
         prompt="a girl playing piano, both hands on the keys, side view",
         expect="双手在琴键上，手指数正常无粘连"),
    dict(id="D4-4", cat="D4_手部肢体", res=R_SQ,
         prompt="a girl holding a smartphone with both hands, looking at the screen",
         expect="双手持机姿态合理，手指不穿模"),
    dict(id="D4-5", cat="D4_手部肢体", res=R_FULL,
         prompt="a girl standing with arms crossed over her chest, full body",
         expect="双臂交叉结构正确（无第三只手/断臂）"),
    # ---------- D5 复杂组合（PartiPrompts complex / CompBench 3-in-1）----------
    dict(id="D5-1", cat="D5_复杂组合", res=R_FULL,
         prompt="a girl with long black hair in a white sailor uniform, running down a school corridor, sunset light through the windows, warm nostalgic atmosphere, cherry blossom petals floating in the air",
         expect="6要素齐: 黑长发/白水手服/走廊奔跑/夕阳侧光/怀旧暖调/飘落花瓣 —— 数缺几项"),
    dict(id="D5-2", cat="D5_复杂组合", res=R_LAND,
         prompt="a girl in a red raincoat holding a paper lantern, standing on a stone bridge at night, heavy rain, reflections on wet stone, lonely melancholic mood",
         expect="6要素齐: 红雨衣/纸灯笼/石桥/夜雨/湿地反光/孤寂氛围"),
    dict(id="D5-3", cat="D5_复杂组合", res=R_LAND,
         prompt="a girl in silver armor kneeling on a battlefield at dawn, broken sword in her right hand, banners burning behind her, cold blue light, epic tragic atmosphere",
         expect="6要素齐: 银甲/跪姿/黎明战场/右手断剑/燃烧旗帜/冷蓝光"),
    dict(id="D5-4", cat="D5_复杂组合", res=R_FULL,
         prompt="a girl in a yellow summer dress sitting on a wooden pier, bare feet touching the water, straw hat in her lap, seagulls in the distance, bright afternoon sunlight",
         expect="6要素齐: 黄裙/坐栈桥/赤足触水/膝上草帽/远处海鸥/午后强光"),
    dict(id="D5-5", cat="D5_复杂组合", res=R_LAND,
         prompt="a girl in a black gothic dress standing in a candle lit library, holding an open book, dust particles in the light beams, tall bookshelves behind her, mysterious dim atmosphere",
         expect="6要素齐: 黑哥特裙/烛光图书馆/手持翻开的书/光束尘埃/高书架/幽暗氛围"),
    # ---------- D6 画面内文字 + 极端透视（AGENTS 标注"模型写不对"但从未实测）----------
    dict(id="D6-1", cat="D6_文字透视", res=R_LAND, neg="text_ok",
         prompt='a girl standing in front of a shop sign that reads "CAFE", street scene',
         expect='招牌上是否出现可读的 "CAFE"（拼写正确才 PASS）'),
    dict(id="D6-2", cat="D6_文字透视", res=R_SQ, neg="text_ok",
         prompt='a girl holding up a book, the cover title reads "MAGIC"',
         expect='书封是否出现可读的 "MAGIC"（拼写正确才 PASS）'),
    dict(id="D6-3", cat="D6_文字透视", res=R_SQ,
         prompt="fisheye lens view of a girl looking down at the camera, extreme wide angle distortion",
         expect="鱼眼畸变成立且五官/肢体不崩（畸变≠崩坏）"),
    dict(id="D6-4", cat="D6_文字透视", res=R_FULL,
         prompt="extreme low angle worms eye view of a girl standing above the camera, dramatic perspective",
         expect="仰视透视成立，腿/躯干比例不断裂"),
    dict(id="D6-5", cat="D6_文字透视", res=R_LAND, neg="text_ok",
         prompt='a night street with neon signs reading "RAMEN", a girl walking away from camera',
         expect='霓虹招牌是否出现可读的 "RAMEN"'),
]

DEFAULT_SEEDS = [111111, 222222]
OUT_DIR = ROOT / "workspace" / "diag"


def submit(wf: dict, base: str) -> str:
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"提交失败 {r.status_code}: {r.text[:500]}")
    return r.json()["prompt_id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="仅跑某类前缀，如 D1")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seeds = args.seeds if args.seeds else DEFAULT_SEEDS
    items = [s for s in SUITE if not args.only or s["id"].startswith(args.only)]
    base = comfy_base_url()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "manifest.json"
    manifest: list[dict] = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    done = {(m["id"], m["seed"]) for m in manifest if m.get("file")}

    total = len(items) * len(seeds)
    print(f"[diag] {len(items)} 题 × {len(seeds)} seed = {total} 张 | ckpt={args.ckpt} steps={args.steps} cfg={args.cfg}")
    if args.dry_run:
        for s in items:
            print(f"  {s['id']:6s} {s['cat']:12s} {s['res']} | {s['prompt'][:70]}")
            print(f"         期望: {s['expect']}")
        return

    comfy_root = resolve_comfy_root()
    n = 0
    t_all = time.time()
    for s in items:
        for seed in seeds:
            n += 1
            if (s["id"], seed) in done:
                print(f"[{n}/{total}] {s['id']} seed={seed} 已存在，跳过")
                continue
            w, h = s["res"]
            neg = NEG_TEXT_OK if s.get("neg") == "text_ok" else NEG
            wf = build_sdxl_clean_workflow(
                QUAL + s["prompt"],
                seed=seed, steps=args.steps, cfg=args.cfg,
                width=w, height=h,
                filename_prefix=f"diag_{s['id']}_{seed}",
                ckpt=args.ckpt, negative_prompt=neg,
            )
            t0 = time.time()
            try:
                pid = submit(wf, base)
                imgs = wait_images(pid, base, timeout_s=600)
            except Exception as exc:  # noqa: BLE001
                print(f"[{n}/{total}] {s['id']} seed={seed} ❌ {exc}")
                manifest.append({**{k: s[k] for k in ("id", "cat", "prompt", "expect")},
                                 "seed": seed, "res": [w, h], "file": None, "error": str(exc)})
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                continue
            dt = time.time() - t0
            saved = None
            for sub, fn in imgs:
                src = comfy_root / "output" / (sub or "") / fn
                if src.exists():
                    dst = OUT_DIR / f"{s['id']}_{seed}.png"
                    dst.write_bytes(src.read_bytes())
                    saved = str(dst)
            print(f"[{n}/{total}] {s['id']} seed={seed} {w}x{h} {dt:.0f}s -> {saved}")
            manifest.append({**{k: s[k] for k in ("id", "cat", "prompt", "expect")},
                             "seed": seed, "res": [w, h], "file": saved, "sec": round(dt, 1)})
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[diag] 完成 {n} 张，总耗时 {(time.time()-t_all)/60:.1f} min，manifest={manifest_path}")


if __name__ == "__main__":
    main()
