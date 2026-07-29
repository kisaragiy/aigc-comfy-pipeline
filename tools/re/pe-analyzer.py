#!/usr/bin/env python3
"""PE 文件分析器 — 自动提取 PE 结构信息

用法:
  python pe-analyzer.py <path/to/exe_or_dll>
  python pe-analyzer.py --strings <path>   # 提取 ASCII/Unicode 字符串
  python pe-analyzer.py --scan <dir>       # 批量扫描目录
"""
import sys, struct, os

def read_dword(data, offset):
    return struct.unpack("<I", data[offset:offset+4])[0]

def read_word(data, offset):
    return struct.unpack("<H", data[offset:offset+2])[0]

def analyze_pe(path):
    with open(path, "rb") as f:
        data = f.read()
    
    if data[:2] != b"MZ":
        return {"error": "Not a PE file (no MZ header)"}
    
    pe_offset = read_dword(data, 0x3C)
    if data[pe_offset:pe_offset+4] != b"PE\x00\x00":
        return {"error": "Invalid PE signature"}
    
    info = {"file": os.path.basename(path), "size": len(data)}
    
    # File header
    fh = pe_offset + 4
    info["machine"] = {0x14c: "i386", 0x8664: "x64", 0xaa64: "ARM64"}.get(
        read_word(data, fh), f"0x{read_word(data,fh):04x}")
    info["sections"] = read_word(data, fh + 2)
    
    # Optional header
    oh = fh + 20
    magic = read_word(data, oh)
    info["pe_type"] = "PE32+" if magic == 0x20b else "PE32" if magic == 0x10b else f"Unknown(0x{magic:04x})"
    
    # Image base
    if magic in (0x10b, 0x20b):
        base_offset = oh + 28 if magic == 0x10b else oh + 32
        info["image_base"] = hex(read_dword(data, base_offset) if magic == 0x10b 
                                else struct.unpack("<Q", data[base_offset:base_offset+8])[0])
    
    # Subsystem
    sub_offset = oh + 68 if magic == 0x10b else oh + 72
    sub = read_word(data, sub_offset)
    subs = {1: "NATIVE", 2: "WINDOWS_GUI", 3: "WINDOWS_CUI"}
    info["subsystem"] = subs.get(sub, f"0x{sub:04x}")
    
    # Sections
    sec_offset = oh + (0xF0 if magic == 0x10b else 0xF8)
    info["sections_list"] = []
    for i in range(info["sections"]):
        off = sec_offset + i * 40
        name = data[off:off+8].rstrip(b"\x00").decode("ascii", errors="replace")
        v_size = read_dword(data, off + 8)
        v_addr = read_dword(data, off + 12)
        r_size = read_dword(data, off + 16)
        r_addr = read_dword(data, off + 20)
        chars = read_dword(data, off + 36)
        flags = []
        if chars & 0x20: flags.append("CODE")
        if chars & 0x40: flags.append("INIT_DATA")
        if chars & 0x80: flags.append("UNINIT_DATA")
        if chars & 0x20000000: flags.append("EXECUTE")
        if chars & 0x40000000: flags.append("READ")
        if chars & 0x80000000: flags.append("WRITE")
        info["sections_list"].append({
            "name": name, "vsize": v_size, "vaddr": hex(v_addr),
            "rsize": r_size, "raddr": hex(r_addr), "flags": flags,
            "suspicious": "WRITE" in flags and "EXECUTE" in flags
        })
    
    # Import/Export tables
    if magic in (0x10b, 0x20b):
        iat_offset = oh + (0x80 if magic == 0x10b else 0x90)
        iat_rva = read_dword(data, iat_offset)
        eat_offset = oh + (0x70 if magic == 0x10b else 0x78)
        eat_rva = read_dword(data, eat_offset)
        info["import_rva"] = hex(iat_rva) if iat_rva else "none"
        info["export_rva"] = hex(eat_rva) if eat_rva else "none"
    
    # Suspicious indicators
    info["warnings"] = []
    for sec in info["sections_list"]:
        if sec["suspicious"]:
            info["warnings"].append(f"RWX section: {sec['name']} — possible packed code")
    if info.get("sections", 0) > 8:
        info["warnings"].append(f"Many sections ({info['sections']}) — possible packer")
    suspicious_names = [s["name"] for s in info["sections_list"] 
                       if s["name"] in (".upx", ".packed", ".themida", ".vmp", ".enigma", ".aspack")]
    if suspicious_names:
        info["warnings"].append(f"Packer detected: {suspicious_names}")
    
    return info

def extract_strings(path, min_len=6):
    with open(path, "rb") as f:
        data = f.read()
    result = []
    current = b""
    for b in data:
        if 0x20 <= b <= 0x7e:
            current += bytes([b])
        else:
            if len(current) >= min_len:
                result.append(current.decode("ascii"))
            current = b""
    if len(current) >= min_len:
        result.append(current.decode("ascii"))
    return result

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    path = sys.argv[1]
    if "--strings" in sys.argv:
        idx = sys.argv.index("--strings")
        path = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else path
        strings = extract_strings(path)
        print(f"字符串 ({len(strings)} 条, >=6 字符):")
        for s in strings[:50]:
            print(f"  {s}")
        if len(strings) > 50:
            print(f"  ... 还有 {len(strings)-50} 条")
    elif "--scan" in sys.argv:
        idx = sys.argv.index("--scan")
        d = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else path
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            if f.endswith((".exe", ".dll", ".sys")):
                info = analyze_pe(fp)
                warns = "; ".join(info.get("warnings", []))
                print(f"  {f:30s} {info.get('machine','?'):6s} {info.get('pe_type','?'):8s} {'⚠️' if warns else '✅'} {warns[:60]}")
    else:
        info = analyze_pe(path)
        print(f"📁 {info['file']} ({info['size']} bytes)")
        print(f"  Machine:    {info.get('machine','?')}")
        print(f"  PE Type:    {info.get('pe_type','?')}")
        print(f"  Sections:   {info.get('sections',0)}")
        print(f"  Subsystem:  {info.get('subsystem','?')}")
        if 'image_base' in info:
            print(f"  ImageBase:  {info['image_base']}")
        for sec in info.get("sections_list", []):
            sus = " ⚠️ RWX" if sec.get("suspicious") else ""
            print(f"    [{sec['name']:8s}] vaddr={sec['vaddr']} vsize={sec['vsize']:>8x} "
                  f"rsize={sec['rsize']:>8x} flags={','.join(sec['flags'])}{sus}")
        print(f"\n  ⚠️ Warnings ({len(info.get('warnings',[]))}):")
        for w in info.get("warnings", []):
            print(f"    ⚠ {w}")
        print(f"  Import RVA: {info.get('import_rva','?')}")
        print(f"  Export RVA: {info.get('export_rva','?')}")

if __name__ == "__main__":
    main()
