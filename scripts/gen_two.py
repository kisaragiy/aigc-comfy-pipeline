"""双人/多人分区生图 — M1 多人塌缩的生产级入口

背景：单条 prompt 出双人时，模型 100% 塌缩成 1 人（诊断集 v1 实测 8/8）。
根因（ComfyUI 官方 area_composition 文档直引）："Stable Diffusion tries to make the overall
image consistent with itself and one of the side effects of that is merging the hair colors together."
解法：ConditioningSetAreaPercentage 把各角色 prompt 锁进各自区域，同时生成。
实测（scripts/diag_area.py, 8张）：人数正确 7/8，左右属性正确 6/8，加权 87.5%（基线 0%）。

用法（英文 tag 效果最好——CLIP 对中文弱）：
  python scripts/gen_two.py \
      --left "1girl, silver long hair, white gothic dress, red eyes" \
      --right "1girl, black short hair, black military uniform, gold eyes" \
      --scene "2girls, standing side by side, full body, night rooftop, city lights" \
      --count 2

参数经验（实测）：
  --overlap 0     硬切，接缝偶尔被模型合理化为窗框/柱子（可接受，2/8 出现）
  --overlap 0.05  左右各向中间扩 5%，缓解硬切；代价是中间区域两个 prompt 竞争
  分辨率：双人横构图 1216x832（默认）；双人全身竖构图用 --res 1024x1216
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "scripts"))

import requests  # noqa: E402

from comfy_utils import comfy_base_url, wait_images, resolve_comfy_root  # noqa: E402
from diag_area import build_area_workflow  # noqa: E402  (复用已验证的构建器，不复制代码)

# R4 颜色守恒（实测唯一有效解法 = 负向排斥；权重括号无效甚至加剧，后处理会连带毁掉该留的颜色）
_HAIR_COLORS = ["black", "brown", "blonde", "red", "orange", "silver", "white",
                "blue", "green", "purple", "pink", "grey"]


def build_color_guard(keep_hair: str = "", extra: str = "") -> str:
    """生成颜色守恒负向词：排斥除 keep_hair 之外的所有发色 + 渐变发。

    依据实测（knowledge/aigc E阶段附录C）：V2_negative 组红溢出显著减少且顺带修正配饰错色；
    V1 权重括号无效（红更鲜艳）；V3 权重+负向互相抵消；V4 全局后处理不可用。

    ⚠️ 多角色必须传多色白名单：负向是全局的，`--guard-hair black` 会连右区的 silver hair
       一起排斥（实测右区正向恰好压住了，但机制上不安全）→ 双人图请写 "black,silver"。
    """
    parts = []
    keeps = {c.strip().lower() for c in keep_hair.split(",") if c.strip()}
    if keeps:
        parts += [f"{c} hair" for c in _HAIR_COLORS if c not in keeps]
        parts += ["gradient hair", "multicolored hair", "colored hair tips", "two-tone hair"]
    if extra.strip():
        parts.append(extra.strip(", "))
    return ", ".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--left", required=True, help="左侧角色 prompt（英文 tag）")
    ap.add_argument("--right", required=True, help="右侧角色 prompt（英文 tag）")
    ap.add_argument("--scene", default="2girls, standing side by side, simple background",
                    help="全局场景/氛围（建议含 2girls）")
    ap.add_argument("--res", default="1216x832", help="WxH，默认 1216x832")
    ap.add_argument("--count", type=int, default=1, help="出图张数（每张换 seed）")
    ap.add_argument("--seed", type=int, default=-1, help="固定 seed（-1=随机）")
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=6.5)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--overlap", type=float, default=0.05,
                    help="交界带填缝。实测 0.05 = 最优默认（8/8 人数正确、0接缝、0串色）")
    ap.add_argument("--base-strength", type=float, default=1.0)
    ap.add_argument("--region-strength", type=float, default=1.0)
    ap.add_argument("--guard-left", default="", metavar="COLOR",
                    help="左侧角色发色守恒（分区负向，如 black）——排斥其他发色只作用于左区。"
                         "⚠️只懂'keep色'粒度：若想既保黑发又保红发带，需用 --neg-left 直传精确词")
    ap.add_argument("--guard-right", default="", metavar="COLOR",
                    help="右侧角色发色守恒（分区负向，如 silver）")
    ap.add_argument("--neg-left", default="", metavar="STR",
                    help="[推荐·精确] 左区直传负向词，绕过 build_color_guard。"
                         "R4 场景(黑发+红发带)：禁'染色'但留 'red hair' 实例的共享 token——"
                         "用 gradient hair / hair tinted red / colored hair tips，别用整条 red hair（会连累 red hair ribbon）")
    ap.add_argument("--neg-right", default="", metavar="STR",
                    help="[推荐·精确] 右区直传负向词。")
    ap.add_argument("--guard-hair", default="", metavar="COLOR",
                    help="[实验性·仅单人] 全局负向。⚠️双人分区场景会误伤另一角色（实测B组右区面部黑块）——请改用 --guard-left/--guard-right")
    ap.add_argument("--neg-extra", default="", help="追加自定义负向词")
    ap.add_argument("--prefix", default="two")
    ap.add_argument("--outdir", default=str(ROOT / "workspace"))
    args = ap.parse_args()

    w, h = (int(x) for x in args.res.lower().split("x"))
    case = {"id": args.prefix, "ref": "gen_two", "res": (w, h),
            "base": args.scene, "left": args.left, "right": args.right, "expect": ""}
    base_url = comfy_base_url()
    root = resolve_comfy_root()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    import random
    saved_all = []
    for i in range(args.count):
        seed = args.seed if args.seed != -1 else random.randint(1, 2**48 - 1)
        guard = build_color_guard(args.guard_hair, args.neg_extra)  # 实验性全局
        # 直传负向（精确）优先于 guard（keep色粒度粗，区分不了 red hair vs red hair ribbon）
        gl = args.neg_left if args.neg_left.strip() else (build_color_guard(args.guard_left) if args.guard_left else "")
        gr = args.neg_right if args.neg_right.strip() else (build_color_guard(args.guard_right) if args.guard_right else "")
        if i == 0:
            if guard:
                print(f"[guard·全局·仅单人] {guard[:100]}... ⚠️双人会误伤另一角色")
            if gl:
                print(f"[guard·左区] {gl[:90]}...")
            if gr:
                print(f"[guard·右区] {gr[:90]}...")
        wf = build_area_workflow(case, seed=seed, steps=args.steps, cfg=args.cfg, ckpt=args.ckpt,
                                 overlap=args.overlap, base_strength=args.base_strength,
                                 region_strength=args.region_strength,
                                 neg_extra=guard, neg_left=gl, neg_right=gr)
        t0 = time.time()
        r = requests.post(f"{base_url}/prompt", json={"prompt": wf}, timeout=60)
        if r.status_code != 200:
            print(f"❌ 提交失败 {r.status_code}: {r.text[:400]}")
            sys.exit(1)
        imgs = wait_images(r.json()["prompt_id"], base_url, timeout_s=600)
        for sub, fn in imgs:
            src = root / "output" / (sub or "") / fn
            if src.exists():
                dst = outdir / f"{args.prefix}_{seed}.png"
                dst.write_bytes(src.read_bytes())
                saved_all.append(str(dst))
                print(f"[{i+1}/{args.count}] seed={seed} {w}x{h} {time.time()-t0:.0f}s -> {dst}")
    if not saved_all:
        print("❌ 未产出图片")
        sys.exit(2)
    print("\n交付:")
    for s in saved_all:
        print("  ", s)
    print("\n⚠️ 人数/属性请人眼过目（本地 VLM 判质不可靠——B阶段已实证）。"
          "残留已知问题: 接缝伪影~25%、属性偶串~12%、偶发多出第三人~12%")


if __name__ == "__main__":
    main()
