"""G1 双人互动 + G2 3人+同场 — 探路（纯 prompt 基线，诚实问"模型能不能做"）

今天 M1-M6 收口的都是"质量维度"，但**题材盲区** G1(双人互动)/G2(3人+同场) 从没实测。
  - G1 互动（拥抱/牵手/对视）比 M1 的"并列站"更难——涉及肢体交叠，预测踩"融合/穿模"
  - G2 3人+ 比区域双区更难——预测踩"中间人塌缩/区域交界混乱"

先跑**纯 prompt 基线**（不上区域控制），诚实看模型基础能力，再决定要不要上控制。
（教训：先试模型能做什么，别一上来就上重型控制——M3/M6 已证明控制常帮倒忙）

验收：看每类真实崩坏模式（G1 哪些肢体融合/穿模？G2 中间人是否塌缩？）
用法: python scripts/g12_probe.py --dry-run | 跑
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
from go_knives_lora import build_sdxl_clean_workflow  # noqa: E402

QUAL = "masterpiece, best quality, anime style, detailed illustration, full color, "
NEG = ("worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, bad hands, "
       "ugly, deformed, bad proportions, extra limbs, fused fingers, missing fingers, "
       "extra fingers, mutated hands, poorly drawn face, bad eyes, signature, watermark, "
       "text, cropped, monochrome, grayscale, lineart, sketch, uncolored, character sheet")
OUT = ROOT / "workspace" / "g12_probe"
SEED = 333333

# G1 双人互动 —— 关键看肢体交叠是否融合/穿模
G1 = [
    ("hug", "two girls hugging each other warmly, both arms wrapped around, close embrace, full body",
     (768, 1344), "双人拥抱：手臂是否缠绕合理/有无融合"),
    ("handhold", "two girls holding hands, standing side by side, interlocked fingers, full body",
     (1216, 832), "双人牵手：手指是否交叠正确/有无多指融合"),
    ("eyelook", "two girls facing each other, looking into each other's eyes, close up, warm light",
     (896, 1152), "双人对视：面对面关系是否成立/脸有无穿模"),
]
# G2 3人+同场 —— 关键看中间人是否塌缩/区域混乱
G2 = [
    ("tri_stand", "three girls standing in a row, full body, group photo, equal size",
     (1344, 768), "3人站一排：人数是否恰好3/有无融合"),
    ("tri_pose", "three girls sitting together on a sofa, full body, indoor",
     (1344, 768), "3人坐沙发：三人位置关系/有无塌缩"),
    ("tri_scene", "three anime girls in a city street, walking, one in front two behind, distant",
     (1344, 768), "3人街景：前后层次/人数是否对"),
]


def _nid():
    n = [0]

    def nxt() -> str:
        n[0] += 1
        return str(n[0])
    return nxt


def build_wf(prompt: str, seed: int, ckpt: str, w: int, h: int) -> dict[str, Any]:
    return build_sdxl_clean_workflow(QUAL + prompt, seed=seed, steps=28, cfg=6.5,
                                     width=w, height=h, filename_prefix="g12",
                                     ckpt=ckpt, negative_prompt=NEG)


def submit(wf: dict, base: str) -> str:
    r = requests.post(f"{base}/prompt", json={"prompt": wf}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
    return r.json()["prompt_id"]


def save_first(pid: str, base: str, root: Path, out: Path) -> str | None:
    try:
        imgs = wait_images(pid, base, timeout_s=600)
    except Exception as e:  # noqa: BLE001
        print(f"   wait 失败: {e}")
        return None
    for sub, fn in imgs:
        src = root / "output" / (sub or "") / fn
        if src.exists():
            out.write_bytes(src.read_bytes())
            return str(out)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--ckpt", default="waiIllustriousSDXL_v160.safetensors")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    seeds = args.seeds or [SEED]
    base = comfy_base_url()
    OUT.mkdir(parents=True, exist_ok=True)
    root = resolve_comfy_root()

    # 合并 G1 + G2
    cases = [(f"G1_{k}", p, res, note) for k, p, res, note in G1] + \
            [(f"G2_{k}", p, res, note) for k, p, res, note in G2]

    if args.dry_run:
        print(f"[g12-probe] {len(cases)} 题 × {len(seeds)} seed = {len(cases)*len(seeds)} 张 | 纯prompt基线")
        for cid, p, res, note in cases:
            print(f"  {cid:20s} {res} | {note}")
            print(f"      {p[:80]}")
        return

    n = 0
    manifest = []
    mpath = OUT / "manifest.json"
    if mpath.exists():
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    done = {(m["id"], m["seed"]) for m in manifest}
    for cid, prompt, (w, h), note in cases:
        for seed in seeds:
            if (cid, seed) in done:
                continue
            n += 1
            t0 = time.time()
            try:
                pid = submit(build_wf(prompt, seed, args.ckpt, w, h), base)
                out = save_first(pid, base, root, OUT / f"{cid}_{seed}.png")
            except Exception as e:  # noqa: BLE001
                print(f"[{n}] {cid} seed={seed} ❌ {e}")
                continue
            print(f"[{n}] {cid} seed={seed} {time.time()-t0:.0f}s -> {out}")
            manifest.append({"id": cid, "seed": seed, "file": out, "prompt": prompt,
                             "note": note, "res": [w, h]})
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[g12-probe] 完成")


if __name__ == "__main__":
    main()
