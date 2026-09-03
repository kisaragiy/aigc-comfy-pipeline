#!/usr/bin/env python3
"""vlm_chain_check.py — 链式VLM质检(本地qwen3.5:9b, 免费)

用法: python scripts/vlm_chain_check.py check <img> [--verbose]
      python scripts/vlm_chain_check.py batch <dir>
核心: qwen3.5:9b 默认思考模式 → 必须 think:false, 否则输出变空(SOUL教训)
主判: 本地免费; 结构崩坏用"区域专用prompt"(手/脸) + 链式(全身→局部)
"""
from __future__ import annotations
import base64, json, subprocess, sys, os, re

WSL = ["wsl.exe", "-e", "bash", "-lc"]
WIN_IMG_PREFIX = "IMG"  # 占位, 实际用 /mnt/c 路径

def win_to_wsl(path: str) -> str:
    p = path.replace("\\", "/")
    if p.startswith("C:/"):
        return "/mnt/c/" + p[3:]
    return p

def wsl_b64(wsl_img: str) -> str:
    """在WSL内把图转base64"""
    cmd = f"python3 -c \"import base64;print(base64.b64encode(open('{wsl_img}','rb').read()).decode())\""
    r = subprocess.run(WSL + [cmd], capture_output=True, text=True, timeout=120)
    return r.stdout.strip()

def qwen_vision(wsl_img: str, prompt: str, model: str = "qwen3.5:9b") -> str:
    b64 = wsl_b64(wsl_img)
    payload = {
        "model": model, "prompt": prompt, "images": [b64],
        "stream": False, "think": False,
        "options": {"temperature": 0.1, "num_predict": 600},
    }
    # 写payload到 Windows 临时目录, WSL 经 /mnt/c 读——避免命令行超长(WinError 206)
    tmp_win = os.path.expandvars("$LOCALAPPDATA/Temp/vlm_payload.json")
    with open(tmp_win, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    tmp_wsl = win_to_wsl(tmp_win)
    cmd = f"curl -s http://127.0.0.1:11434/api/generate -d @{tmp_wsl}"
    r = subprocess.run(WSL + [cmd], capture_output=True, text=True, timeout=300)
    try:
        data = json.loads(r.stdout)
        return data.get("response", "")
    except Exception as e:
        return f"ERROR: {r.stdout[:200]} {e}"

# 区域专用 prompt
PROMPT_HAND = "你是动漫立绘结构质检员。仔细检查图中人物的【手部】: 有没有多余手指、手指融合连体、关节错位、手指消失、握持姿势崩坏。只输出JSON: {\"hand_ok\": true/false, \"hand_issue\": \"具体问题或空\"}"
PROMPT_FACE = "你是动漫立绘结构质检员。仔细检查图中人物的【脸部五官】: 有没有眼睛扭曲、五官错位、表情崩坏、面部比例失调。只输出JSON: {\"face_ok\": true/false, \"face_issue\": \"具体问题或空\"}"
PROMPT_FULL = "你是动漫立绘结构质检员。检查整张图的结构问题(手/脸/身体/道具): 多余手指、手指融合、五官扭曲、肢体穿模、道具崩坏。只输出JSON: {\"has_defect\": true/false, \"defects\": [\"具体问题\"]}"

def parse_json(s: str) -> dict:
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m: return {"raw": s[:200]}
    try: return json.loads(m.group(0))
    except Exception: return {"raw": s[:200]}

def check_one(img: str, verbose=False) -> dict:
    wimg = win_to_wsl(img)
    if not os.path.exists(img):
        return {"image": img, "error": "not_found"}
    full = parse_json(qwen_vision(wimg, PROMPT_FULL))
    hand = parse_json(qwen_vision(wimg, PROMPT_HAND))
    face = parse_json(qwen_vision(wimg, PROMPT_FACE))
    res = {"image": img, "chain": {"full": full, "hand": hand, "face": face}}
    res["has_defect"] = bool(
        (full.get("has_defect") or
         hand.get("hand_ok") is False or
         face.get("face_ok") is False))
    res["defects"] = []
    if full.get("defects"): res["defects"] += full["defects"]
    if hand.get("hand_issue"): res["defects"].append("手:" + hand["hand_issue"])
    if face.get("face_issue"): res["defects"].append("脸:" + face["face_issue"])
    if verbose:
        print(f"  {os.path.basename(img)}: defect={res['has_defect']} {res['defects'][:2]}")
    return res

def main():
    if len(sys.argv) < 3:
        print("用法: vlm_chain_check.py check <img> | batch <dir>")
        return
    mode, target = sys.argv[1], sys.argv[2]
    verbose = "--verbose" in sys.argv
    if mode == "check":
        r = check_one(target, verbose=True)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif mode == "batch":
        from pathlib import Path
        imgs = [str(p) for p in Path(target).rglob("*") if p.suffix.lower() in (".png",".jpg")]
        print(f"批量 {len(imgs)} 张...")
        defects = 0; err = 0
        for i, im in enumerate(imgs):
            r = check_one(im, verbose)
            if "error" in r: err += 1; continue
            if r["has_defect"]:
                defects += 1
                print(f"  [疑似崩坏] {os.path.basename(im)}: {r['defects'][:2]}")
            if i % 5 == 0 and i: print(f"  ... {i}/{len(imgs)}")
        print(f"\n完成: {len(imgs)}张, 疑似崩坏 {defects}, 错误 {err}")

if __name__ == "__main__":
    main()
