#!/usr/bin/env python3
"""游戏资源包提取器 — 识别并提取常见游戏存档格式

用法:
  python game-arch-extract.py identify <file>        # 识别格式
  python game-arch-extract.py extract <file> [out]    # 提取文件
  python game-arch-extract.py scan <dir>              # 批量扫描
"""
import sys, os, struct

MAGIC_DB = [
    (b"PK\x03\x04", "Zip/APK"),
    (b"Rar!\x1a\x07", "RAR"),
    (b"\x1f\x8b\x08", "GZip"),
    (b"BM", "BMP (image)"),
    (b"\x89PNG\r\n\x1a\n", "PNG (image)"),
    (b"\xff\xd8\xff", "JPEG (image)"),
    (b"GIF8", "GIF (image)"),
    (b"RIFF", "AVI/WAV"),
    (b"\x7fELF", "ELF (Linux binary)"),
    (b"MZ", "PE (DLL/EXE)"),
    (b"OggS", "OGG (audio)"),
    (b"ftyp", "MP4 (video)"),
    (b"\x00\x00\x00\x0c\x6a\x50\x20\x20\x0d\x0a\x87\x0a", "JPEG 2000"),
    (b"\x1a\x45\xdf\xa3", "WebM/MKV (video)"),
    (b"\x42\x4c\x49\x4e\x44\x1a\xff\xff", "BLIND (NK Engine - Closers)"),
    (b"NKGD", "NK Archive"),
    (b"\x50\x41\x43\x4b", "PAK (Quake/Unity)"),
    (b"\x53\x42\x5a\x69\x70", "SBZip"),
]

def identify(filepath):
    with open(filepath, "rb") as f:
        head = f.read(16)
    for magic, desc in MAGIC_DB:
        if head.startswith(magic):
            return desc
    # Try to detect common types from extension
    ext = os.path.splitext(filepath)[1].lower()
    ext_map = {
        ".nk": "NK Engine Archive (Closers)",
        ".cmf": "Closers CMF Archive",
        ".unity3d": "Unity Asset Bundle",
        ".uasset": "Unreal Engine Asset",
        ".pak": "Unreal Engine PAK",
        ".upk": "Unreal Engine Package",
        ".wad": "WAD Archive",
        ".vpk": "Source Engine VPK",
        ".grp": "Generic Group Archive",
    }
    return ext_map.get(ext, f"Unknown (magic: {head[:8].hex()[:16]})")

def extract_nk(filepath, outdir):
    """NK Engine archive extractor (placeholder)"""
    print(f"[NK] 尝试提取: {filepath}")
    # NK archive structure varies by version
    # Version 1-4: simple header + offset/entry table
    # Version 5-10: encryption + block compression
    # Version 11+: XTEA encryption
    print("[NK] 提取需要知道档案版本号。")
    print("  查看 game-file-forensics skill 获取详细格式说明")

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else "."
    
    if cmd == "identify":
        if os.path.isdir(path):
            for f in os.listdir(path)[:20]:
                fp = os.path.join(path, f)
                if os.path.isfile(fp):
                    print(f"  {f:40s} → {identify(fp)}")
        else:
            print(f"{path} → {identify(path)}")
    
    elif cmd == "extract":
        if not os.path.exists(path):
            print(f"文件不存在: {path}"); return
        outdir = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(os.path.basename(path))[0]
        fmt = identify(path)
        print(f"格式: {fmt}")
        if "NK" in fmt or "Closers" in fmt:
            extract_nk(path, outdir)
        else:
            print(f"标准格式: 请用对应的解压工具 (7z/winrar/vgmtoolbox)")
    
    elif cmd == "scan":
        for f in os.listdir(path):
            fp = os.path.join(path, f)
            if os.path.isfile(fp) and os.path.getsize(fp) > 1024:
                print(f"  {f:40s} → {identify(fp)}")
    
    else:
        print(f"未知命令: {cmd}")

if __name__ == "__main__":
    main()
