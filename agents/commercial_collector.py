#!/usr/bin/env python3
"""
commercial_collector.py — 商业立绘采集器（正样本库建设）

【用途】从二次元手游 wiki（biligame 碧蓝航线）批量抓取官方立绘/时装图，
  作为质量判据的"真商业立绘"正样本基准。2026-08-24 教训：output AI 图非商业立绘，
  真基准必须来自官方素材。

【原理】
  1. 用 MediaWiki API 按角色页抓页面 HTML
  2. 提取 hdslb/bfs 大图（官方图床, 角色立绘/时装图）
  3. 只保留 ≥MIN_SIZE 的大图（过滤小图标/表情）
  4. 去重下载到正样本目录

【用法】
  python commercial_collector.py --chars 企业 拉菲 标枪 独角兽 --out <dir>
  python commercial_collector.py --chars-file chars.txt --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
from pathlib import Path

import requests

WIKI = "https://wiki.biligame.com/blhx"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REFERER = "https://wiki.biligame.com/"
MIN_SIZE = 512        # 最短边 < 512 丢弃(小图标/表情)
MIN_BYTES = 50_000    # 文件 < 50KB 丢弃(缩略图/低质)
# biligame 图床 + Fandom 图床(static.wikia.nocookie.net)
IMG_RE = re.compile(r'https://(?:i\d+\.hdslb\.com/bfs/game|patchwiki\.biligame\.com/images/blhx|static\.wikia\.nocookie\.net)/[^"\')\s]+\.(?:png|jpg|jpeg|webp)', re.I)


def fetch_char_page(char: str, wiki: str = WIKI) -> str:
    import urllib.parse
    url = f"{wiki}/{urllib.parse.quote(char)}"
    r = requests.get(url, headers={"User-Agent": UA, "Referer": REFERER},
                     timeout=25)
    r.raise_for_status()
    return r.text


def extract_images(html: str) -> list[str]:
    urls = IMG_RE.findall(html)
    # 去掉 @64w 之类的缩放后缀
    cleaned = [re.sub(r'@\d+w.*$', '', u) for u in urls]
    # 过滤 thumb 缩略图(patchwiki/thumb/xxx) —— 优先原始图, 缩略图是二次压缩的
    cleaned = [u for u in cleaned if "/thumb/" not in u]
    # 优先 PNG(无损), 再 jpg
    cleaned.sort(key=lambda u: 0 if u.lower().endswith((".png", ".webp")) else 1)
    return list(dict.fromkeys(cleaned))   # 去重保序


def download(url: str, out_dir: Path, tag: str, idx: int) -> Path | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Referer": REFERER},
                         timeout=30)
        if r.status_code != 200 or len(r.content) < MIN_BYTES:
            return None
        ext = Path(url.split("?")[0]).suffix or ".png"
        if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            ext = ".png"
        # 用内容哈希命名, 自动去重
        h = hashlib.md5(r.content).hexdigest()[:10]
        out = out_dir / f"{tag}_{idx:02d}_{h}{ext}"
        out.write_bytes(r.content)
        # 验证尺寸 (with 块确保句柄释放, 否则 Windows WinError 32)
        try:
            from PIL import Image
            with Image.open(out) as im:
                if min(im.size) < MIN_SIZE:
                    out.unlink()
                    return None
            return out
        except Exception:
            out.unlink()
            return None
    except Exception as e:
        print(f"    [skip] {url[:60]}... {str(e)[:40]}")
        return None


def collect(chars: list[str], out_dir: Path, per_char: int, wiki: str = WIKI) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"chars": 0, "downloaded": 0, "skipped": 0}
    for ci, char in enumerate(chars):
        print(f"[{ci+1}/{len(chars)}] {char} ...")
        try:
            html = fetch_char_page(char, wiki)
        except Exception as e:
            print(f"    [fail] 页面获取失败: {str(e)[:60]}")
            stats["skipped"] += 1
            continue
        urls = extract_images(html)
        print(f"    找到 {len(urls)} 张图")
        got = 0
        for i, u in enumerate(urls):
            if got >= per_char:
                break
            p = download(u, out_dir, char, i + 1)
            if p:
                got += 1
                stats["downloaded"] += 1
            time.sleep(0.3)   # 礼貌限速
        if got:
            stats["chars"] += 1
        print(f"    下载 {got} 张")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="商业立绘采集器")
    ap.add_argument("--chars", nargs="+", default=[], help="角色名列表")
    ap.add_argument("--chars-file", default=None, help="角色名文件(每行一个)")
    ap.add_argument("--out", default=r"C:\Users\zwq\kohya_ss\train_data\commercial_samples",
                    help="正样本输出目录")
    ap.add_argument("--per-char", type=int, default=6, help="每角色最多抓几张")
    ap.add_argument("--wiki", default=WIKI,
                    help="MediaWiki 源(默认碧蓝航线; Fandom 如 https://megamitensei.fandom.com)")
    args = ap.parse_args()

    chars = list(args.chars)
    if args.chars_file:
        with open(args.chars_file, encoding="utf-8") as f:
            chars += [ln.strip() for ln in f if ln.strip()]
    if not chars:
        print("请提供 --chars 或 --chars-file")
        return

    print(f"采集 {len(chars)} 个角色 → {args.out} (每角色≤{args.per_char}张, 源: {args.wiki})")
    stats = collect(chars, Path(args.out), args.per_char, wiki=args.wiki)
    print(f"\n完成: 成功{stats['chars']}角色 / 下载{stats['downloaded']}张 / 跳过{stats['skipped']}")
    n = len(list(Path(args.out).glob("*")))
    print(f"样本库现有 {n} 张")


if __name__ == "__main__":
    main()
