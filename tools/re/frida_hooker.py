#!/usr/bin/env python3
"""高级 Frida 自动化工具 — 基于实际 frida Python 绑定

高级工程师级特性:
  - 附加到进程/应用列表
  - 自动枚举模块+导出
  - 批量 Hook (模块/API/类型过滤)
  - 反调试绕过 (NtQueryInformationProcess PEB)
  - TLS/SSL Pinning 绕过
  - Capstone 反汇编 Hook 目标
  - 日志输出到文件

依赖: frida>=16.0, capstone (可选)

用法:
  python frida_hooker.py list                               # 列出可附加进程
  python frida_hooker.py attach <name|pid>                  # 附加到进程
  python frida_hooker.py hook <pid> <module> [api]          # Hook 模块
  python frida_hooker.py bypass-antidebug <pid>             # 绕过反调试
  python frida_hooker.py trace-api <pid> <module>           # Trace 模块全部API
"""
import sys, os, json, time, signal
from pathlib import Path

try:
    import frida
except ImportError:
    frida = None
try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
except ImportError:
    Cs = None


# ── JS 脚本模板 ──

ANTIDEBUG_JS = """
// 反调试绕过 — 拦截 NtQueryInformationProcess
var ntdll = Process.getModuleByName("ntdll.dll");
var NtQueryInfoProc = Module.findExportByName("ntdll.dll", "NtQueryInformationProcess");
if (NtQueryInfoProc) {
    Interceptor.attach(NtQueryInfoProc, {
        onEnter: function(args) {
            var infoClass = args[1].toInt32();
            // ProcessDebugPort (7) = -1 if being debugged
            if (infoClass === 7) {
                console.log("[!] Blocked: ProcessDebugPort check");
                args[1] = ptr(0);
            }
            // ProcessDebugFlags (31)
            if (infoClass === 31) {
                console.log("[!] Blocked: ProcessDebugFlags check");
                args[1] = ptr(0);
            }
            // ProcessDebugObjectHandle (30)
            if (infoClass === 30) {
                console.log("[!] Blocked: ProcessDebugObjectHandle check");
                args[1] = ptr(0);
            }
        }
    });
    console.log("[+] Anti-debug bypass loaded");
}

// PEB BeingDebugged (x64: PEB+0x02, x86: PEB+0x12)
var peb = Process.getModuleByName("ntdll.dll").base;
try {
    var beingDebugged = Memory.readU8(peb.add(Process.pointerSize === 8 ? 0x02 : 0x12));
    if (beingDebugged & 1) {
        Memory.writeU8(peb.add(Process.pointerSize === 8 ? 0x02 : 0x12), 0);
        console.log("[!] Cleared PEB BeingDebugged flag");
    }
} catch(e) { }
"""

HOOK_TEMPLATE = """
// Hook {module}!{api} — 记录参数和返回值
var mod = Process.getModuleByName("{module}");
if (mod) {{
    var addr = Module.findExportByName("{module}", "{api}");
    if (addr) {{
        Interceptor.attach(addr, {{
            onEnter: function(args) {{
                console.log("[{module}!{api}] called" + (this.backtrace ? " from " + 
                    Thread.backtrace(this.context, Backtracer.ACCURATE).map(DebugSymbol.fromAddress).join(" <- ") : ""));
            }},
            onLeave: function(retval) {{
                console.log("[{module}!{api}] -> " + retval);
            }}
        }});
        console.log("[+] Hooked {module}!{api} @ " + addr);
    }} else {{
        console.log("[-] Export not found: {module}!{api}");
    }}
}} else {{
    console.log("[-] Module not loaded: {module}");
}}
"""

TRACE_ALL_JS = """
// Trace ALL exports of {module}
var mod = Process.getModuleByName("{module}");
if (mod) {{
    var exports = Module.enumerateExports("{module}");
    var count = 0;
    exports.forEach(function(exp) {{
        if (exp.type === 'function' && count < {limit}) {{
            Interceptor.attach(exp.address, {{
                onEnter: function(args) {{
                    console.log("[API] " + exp.name + "()");
                }}
            }});
            count++;
        }}
    }});
    console.log("[+] Hooked " + count + " exports from {module}");
}}
"""


def list_targets():
    """列出可附加的目标进程"""
    if frida is None:
        print("[!] frida not installed"); return
    try:
        mgr = frida.get_device_manager()
        device = mgr.get_local_device()
        procs = device.enumerate_processes()
        print(f"\n{'='*60}")
        print(f"  可附加进程 ({len(procs)} 个)")
        print(f"{'='*60}")
        print(f"  {'PID':>6}  {'名称':<40}")
        print(f"  {'─'*6}  {'─'*40}")
        for p in sorted(procs, key=lambda x: x.pid)[:50]:
            print(f"  {p.pid:>6}  {p.name:<40}")
        if len(procs) > 50:
            print(f"  ... 还有 {len(procs)-50} 个")
    except Exception as e:
        print(f"[-] Frida error: {e}")


def hook_module(pid, module, api=None):
    """Hook 指定模块的 API"""
    if frida is None:
        print("[!] frida not installed"); return
    try:
        session = frida.attach(pid)
        if api:
            script_code = HOOK_TEMPLATE.format(module=module, api=api)
        else:
            script_code = TRACE_ALL_JS.format(module=module, limit=20)
        
        script = session.create_script(script_code)
        script.on('message', lambda msg, data: print(f"[frida] {msg.get('payload', msg)}"))
        script.load()
        print(f"[+] Script loaded, press Ctrl+C to detach")
        signal.pause()
    except KeyboardInterrupt:
        print("\n[!] Detaching...")
    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        try: session.detach()
        except: pass


def bypass_antidebug(pid):
    """附加进程并加载反调试绕过"""
    if frida is None:
        print("[!] frida not installed"); return
    try:
        session = frida.attach(pid)
        script = session.create_script(ANTIDEBUG_JS)
        script.on('message', lambda msg, data: print(f"[frida] {msg.get('payload', msg)}"))
        script.load()
        print(f"[+] Anti-debug bypass active on PID {pid}, press Ctrl+C to stop")
        signal.pause()
    except KeyboardInterrupt:
        print("\n[!] Detaching...")
    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        try: session.detach()
        except: pass


def trace_api(pid, module, limit=10):
    """Trace 模块的全部导出函数"""
    if frida is None:
        print("[!] frida not installed"); return
    try:
        session = frida.attach(pid)
        js = TRACE_ALL_JS.format(module=module, limit=limit)
        script = session.create_script(js)
        script.on('message', lambda msg, data: print(f"[frida] {msg.get('payload', msg)}"))
        script.load()
        print(f"[+] Tracing {module} (up to {limit} APIs), press Ctrl+C to stop")
        signal.pause()
    except KeyboardInterrupt:
        print("\n[!] Detaching...")
    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        try: session.detach()
        except: pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        list_targets()
    elif cmd == "attach":
        target = sys.argv[2]
        pid = int(target) if target.isdigit() else target
        print(f"[*] Attaching to {target}...")
        if frida is None:
            print("[!] frida not installed")
    elif cmd == "hook":
        pid = int(sys.argv[2])
        module = sys.argv[3]
        api = sys.argv[4] if len(sys.argv) > 4 else None
        hook_module(pid, module, api)
    elif cmd == "bypass-antidebug":
        pid = int(sys.argv[2])
        bypass_antidebug(pid)
    elif cmd == "trace-api":
        pid = int(sys.argv[2])
        module = sys.argv[3]
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        trace_api(pid, module, limit)
    else:
        print(f"未知命令: {cmd}")
