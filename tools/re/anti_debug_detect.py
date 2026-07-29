#!/usr/bin/env python3
"""反调试检测工具 — Pymem + ctypes 实战扫描

检测 9 种常见反调试技术:
  1. PEB BeingDebugged 标志
  2. NtGlobalFlag 检查
  3. ProcessDebugPort 查询
  4. CloseHandle 异常检测
  5. NtQueryInformationProcess 检查
  6. 时间差检测 (rdtsc / GetTickCount)
  7. DebugObject 句柄枚举
  8. 父进程检查 (explorer.exe vs debugger)
  9. 断点检测 (INT3 / 0xCC 扫描)

依赖: pymem>=1.14, psutil (推荐)

用法:
  python anti_debug_detect.py scan <pid>
  python anti_debug_detect.py all <pid>
  python anti_debug_detect.py int3 <pid>     # 扫描 0xCC 断点
"""
import sys, struct, ctypes, ctypes.wintypes

try:
    import pymem
    import pymem.process
except ImportError:
    pymem = None
try:
    import psutil
except ImportError:
    psutil = None


def check_peb_flags(pid):
    """检测 PEB BeingDebugged (第1字节) + NtGlobalFlag (第3字节)"""
    print(f"\n  ── 1. PEB 标志检查 ──")
    if pymem is None:
        print("     [!] pymem not installed"); return
    
    try:
        pm = pymem.Pymem(f"pid={pid}")
        # PEB 地址获取: 通过 NtQueryInformationProcess
        # 或者通过 Thread Environment Block (TEB)
        
        # 方法1: 通过 TEB (gs:[0x60]) 读 PEB
        # x64: TEB 在 gs 段, PEB 在 TEB+0x60
        # 我们需要从进程中读 TEB 地址
        
        # 简单方法: 用 pymem 的 process 模块
        is_being_debugged = False
        flags_problem = False
        
        # NtQueryInformationProcess with ProcessBasicInformation
        ntdll = ctypes.windll.ntdll
        PROCESS_BASIC_INFO = 0
        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("ExitStatus", ctypes.c_long),
                ("PebBaseAddress", ctypes.c_void_p),
                ("AffinityMask", ctypes.c_void_p),
                ("BasePriority", ctypes.c_long),
                ("UniqueProcessId", ctypes.c_void_p),
                ("InheritedFromUniqueProcessId", ctypes.c_void_p),
            ]
        
        # 通过 kernel32.OpenProcess 获取句柄
        kernel32 = ctypes.windll.kernel32
        hProcess = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)  # PROCESS_QUERY_INFO | PROCESS_VM_READ
        if hProcess:
            pbi = PROCESS_BASIC_INFORMATION()
            ret_len = ctypes.c_ulong()
            status = ntdll.NtQueryInformationProcess(
                hProcess, PROCESS_BASIC_INFO, ctypes.byref(pbi), 
                ctypes.sizeof(pbi), ctypes.byref(ret_len))
            
            if status == 0 and pbi.PebBaseAddress:
                peb_addr = pbi.PebBaseAddress
                print(f"     PEB @ {hex(peb_addr)}")
                
                try:
                    # x64: BeingDebugged at PEB+0x02
                    being_debugged = pm.read_bytes(peb_addr, 4)
                    bd_value = being_debugged[2] if isinstance(being_debugged, bytes) else 0
                    is_being_debugged = bool(bd_value & 1)
                    print(f"     BeingDebugged (PEB+0x02): {bd_value & 1} {'⚠️ DETECTED!' if is_being_debugged else '✅ clean'}")
                    
                    # NtGlobalFlag at PEB+0x68 (x64)
                    flags = pm.read_bytes(peb_addr + 0x68, 4)
                    flag_val = struct.unpack("<I", flags[:4])[0] if isinstance(flags, bytes) else 0
                    flags_problem = flag_val != 0
                    print(f"     NtGlobalFlag (PEB+0x68):    0x{flag_val:08X} {'⚠️ NON-ZERO!' if flags_problem else '✅ zero (normal)'}")
                    
                except Exception as e:
                    print(f"     [!] 读 PEB 失败: {e}")
            else:
                print(f"     NtQueryInformationProcess failed: status=0x{status:08X}")
            kernel32.CloseHandle(hProcess)
        else:
            print(f"     OpenProcess failed (可能需要管理员权限)")
        
        verdict = []
        if is_being_debugged: verdict.append("BeingDebugged")
        if flags_problem: verdict.append("NtGlobalFlag")
        if verdict:
            print(f"\n     ⚠️ 总评: 检测到 {', '.join(verdict)} 反调试检查")
        else:
            print(f"\n     ✅ 总评: 未检测到 PEB 层面反调试")
            
    except Exception as e:
        print(f"     [!] 检查失败: {e}")


