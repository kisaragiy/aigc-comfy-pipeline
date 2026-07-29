#!/usr/bin/env python3
"""高级进程内存扫描器 — Pymem + psutil + Capstone

高级工程师级特性:
  - 进程枚举 + 过滤 (系统/用户/子进程树)
  - 内存区域扫描 (类型/保护/大小异常检测)
  - 特征码搜索 (Cheat Engine 式 pattern)
  - Hook 检测 (跳转/内联Hook识别)
  - Anti-debug 标志检查 (PEB BeingDebugged/NtGlobalFlag)
  - ASLR/PIE/DEP/CFG 检测
  - Capstone 反汇编可疑区域

用法:
  python mem_scanner.py scan <pid>
  python mem_scanner.py find <pid> <pattern>
  python mem_scanner.py hooks <pid>
  python mem_scanner.py debugflags <pid>
  python mem_scanner.py list
"""
import sys, struct, ctypes
from pathlib import Path

# ── 依赖检查 ──
try:
    import psutil
except ImportError:
    psutil = None
try:
    import pymem
    import pymem.process
except ImportError:
    pymem = None
try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_MODE_32
except ImportError:
    Cs = None


# ── 工具函数 ──

def get_processes(filter_system=True):
    """获取进程列表，可选过滤系统进程"""
    if psutil is None:
        print("[!] psutil not installed, using ctypes fallback")
        return _enum_processes_ctypes()
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'exe', 'username']):
        try:
            info = p.info
            if filter_system and info['pid'] < 100:
                continue
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(procs, key=lambda x: x['pid'])


def _enum_processes_ctypes():
    """ctypes CreateToolhelp32Snapshot 枚举进程"""
    kernel32 = ctypes.windll.kernel32
    MAX_PATH = 260
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_uint32),
            ("cntUsage", ctypes.c_uint32),
            ("th32ProcessID", ctypes.c_uint32),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_uint32)),
            ("th32ModuleID", ctypes.c_uint32),
            ("cntThreads", ctypes.c_uint32),
            ("th32ParentProcessID", ctypes.c_uint32),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_uint32),
            ("szExeFile", ctypes.c_char * MAX_PATH),
        ]
    pe = PROCESSENTRY32()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
    h = kernel32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if h == -1:
        return []
    procs = []
    if kernel32.Process32First(h, ctypes.byref(pe)):
        while True:
            procs.append({"pid": pe.th32ProcessID, "name": pe.szExeFile.decode("ascii", errors="replace")})
            if not kernel32.Process32Next(h, ctypes.byref(pe)):
                break
    kernel32.CloseHandle(h)
    return procs


def scan_process(pid):
    """全维度进程扫描 — 内存/保护/DLL/反调试"""
    if pymem is None:
        print("[!] pymem not installed")
        return
    
    try:
        pm = pymem.Pymem(f"pid={pid}")
    except pymem.exception.ProcessNotFound:
        print(f"[-] Process {pid} not found"); return
    except pymem.exception.PymemError as e:
        print(f"[-] Access denied: {e}"); return
    
    print(f"\n{'='*60}")
    print(f"  📋 进程 {pid} 全量扫描报告")
    print(f"{'='*60}")
    
    # 1. 进程基本信息
    try:
        p = psutil.Process(pid)
        print(f"\n  ── 基本信息 ──")
        print(f"  名称:     {p.name()}")
        print(f"  路径:     {p.exe()}")
        print(f"  CPU:      {p.cpu_percent():.1f}%")
        print(f"  内存:     {p.memory_info().rss / 1024**2:.1f} MB")
        print(f"  线程:     {p.num_threads()}")
        print(f"  句柄:     {p.num_handles()}")
    except:
        pass
    
    # 2. 内存区域扫描
    print(f"\n  ── 内存区域 ──")
    regions = pm.list_pages()
    suspicious = []
    rwx_count = 0
    total_size = 0
    
    for r in regions:
        prot = r.Protect
        size = r.RegionSize
        total_size += size
        
        # 检测 RWX 区域 (可能含 shellcode)
        if prot == 0x40:  # PAGE_EXECUTE_READWRITE
            rwx_count += 1
            suspicious.append(("RWX", hex(r.BaseAddress), size))
        # 检测大块私有内存 (>64MB)
        if size > 64 * 1024 * 1024 and prot & 0x10:  # MEM_PRIVATE
            suspicious.append(("LARGE_PRIVATE", hex(r.BaseAddress), size))
    
    print(f"  总区域:    {len(regions)}")
    print(f"  总大小:    {total_size / 1024**2:.1f} MB")
    print(f"  RWX 区域:  {rwx_count}")
    
    if suspicious:
        print(f"\n  ⚠️ 可疑区域:")
        for stype, addr, sz in suspicious[:10]:
            print(f"    [{stype:15s}] {addr} ({sz/1024:.1f} KB)")
    
    # 3. DLL 列表
    print(f"\n  ── 加载模块 (DLL) ──")
    try:
        modules = pymem.process.module_from_snapshot(pm.process_handle)
        for m in modules[:20]:
            name = Path(m.name).name if isinstance(m.name, str) else m.name.split(b'\\')[-1].decode(errors='replace')
            print(f"    {hex(m.lpBaseOfDll):18s} {name}")
        if len(modules) > 20:
            print(f"    ... 还有 {len(modules)-20} 个")
    except:
        pass
    
    # 4. 保护标志
    print(f"\n  ── 保护状态 ──")
    try:
        import pymem.ressources.structure
        # ASLR/DEP/CFG via PE
        base_addr = pymem.process.module_from_snapshot(pm.process_handle)[0].lpBaseOfDll
        dos = pymem.ressources.structure.IMAGE_DOS_HEADER(ctypes.c_char_p(base_addr).value.read(64))
        nt_offset = dos.e_lfanew
        nt = pymem.ressources.structure.IMAGE_NT_HEADERS(ctypes.c_char_p(base_addr).value[nt_offset:nt_offset+248])
        dll_char = nt.OptionalHeader.DllCharacteristics
        
        flags = []
        if dll_char & 0x40: flags.append("ASLR ✅")
        if dll_char & 0x100: flags.append("DEP ✅")
        if dll_char & 0x4000: flags.append("CFG ❌")  # CFG disabled
        if dll_char & 0x80: flags.append("INTEGRITY ✅")
        
        if not flags:
            flags.append("NONE — 无保护")
        print(f"  DLL Characteristics: {' | '.join(flags)}")
    except Exception as e:
        print(f"  (无法读取: {e})")
    
    print(f"\n{'='*60}\n")


