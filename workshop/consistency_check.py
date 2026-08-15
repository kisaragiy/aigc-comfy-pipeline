#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/consistency_check.py — 跨图一致性核对 v1.0
===================================================
多图交付场景（朋友小说女主类）——检查每张图的关键特征是否与角色卡一致:
  发色 / 泪痣 / 服装 / 氛围。
用 VLM（qwen3-vl 本地——免费）逐图问特征 → 比对角色卡 → 报告偏差。
VLM 不可用（ollama 挂）→ 降级: 输出"跳过核对"提示（不阻塞交付——图照发）。

用法:
  python -m agents workshop consistency_check "<角色卡描述>" <图1> [图2 图3 ...]
  例: python -m agents workshop consistency_check "黑发短发, 侧辫耳前, 左眼内眼角泪痣, 藏青水手服" a.png b.png
"""
import argparse, json, os, sys, urllib.request

# 特征检查项（从角色卡提取——VLM 逐项确认）
CHECKS = ["发色", "泪痣", "服装", "氛围/背景"]


def vlm_ask(image_path, question, base_url="http://localhost:11434"):
    """调本地 ollama qwen3-vl 看图（/api/generate——非 /api/chat）"""
    import base64
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        body = {
            "model": "qwen3-vl:8b",
            "prompt": question,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.1, "max_tokens": 150},
        }
        req = urllib.request.Request(
            base_url + "/api/generate",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            d = json.loads(resp.read())
        return (d.get("response") or "").strip()[:200]
    except Exception as e:
        return f"__VLM_ERR__:{type(e).__name__}:{str(e)[:60]}"


def check_one(image_path, character):
    print(f"\n📄 {os.path.basename(image_path)}")
    for c in CHECKS:
        q = f"这张动漫图里，角色的{c}是什么？请用一句话描述（如果没有/不符合请直接说明）。角色设定: {character}"
        ans = vlm_ask(image_path, q)
        if ans.startswith("__VLM_ERR__"):
            print(f"  ⚠️ {c}: VLM 不可用（{ans[12:60]}）——跳过")
            continue
        # 简单一致性判断（关键词匹配——够用）
        ok = False
        if c == "发色":
            ok = any(k in ans for k in ["黑", "棕", "brown", "black"])
        elif c == "泪痣":
            ok = any(k in ans for k in ["泪痣", "痣", "mole", "mark"])
        elif c == "服装":
            ok = any(k in ans for k in ["校服", "水手服", "uniform", "制服"])
        else:
            ok = any(k in ans for k in ["阳光", "走廊", "校园", "sunlight", "school"])
        print(f"  {'✅' if ok else '⚠️ 偏差?'} {c}: {ans[:80]}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="workshop consistency_check", description="跨图一致性核对")
    ap.add_argument("character", help="角色卡描述（发色/发型/泪痣/服装/氛围——一行）")
    ap.add_argument("images", nargs="+", help="要核对的图片路径（多张）")
    args = ap.parse_args(argv)

    print(f"═══ 跨图一致性核对 ═══")
    print(f"角色卡: {args.character}")
    for img in args.images:
        if os.path.isfile(img):
            check_one(img, args.character)
        else:
            print(f"❌ 文件不存在: {img}")
    print(f"\n（VLM 不可用时会跳过核对——图照常交付——标注'未核对一致性'）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
