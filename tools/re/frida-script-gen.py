#!/usr/bin/env python3
"""Frida 脚本生成器 — 从自然语言描述生成 Frida JS 脚本

用法:
  python frida-script-gen.py hook <function>     # Hook 函数
  python frida-script-gen.py trace <module>       # Trace 模块
  python frida-script-gen.py dump <pid>           # Dump 内存
  python frida-script-gen.py list                 # 列出模板
"""
import sys

TEMPLATES = {
    "hook-args": """// Hook {target} — 记录参数和返回值
if ({{typeof {target} !== 'undefined'}}) {{
    Interceptor.attach({target}.address, {{
        onEnter: function(args) {{
            console.log(`[{target}] called`);
            for(var i=0; i<{argc}; i++) {{
                try {{ console.log(`  arg[{i}] = ${{args[i]}}`); }} catch(e) {{}}
            }}
        }},
        onLeave: function(retval) {{
            console.log(`[{target}] -> ${{retval}}`);
        }}
    }});
    console.log('[+] Hooked: {target}');
}} else {{
    console.log('[-] Cannot find: {target}');
}}""",
    "trace-api": """// Trace all calls to {module}
var modules = Process.enumerateModules();
var mod = modules.find(m => m.name === '{module}');
if (mod) {{
    var exports = Module.enumerateExports('{module}');
    console.log(`[*] {module} has ${{exports.length}} exports`);
    exports.slice(0, {limit}).forEach(function(exp) {{
        if (exp.type === 'function') {{
            Interceptor.attach(exp.address, {{
                onEnter: function(args) {{
                    console.log(`[API] ${{exp.name}}()`);
                }}
            }});
        }}
    }});
    console.log(`[+] Hooked ${{Math.min(exports.length, {limit})}} functions`);
}}""",
    "dump-mem": """// Dump memory regions matching pattern
Process.enumerateRanges('{{protection}}').forEach(function(range) {{
    console.log(`Range: ${{range.base}}-${range.size} prot=${{range.protection}}`);
    try {{
        var buf = Memory.readByteArray(range.base, Math.min(range.size, 4096));
        console.log(hexdump(buf, {{offset: 0, length: 256, header: true, ansi: true}}));
    }} catch(e) {{}}
}});""",
    "bypass-debug": """// Bypass anti-debug checks
// Trace PEB->BeingDebugged
var peb = Process.getModuleByName('ntdll.dll');
var NtQueryInfoProc = Module.findExportByName('ntdll.dll', 'NtQueryInformationProcess');
if (NtQueryInfoProc) {{
    Interceptor.attach(NtQueryInfoProc, {{
        onEnter: function(args) {{
            this.pid = args[1]; // ProcessInformationClass
            if (this.pid.toInt32() === 7) {{ // ProcessDebugPort
                console.log('[!] Blocked anti-debug check (ProcessDebugPort)');
                args[1] = ptr(0); // NOP
            }}
        }}
    }});
    console.log('[+] NtQueryInformationProcess hooked');
}}
""",
}

def gen_hook(target, argc=4):
    return TEMPLATES["hook-args"].format(target=target, argc=argc)

def gen_trace(module, limit=10):
    return TEMPLATES["trace-api"].format(module=module, limit=limit)

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "list":
        print("可用模板:")
        for k, v in TEMPLATES.items():
            print(f"  {k:<15s} {v.split(chr(10))[0].strip('/ ')[:50]}")
        print("\n快捷生成:")
        print("  frida-script-gen.py hook <func> [argc]")
        print("  frida-script-gen.py trace <module> [limit]")
        print("  frida-script-gen.py dump <protection>")
        print("  frida-script-gen.py bypass-debug")
        return
    if cmd == "hook":
        target = sys.argv[2] if len(sys.argv) > 2 else input("Function name: ")
        argc = int(sys.argv[3]) if len(sys.argv) > 3 else 4
        print(gen_hook(target, argc))
    elif cmd == "trace":
        mod = sys.argv[2] if len(sys.argv) > 2 else input("Module name: ")
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        print(gen_trace(mod, limit))
    elif cmd == "dump":
        prot = sys.argv[2] if len(sys.argv) > 2 else "rwx"
        print(TEMPLATES["dump-mem"].format(protection=prot))
    elif cmd == "bypass-debug":
        print(TEMPLATES["bypass-debug"])
    elif cmd in TEMPLATES:
        print(TEMPLATES[cmd])
    else:
        print(f"未知命令: {cmd}")

if __name__ == "__main__":
    main()