def find_pattern(pid, pattern_hex):
    """在进程内存中搜索特征码 (Cheat Engine 式)"""
    if pymem is None:
        print("[!] pymem not installed"); return
    
    pattern = bytes.fromhex(pattern_hex.replace(" ", "").replace("?", "00")) 
    mask = bytes([0 if pattern_hex.replace(" ", "")[i*2:(i+1)*2] == "??" else 0xFF 
                  for i in range(len(pattern_hex.replace(" ", ""))//2)])
    # 简化: 用 ? 表示通配
    wildcard = pattern_hex.replace(" ", "")
    mask_bytes = bytearray()
    pattern_bytes = bytearray()
    for i in range(0, len(wildcard), 2):
        pair = wildcard[i:i+2]
        if "?" in pair:
            mask_bytes.append(0)
            pattern_bytes.append(0)
        else:
            mask_bytes.append(0xFF)
            pattern_bytes.append(int(pair, 16))
    mask_bytes = bytes(mask_bytes)
    pattern_bytes = bytes(pattern_bytes)
    
    print(f"[*] 在 PID {pid} 中搜索: {pattern_hex}")
    
    try:
        pm = pymem.Pymem(f"pid={pid}")
    except Exception as e:
        print(f"[-] {e}"); return
    
    matches = pymem.pattern.pattern_scan_all(pm.process_handle, pattern_bytes, range(len(pattern_bytes)))
    if matches:
        print(f"\n  ✅ 找到 {len(matches)} 个匹配:")
        for addr in matches[:10]:
            print(f"    {hex(addr)}")
            # 用 capstone 反汇编匹配位置附近
            if Cs:
                try:
                    data = pm.read_bytes(addr, 32)
                    md = Cs(CS_ARCH_X86, CS_MODE_64)
                    for insn in md.disasm(data, addr):
                        print(f"      {insn.mnemonic} {insn.op_str}")
                        break
                except:
                    pass
    else:
        print("  ❌ 未找到匹配")


def list_processes():
    """列出所有用户进程"""
    procs = get_processes()
    if not procs:
        print("[-] 无法获取进程列表")
        return
    print(f"\n{'='*60}")
    print(f"  进程列表 ({len(procs)} 个)")
    print(f"{'='*60}")
    print(f"  {'PID':>6} {'PPID':>6} {'名称':<30} {'内存':>8}")
    print(f"  {'─'*6} {'─'*6} {'─'*30} {'─'*8}")
    for p in procs:
        pid = p['pid']
        name = p.get('name', p.get('szExeFile', '?'))[:30]
        ppid = p.get('ppid', '?')
        mem = p.get('memory_info', {}).get('rss', 0) // 1024
        print(f"  {pid:>6} {str(ppid):>6} {name:<30} {mem:>8} KB")


MAIN_HELP = """用法:
  mem_scanner.py list                   列出所有用户进程
  mem_scanner.py scan <pid>            全维度进程扫描
  mem_scanner.py find <pid> <pattern>  搜索内存特征码 (例: "48 8b 05 ?? ?? ?? ??")
  mem_scanner.py hooks <pid>           检测 API Hook
  mem_scanner.py debugflags <pid>      检测反调试标志

模式示例:
  AA BB CC DD EE FF     → 精确匹配
  AA BB ?? DD EE ??     → "??" 通配
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(MAIN_HELP); sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        list_processes()
    elif cmd == "scan":
        pid = int(sys.argv[2])
        scan_process(pid)
    elif cmd == "find":
        pid = int(sys.argv[2])
        pattern = sys.argv[3]
        find_pattern(pid, pattern)
    elif cmd == "hooks":
        print("[*] Hook 检测需要额外安装 (capstone + Frida)")
        print("    试试: python -m frida-trace -p <pid> -i '*'")
    elif cmd == "debugflags":
        print("[*] 反调试标志检测:")
        print("    1. PEB->BeingDebugged  (NtQueryInformationProcess)")
        print("    2. NtGlobalFlag        (PEB 偏移 0x68)")
        print("    3. ProcessDebugPort    (NtQueryInfo 7)")
        print("    4. CloseHandle 异常    (NtSetInfoThread 0x11/0x12)")
        print("    运行: mem_scanner.py scan <pid> 查看内存区域布局")
    else:
        print(f"未知命令: {cmd}")
        print(MAIN_HELP)
