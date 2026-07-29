#!/usr/bin/env python3
"""API 监控工具 — 检测和解码常见 Windows API 调用模式

用法:
  python api-monitor.py strings <dll>      # 从 DLL 提取 API 名
  python api-monitor.py decode <api>       # 解码 API 参数模式
  python api-monitor.py pattern <api>      # 生成 Frida Hook 模式
"""
import sys

API_DB = {
    "CreateFileA": {"dll": "kernel32", "args": ["lpFileName", "dwDesiredAccess", "dwShareMode", "lpSecurityAttributes", "dwCreationDisposition", "dwFlagsAndAttributes", "hTemplateFile"], "desc": "打开/创建文件"},
    "ReadProcessMemory": {"dll": "kernel32", "args": ["hProcess", "lpBaseAddress", "lpBuffer", "nSize", "lpNumberOfBytesRead"], "desc": "读取进程内存"},
    "WriteProcessMemory": {"dll": "kernel32", "args": ["hProcess", "lpBaseAddress", "lpBuffer", "nSize", "lpNumberOfBytesWritten"], "desc": "写入进程内存"},
    "CreateRemoteThread": {"dll": "kernel32", "args": ["hProcess", "lpThreadAttributes", "dwStackSize", "lpStartAddress", "lpParameter", "dwCreationFlags", "lpThreadId"], "desc": "远程线程注入"},
    "VirtualAllocEx": {"dll": "kernel32", "args": ["hProcess", "lpAddress", "dwSize", "flAllocationType", "flProtect"], "desc": "远程内存分配"},
    "OpenProcess": {"dll": "kernel32", "args": ["dwDesiredAccess", "bInheritHandle", "dwProcessId"], "desc": "打开进程句柄"},
    "NtOpenProcess": {"dll": "ntdll", "args": ["ProcessHandle", "DesiredAccess", "ObjectAttributes", "ClientId"], "desc": "底层进程打开"},
    "NtQueryInformationProcess": {"dll": "ntdll", "args": ["ProcessHandle", "ProcessInformationClass", "ProcessInformation", "ProcessInformationLength", "ReturnLength"], "desc": "查询进程信息(含反调试)"},
    "GetProcAddress": {"dll": "kernel32", "args": ["hModule", "lpProcName"], "desc": "获取函数地址"},
    "LoadLibraryA": {"dll": "kernel32", "args": ["lpLibFileName"], "desc": "加载 DLL"},
}

def decode_api(name):
    api = API_DB.get(name)
    if not api:
        print(f"未知 API: {name}"); return
    print(f"🔍 {name} ({api['dll']}.dll)")
    print(f"   用途: {api['desc']}")
    print(f"   参数 ({len(api['args'])}):")
    for i, a in enumerate(api['args']):
        print(f"     [{i}] {a}")
    # Hook pattern
    print(f"\n🔧 Frida Hook:")
    print(f'Interceptor.attach(Module.findExportByName("{api["dll"]}.dll", "{name}"), {{')
    print(f"    onEnter: function(args) {{")
    for i, a in enumerate(api["args"][:4]):
        print(f"        console.log(`  {a} = ${{args[{i}]}}`);")
    print(f"    }}")
    print(f"}});")

def pattern_detect(api_list):
    """从 API 序列推断攻击模式"""
    suspicious = {
        "OpenProcess": "进程打开 — 可能尝试跨进程访问",
        "VirtualAllocEx": "远程内存分配 — 注入准备",
        "WriteProcessMemory": "内存写入 — 写 Shellcode",
        "CreateRemoteThread": "远程线程 — 注入执行",
        "ReadProcessMemory": "内存读取 — 数据窃取",
    }
    print("🔍 API 序列分析:")
    found = [a for a in api_list if a in suspicious]
    if not found:
        print("  未发现可疑 API")
    for api in found:
        print(f"  ⚠️ {api} — {suspicious[api]}")

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "strings":
        dll = sys.argv[2] if len(sys.argv) > 2 else "*"
        for name, info in sorted(API_DB.items()):
            if dll == "*" or dll.lower() in info["dll"]:
                print(f"  {name:<30s} {info['dll']:10s} {info['desc']}")
    elif cmd == "decode":
        api = sys.argv[2] if len(sys.argv) > 2 else input("API 名: ")
        decode_api(api)
    elif cmd == "pattern":
        apis = sys.argv[2:] if len(sys.argv) > 2 else ["OpenProcess", "VirtualAllocEx", "WriteProcessMemory", "CreateRemoteThread"]
        pattern_detect(apis)
    else:
        print(f"未知命令: {cmd}")

if __name__ == "__main__":
    main()