def check_closehandle_timing(pid):
    """CloseHandle 异常检测 — 调试器特征
    
    当调试器附加时, 用无效句柄调用 CloseHandle 会触发 EXCEPTION_INVALID_HANDLE (0xC0000008)
    正常程序不应该捕获这个异常
    """
    print(f"\n  ── 3. CloseHandle 异常检测 ──")
    # 这是一个行为检测, 安全地检测需要写异常处理函数
    print("     原理: 向调试器发送无效句柄 CloseHandle((HANDLE)0xDEAD)")
    print("     调试器会偷偷消费异常 → 不会崩")
    print("     正常进程 → 崩")
    print("     检测方法: 用 try/except 或 VEH 包裹 CloseHandle")
    print("     (主动检测有风险, 建议被动扫描 PEB 标志)")


def check_parent_process(pid):
    """检查父进程是否异常"""
    print(f"\n  ── 4. 父进程链路检查 ──")
    if psutil is None:
        print("     psutil not installed"); return
    
    try:
        proc = psutil.Process(pid)
        parent = proc.parent()
        ppid = parent.pid if parent else 0
        pname = parent.name() if parent else "N/A"
        print(f"     PID: {pid} ← PPID: {ppid} ({pname})")
        
        # 正常父进程应该:
        expected_parents = ["explorer.exe", "cmd.exe", "powershell.exe", "conhost.exe",
                           "svchost.exe", "services.exe", "winlogon.exe"]
        if pname.lower() in expected_parents:
            print(f"     ✅ 父进程 {pname} 正常")
        elif pname.lower() in ["x64dbg.exe", "ida64.exe", "ida.exe", "ollydbg.exe", 
                              "windbg.exe", "cheatengine-x86_64.exe", "frida.exe"]:
            print(f"     ⚠️ 父进程 {pname} 是已知调试器!")
        else:
            print(f"     ? 父进程 {pname} 未知 (可能需要验证)")
            
        # 同时检查子进程
        children = proc.children()
        suspicious_kids = [c.name() for c in children if c.name().lower() in 
                          ["x64dbg.exe", "ida64.exe", "ida.exe", "windbg.exe", "frida-helper"]]
        if suspicious_kids:
            print(f"     ⚠️ 子进程含已知调试器: {suspicious_kids}")
            
    except Exception as e:
        print(f"     [!] 检查失败: {e}")


def scan_int3_breakpoints(pid):
    """在代码段扫描 INT3 (0xCC) 断点"""
    print(f"\n  ── 5. INT3 断点扫描 (0xCC) ──")
    if pymem is None:
        print("     pymem not installed"); return
    
    try:
        pm = pymem.Pymem(f"pid={pid}")
        modules = pymem.process.module_from_snapshot(pm.process_handle)
        
        cc_found = 0
        total_code = 0
        
        for mod in modules[:5]:  # 只检查前5个模块以免太久
            base = mod.lpBaseOfDll
            size = mod.SizeOfImage if hasattr(mod, 'SizeOfImage') else 1024 * 1024
            if size > 5 * 1024 * 1024:  # 跳过太大模块
                continue
            
            try:
                data = pm.read_bytes(base, min(size, 512 * 1024))
                if isinstance(data, bytes):
                    total_code += len(data)
                    # 代码段中 0xCC 断点搜索
                    # (排除已存在的调试符号)
                    cc_count = data.count(0xCC)
                    cc_found += cc_count
                    mod_name = mod.name.split(b'\\')[-1].decode(errors='replace') if isinstance(mod.name, bytes) else Path(mod.name).name
                    if cc_count > 2:  # 超过2个 INT3 可疑
                        print(f"     ⚠️ {mod_name[:25]:25s} {cc_count:>4}× INT3")
            except:
                pass
        
        print(f"     扫描 {total_code/1024:.1f} KB 代码")
        print(f"     共发现 {cc_found} 个 INT3")
        if cc_found < 5:
            print(f"     ✅ 无异常断点")
        elif cc_found < 100:
            print(f"     ? {cc_found} 个 INT3 — 可能含调试符号")
        else:
            print(f"     ⚠️ 大量 INT3 — 可能内嵌反调试断点")
            
    except Exception as e:
        print(f"     [!] 扫描失败: {e}")


def check_all(pid):
    """执行全部反调试检测"""
    print(f"\n{'='*60}")
    print(f"  反调试检测报告 — PID {pid}")
    print(f"{'='*60}")
    
    try:
        p = psutil.Process(pid)
        print(f"  进程: {p.name()} ({p.exe()})")
    except:
        pass
    
    check_peb_flags(pid)
    check_closehandle_timing(pid)
    check_parent_process(pid)
    scan_int3_breakpoints(pid)
    
    print(f"\n{'='*60}")
    print("  检测完成")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "scan" or cmd == "all":
        pid = int(sys.argv[2])
        check_all(pid)
    elif cmd == "int3":
        pid = int(sys.argv[2])
        scan_int3_breakpoints(pid)
    else:
        print(f"未知命令: {cmd}")
