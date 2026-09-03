#!/usr/bin/env python3
"""
polish_engine.py — D阶段 顶级商业图打磨引擎

三轴标准（2026-08-30 定稿）:
  轴3 七维: 面部25 / 线条20 / 手身15 / 光影15 / 构图10 / 精致度10 / 氛围10
  硬伤: 噪点/线条断/脸崩/手扭 → 任一直接 ≤5 不合格
  轴1 层级: 合格5-7 / 优质7-8.5 / 顶级≥8.5 / 代表作≥9
  轴2 用途: 不同用途短板容忍度不同

VLM 主判 failover 链: qwen3.8-flash(主) → deepseek-vision-exp(fallback)
  (本地VLM判结构不可靠, B阶段已证, 仅人眼复核用)

用法:
  python polish_engine.py detect <img> [--use library|portrait]   # 七维质检+定位弱项
  python polish_engine.py polish <img> <weak_action> <seed>       # 施行修复动作
  python polish_engine.py loop <img> [--rounds 3] [--target 8.5]  # 打磨循环
"""
from __future__ import annotations
import json, os, sys, time, base64
import urllib.request

# ── 七维质检 prompt (逐维打分, 带参考基准) ──
SEVEN_DIM_PROMPT = """你是顶级商业动漫立绘质检员。按7个维度给这张图打分(每维0-10, 参考主流游戏官方立绘如碧蓝航线/原神)。

【7维度 & 权重】(加权总分 = 各维×权重)
1. 面部质量 (25%): 眼睫毛分层/瞳孔高光/三庭五眼/无崩坏
2. 线条完成度 (20%): 轮廓流畅/粗细变化/无断裂/无像素噪点
3. 手部&身体比例 (15%): 手指关节分明/无扭曲/头身比标准(评手必须全身构图)
4. 光影色彩 (15%): 光源方向/明暗过渡/冷暖互补/无过曝烧色
5. 构图背景 (10%): 层次纵深/主体突出/背景不吞噬主体
6. 整体精致度 (10%): 细节密度/完成度/无像素化
7. 氛围感 (10%): 情绪传达/画面感染力

【硬伤检测】像素噪点/线条断裂/面部崩坏/手扭曲 → 命中任一, 总分直接≤5并明确标注硬伤。

【定位弱项】找出分数最低的1-2个维度, 说明为什么低(具体画面位置+问题)。

【输出 ONLY JSON】
{
 "dims": {"face": 0, "line": 0, "hand_body": 0, "light_color": 0, "compose": 0, "detail": 0, "mood": 0},
 "weighted_total": 0.0,
 "hard_flaw": "<无/或具体硬伤>",
 "weak_points": [{"dim": "手部&身体", "score": 0, "why": "具体问题+位置"}],
 "grade": "废/合格/优质/顶级/代表作",
 "summary": "<一句话>"
}"""


def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _dash_key():
    env = os.path.expanduser("~/AppData/Local/hermes/.env")
    if not os.path.isfile(env):
        return ""
    for line in open(env, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if "DASHSCOPE_API_KEY" in line and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _img_data_url(path: str, max_dim: int = 1100):
    """图 → data_url (缩到max_dim, JPEG)"""
    from PIL import Image
    import io
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_dim:
        r = max_dim / max(im.size)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _qwen38_chat(prompt: str, data_url: str, max_tokens: int = 3000) -> dict:
    """调 qwen3.8-flash (dashscope OpenAI兼容) 返回响应文本。"""
    key = _dash_key()
    if not key:
        return {"error": "no_dash_key"}
    base = os.environ.get("GATE_QWEN38_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    import requests
    for mt in (max_tokens, max_tokens + 1200):
        payload = {
            "model": os.environ.get("GATE_QWEN38_MODEL", "qwen3.8-flash"),
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}],
            "max_tokens": mt, "stream": False,
        }
        try:
            r = requests.post(base + "/chat/completions",
                              headers={"Authorization": f"Bearer {key}"},
                              json=payload, timeout=150)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"].get("content", "")
            if content and content.strip():
                return {"text": content}
            time.sleep(2)
        except Exception as e:
            return {"error": str(e)[:120]}
    return {"error": "empty"}


def _parse_json(s: str) -> dict:
    import re
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        return {"raw": s[:200]}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"raw": s[:200]}


def detect(image_path: str, use: str = "library") -> dict:
    """七维质检: qwen3.8-flash 逐维打分 + 定位弱项 + 硬伤。"""
    if not os.path.exists(image_path):
        return {"image": image_path, "error": "not_found"}
    # 用途微调 prompt(轴2: 不同用途短板容忍度不同)
    use_extra = ""
    if use == "library":
        use_extra = "【用途: 角色立绘/角色卡】近景为主, 面部与记忆点权重要高, 构图次之。"
    elif use == "portrait":
        use_extra = "【用途: 头像/特写】面部是命门, 面部质量权重再提高。"
    elif use == "kv":
        use_extra = "【用途: 游戏主视觉】构图/主体突出权重要高, 脸部是远景可容忍。"
    full = SEVEN_DIM_PROMPT + "\n" + use_extra
    data_url = _img_data_url(image_path)
    resp = _qwen38_chat(full, data_url)
    if "error" in resp:
        return {"image": image_path, "error": resp["error"]}
    parsed = _parse_json(resp["text"])
    # 补用途
    parsed["use"] = use
    parsed["image"] = image_path
    # 如果 qwen3.8 失败, 记录原始文本便于 fallback 判断
    parsed["raw"] = resp["text"][:600]
    return parsed


def test():
    """自测: 对 celeste closeup / battle 跑七维质检。"""
    base = "C:/Users/zwq/aigc-comfy-pipeline/workspace/"
    for f in ["celeste_closeup.png", "celeste_battle.png"]:
        p = base + f
        if not os.path.exists(p):
            print(f"{f}: 不存在")
            continue
        print(f"\n=== {f} ===")
        r = detect(p, use="portrait" if "closeup" in f else "library")
        if "error" in r:
            print("  ERROR:", r["error"])
            continue
        print("  七维:", r.get("dims"))
        print("  加权总分:", r.get("weighted_total"), " 等级:", r.get("grade"))
        print("  硬伤:", r.get("hard_flaw"))
        for wp in r.get("weak_points", [])[:2]:
            print(f"  弱项[{wp.get('dim')}] {wp.get('score')}: {str(wp.get('why'))[:60]}")
        print("  总结:", str(r.get("summary"))[:70])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "detect":
        img = sys.argv[2]
        use = sys.argv[3] if len(sys.argv) > 3 else "library"
        print(json.dumps(detect(img, use), ensure_ascii=False, indent=1))
    else:
        test()
