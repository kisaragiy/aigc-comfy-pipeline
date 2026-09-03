"""M1 多人塌缩修复验证 — Area Composition 分区提示词

对标一手官方：
  ComfyUI 官方 examples "Area Composition"
  https://comfyanonymous.github.io/ComfyUI_examples/area_composition/
  官方原文（根因直引）："Stable Diffusion tries to make the overall image consistent with
  itself and one of the side effects of that is merging the hair colors together."
  → 多人塌缩机制 = 模型追求整体一致性时合并主体。解法 = 用 ConditioningSetArea 把
    各主体 prompt 锁进各自区域，同时生成（而非二次 pass，官方明确二次 pass 会让属性互串）。

本机节点（已 /object_info 硬验证，零依赖，无需装插件）：
  ConditioningSetAreaPercentage(conditioning, width, height, x, y, strength) -> CONDITIONING
  ConditioningCombine(conditioning_1, conditioning_2) -> CONDITIONING

结构：
  base(全局场景/画风，覆盖全图) + 左区(角色A) + 右区(角色B) --Combine--> KSampler.positive

验收标准（前置定义）：
  基线 = 原版单条 prompt 8/8 全塌缩成 1 人（诊断集 v1 实测）
  目标 = ≥6/8 出现恰好 2 人；≥4/8 左右属性归属正确

用法:
  python scripts/diag_area.py --dry-run
  python scripts/diag_area.py                       # 4题×2seed=8张
  python scripts/diag_area.py --overlap 0.05 --base-strength 0.8   # 扫参
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))

import requests  # noqa: E402

from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402

QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
NEG = (
    "worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
    "ugly, deformed, bad proportions, extra limbs, fused fingers, missing fingers, "
    "extra fingers, mutated hands, poorly drawn face, bad eyes, signature, watermark, "
    "text, error, cropped, monochrome, grayscale, lineart, sketch, uncolored, "
    "character sheet, reference sheet, multiple views"
)

# M1 四道题：原诊断集里 100% 塌缩的题目，改造为左右分区
CASES: list[dict] = [
    dict(id="A1", ref="D1-2", res=(1216, 832),
         base="2girls, cafe interior, wooden table, warm indoor lighting",
         left="1girl, sitting at the table, facing right, brown hair, white blouse",
         right="1girl, sitting at the table, facing left, black hair, green sweater",
         expect="恰好2人，隔桌相对而坐；左=棕发白衬衫，右=黑发绿毛衣"),
    dict(id="A2", ref="D2-1", res=(1216, 832),
         base="2girls, library interior, bookshelves, soft warm light",
         left="1girl, black long hair, reading an open book, looking down",
         right="1girl, brown short hair, standing, hands on hips, looking at viewer",
         expect="恰好2人；左=黑长发在读书，右=棕短发叉腰站立（左右不可换）"),
    dict(id="A3", ref="D3-2", res=(1216, 832),
         base="2girls, classroom, daylight from window",
         left="1girl, black hair, red framed glasses, school uniform",
         right="1girl, brown hair, blue framed glasses, school uniform",
         expect="恰好2人；左=黑发红框眼镜，右=棕发蓝框眼镜（属性不可串）"),
    dict(id="A4", ref="双人立绘(商业刚需)", res=(1216, 832),
         base="2girls, standing side by side, full body, simple gradient background",
         left="1girl, silver long hair, white gothic dress, red eyes",
         right="1girl, black short hair, black military uniform, gold eyes",
         expect="恰好2人全身；左=银长发白裙红瞳，右=黑短发黑军装金瞳"),
]
SEEDS = [111111, 222222]
OUT = ROOT / "workspace" / "diag_area"


def build_area_workflow(
    case: dict, *, seed: int, steps: int, cfg: float, ckpt: str,
    overlap: float, base_strength: float, region_strength: float,
    neg_extra: str = "", neg_left: str = "", neg_right: str = "",
) -> dict[str, Any]:
    """base(全图) + 左右两区 → ConditioningCombine 链 → KSampler。"""
    w, h = case["res"]
    wf: dict[str, Any] = {}
    nid = [0]

    def nxt() -> str:
        nid[0] += 1
        return str(nid[0])

    ck = nxt()
    wf[ck] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}

    def enc(text: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": [ck, 1]}}
        return n

    def area(cond: str, x: float, width: float, strength: float) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningSetAreaPercentage", "inputs": {
            "conditioning": [cond, 0], "width": round(width, 3), "height": 1.0,
            "x": round(x, 3), "y": 0.0, "strength": round(strength, 3)}}
        return n

    def combine(a: str, b: str) -> str:
        n = nxt()
        wf[n] = {"class_type": "ConditioningCombine",
                 "inputs": {"conditioning_1": [a, 0], "conditioning_2": [b, 0]}}
        return n

    # 全局 base：覆盖全图（官方做法：base 不设 area）
    c_base = enc(QUAL + case["base"])
    if base_strength != 1.0:
        n = nxt()
        wf[n] = {"class_type": "ConditioningSetAreaStrength",
                 "inputs": {"conditioning": [c_base, 0], "strength": round(base_strength, 3)}}
        c_base = n
    # 左右区：各占 0.5+overlap，中间轻微重叠可缓解接缝硬切
    half = 0.5 + overlap
    c_left = area(enc(QUAL + case["left"]), 0.0, half, region_strength)
    c_right = area(enc(QUAL + case["right"]), max(0.0, 1.0 - half), half, region_strength)

    positive = combine(combine(c_base, c_left), c_right)
    # 负向：全局基础 + （可选）分区负向。
    # 依据实测（E阶段附录C）：正向分区而负向全局时，全局负向会误伤另一区角色的合法属性
    # （--guard-hair black 让右区 silver 角色脸部长黑块）→ 负向必须同样分区。
    neg_base = enc(NEG + (", " + neg_extra.strip(", ") if neg_extra.strip() else ""))
    if neg_left.strip() or neg_right.strip():
        parts = [neg_base]
        if neg_left.strip():
            parts.append(area(enc(neg_left.strip(", ")), 0.0, half, region_strength))
        if neg_right.strip():
            parts.append(area(enc(neg_right.strip(", ")), max(0.0, 1.0 - half), half, region_strength))
        negative = parts[0]
        for extra_neg in parts[1:]:
            negative = combine(negative, extra_neg)
    else:
        negative = neg_base

    lat = nxt()
    wf[lat] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    ks = nxt()
    wf[ks] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m",
        "scheduler": "karras", "denoise": 1, "model": [ck, 0],
        "positive": [positive, 0], "negative": [negative, 0], "latent_image": [lat, 0]}}
    vd = nxt()
    wf[vd] = {"class_type": "VAEDecode", "inputs": {"samples": [ks, 0], "vae": [ck, 2]}}
    sv = nxt()
    wf[sv] = {"class_type": "SaveImage", "inputs": {
        "filename_prefix": f'area_{case["id"]}_{seed}', "images": [vd, 0]}}
    return wf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="题号，逗号分隔如 A2,A3")
    ap.add_argument("--no-count-word", action="store_true",
                    help="去掉 base 中的 2girls 计数词（R3 假设验证用）")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--overlap", type=float, default=0.05,
                    help="左右区各向中间扩张比例。实测 0.05 最优：消 R1接缝+R3多余人（8/8）")
    ap.add_argument("--base-strength", type=float, default=1.0)
    ap.add_argument("--region-strength", type=float, default=1.0)
    ap.add_argument("--tag", default="v1", help="产物标签（扫参时区分批次）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seeds = args.seeds or SEEDS
    only = [x.strip() for x in args.only.split(",")] if args.only else None
    cases = [c for c in CASES if not only or c["id"] in only]
    # R3 假设验证开关：去掉 base 里的计数词（2girls），单变量对比是否影响"偶发第三人"
    if args.no_count_word:
        cases = [{**c, "base": c["base"].replace("2girls, ", "").replace("2girls ", "")} for c in cases]
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    mpath = OUT / f"manifest_{args.tag}.json"
    manifest: list[dict] = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else []

    print(f"[area] {len(cases)} 题 × {len(seeds)} seed = {len(cases)*len(seeds)} 张 | "
          f"overlap={args.overlap} base_str={args.base_strength} region_str={args.region_strength} tag={args.tag}")
    if args.dry_run:
        for c in cases:
            wf = build_area_workflow(c, seed=1, steps=args.steps, cfg=args.cfg, ckpt=args.ckpt,
                                     overlap=args.overlap, base_strength=args.base_strength,
                                     region_strength=args.region_strength)
            print(f'  {c["id"]} ({c["ref"]}) 节点数={len(wf)}  期望: {c["expect"]}')
        return

    root = resolve_comfy_root()
    n = 0
    for c in cases:
        for seed in seeds:
            n += 1
            wf = build_area_workflow(c, seed=seed, steps=args.steps, cfg=args.cfg, ckpt=args.ckpt,
                                     overlap=args.overlap, base_strength=args.base_strength,
                                     region_strength=args.region_strength)
            t0 = time.time()
            try:
                r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code}: {r.text[:400]}")
                imgs = wait_images(r.json()["prompt_id"], base, timeout_s=600)
            except Exception as exc:  # noqa: BLE001
                print(f'[{n}] {c["id"]} seed={seed} ❌ {exc}')
                continue
            saved = None
            for sub, fn in imgs:
                src = root / "output" / (sub or "") / fn
                if src.exists():
                    dst = OUT / f'{c["id"]}_{seed}_{args.tag}.png'
                    dst.write_bytes(src.read_bytes())
                    saved = str(dst)
            print(f'[{n}] {c["id"]} seed={seed} {time.time()-t0:.0f}s -> {saved}')
            manifest.append({"id": c["id"], "ref": c["ref"], "seed": seed, "tag": args.tag,
                             "expect": c["expect"], "file": saved,
                             "params": {"overlap": args.overlap, "base_strength": args.base_strength,
                                        "region_strength": args.region_strength,
                                        "steps": args.steps, "cfg": args.cfg}})
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[area] 完成，manifest={mpath}")


if __name__ == "__main__":
    main()
