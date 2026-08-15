#!/usr/bin/env python3
"""
Direct Syscall Memory Scanner — 绕过BlackCipher读取CW.EXE内存找AES密钥
"""
import ctypes, ctypes.wintypes, struct, os, time, zlib, base64
from ctypes import wintypes
from Crypto.Cipher import AES

# ── Windows API types ──
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
ntdll_disk = open(r'C:\Windows\System32\ntdll.dll', 'rb').read()

# ── Extract syscall numbers from disk ntdll ──
def get_syscall_number(func_name):
    """Extract syscall number from a ntdll function on DISK (unhooked)"""
    # Find function by searching for its name in the export table
    # Parse PE headers
    dos_hdr = struct.unpack_from('<H', ntdll_disk, 0)[0]
    if dos_hdr != 0x5A4D:  # MZ
        return None
    
    pe_off = struct.unpack_from('<I', ntdll_disk, 0x3C)[0]
    # Find export directory
    export_rva = struct.unpack_from('<I', ntdll_disk, pe_off + 0x18 + 0x70)[0]
    export_size = struct.unpack_from('<I', ntdll_disk, pe_off + 0x18 + 0x74)[0]
    
    # Convert RVA to file offset (find the right section)
    sections = []
    for i in range(96):  # max sections
        sec = pe_off + 0x18 + 0xF8 + i * 40
        name = ntdll_disk[sec:sec+8].rstrip(b'\x00').decode('ascii', errors='replace')
        vaddr = struct.unpack_from('<I', ntdll_disk, sec + 12)[0]
        vsize = struct.unpack_from('<I', ntdll_disk, sec + 8)[0]
        foffset = struct.unpack_from('<I', ntdll_disk, sec + 20)[0]
        sections.append((name, vaddr, vsize, foffset))
        if name == '.text':
            text_va, text_fo = vaddr, foffset
    
    def rva_to_offset(rva):
        for name, vaddr, vsize, foffset in sections:
            if vaddr <= rva < vaddr + vsize:
                return foffset + (rva - vaddr)
        return None
    
    # Parse export table
    exp_fo = rva_to_offset(export_rva)
    if not exp_fo:
        return None
    
    num_names = struct.unpack_from('<I', ntdll_disk, exp_fo + 0x18)[0]
    addr_of_functions = rva_to_offset(struct.unpack_from('<I', ntdll_disk, exp_fo + 0x1C)[0])
    addr_of_names = rva_to_offset(struct.unpack_from('<I', ntdll_disk, exp_fo + 0x20)[0])
    addr_of_ordinals = rva_to_offset(struct.unpack_from('<I', ntdll_disk, exp_fo + 0x24)[0])
    
    if not all([addr_of_functions, addr_of_names, addr_of_ordinals]):
        return None
    
    for i in range(num_names):
        name_fo = rva_to_offset(struct.unpack_from('<I', ntdll_disk, addr_of_names + i * 4)[0])
        if not name_fo:
            continue
        # Read the function name
        name_bytes = []
        pos = name_fo
        while ntdll_disk[pos:pos+1] != b'\x00':
            name_bytes.append(ntdll_disk[pos])
            pos += 1
        current_name = bytes(name_bytes).decode('ascii', errors='replace')
        
        if current_name == func_name:
            ordinal = struct.unpack_from('<H', ntdll_disk, addr_of_ordinals + i * 2)[0]
            func_rva = struct.unpack_from('<I', ntdll_disk, addr_of_functions + ordinal * 4)[0]
            func_fo = rva_to_offset(func_rva)
            if func_fo:
                # Read first 5 bytes: mov eax, SYSCALL# (B8 XX XX XX XX)
                if ntdll_disk[func_fo:func_fo+1] == b'\xb8':
                    syscall_num = struct.unpack_from('<I', ntdll_disk, func_fo + 1)[0]
                    return syscall_num
                # Alternative: stub starts with 4C 8B D1 (mov r10, rcx) then B8
                if ntdll_disk[func_fo:func_fo+3] == b'\x4c\x8b\xd1':
                    for j in range(3, 20):
                        if ntdll_disk[func_fo+j:func_fo+j+1] == b'\xb8':
                            syscall_num = struct.unpack_from('<I', ntdll_disk, func_fo + j + 1)[0]
                            return syscall_num
    return None

# ── Build syscall stubs ──
def make_stub(num):
    return b'\x4c\x8b\xd1' + b'\xb8' + struct.pack('<I', num) + b'\x0f\x05\xc3'

# Get syscall numbers
SC_NtOpenProcess = get_syscall_number('NtOpenProcess')
SC_NtReadVirtualMemory = get_syscall_number('NtReadVirtualMemory')
SC_NtClose = get_syscall_number('NtClose')

print(f'Syscall numbers: NtOpenProcess=0x{SC_NtOpenProcess:x}, NtReadVirtualMemory=0x{SC_NtReadVirtualMemory:x}, NtClose=0x{SC_NtClose:x}')

if not all([SC_NtOpenProcess, SC_NtReadVirtualMemory, SC_NtClose]):
    print('❌ Failed to get syscall numbers')
    exit(1)

# Allocate executable memory for stubs
stub_open = make_stub(SC_NtOpenProcess)
stub_read = make_stub(SC_NtReadVirtualMemory)
stub_close = make_stub(SC_NtClose)

STUB_SIZE = max(len(stub_open), len(stub_read), len(stub_close))
code = stub_open + stub_read + stub_close

k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]

exec_mem = k32.VirtualAlloc(None, len(code), 0x1000, 0x40)  # MEM_COMMIT | PAGE_EXECUTE_READWRITE
if not exec_mem:
    print('❌ VirtualAlloc failed')
    exit(1)

# Copy stubs to executable memory
ctypes.memmove(exec_mem, code, len(code))

# Calculate stub addresses
addr_NtOpenProcess = exec_mem
addr_NtReadVirtualMemory = exec_mem + len(stub_open)
addr_NtClose = exec_mem + len(stub_open) + len(stub_read)

# Create function prototypes
NTSTATUS = wintypes.DWORD
HANDLE = ctypes.c_void_p

# NtOpenProcess
k32_func = ctypes.CFUNCTYPE(NTSTATUS, ctypes.POINTER(HANDLE), wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p)
NT_OpenProcess = k32_func(addr_NtOpenProcess)

# NtReadVirtualMemory
k32_func2 = ctypes.CFUNCTYPE(NTSTATUS, HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
NT_ReadVirtualMemory = k32_func2(addr_NtReadVirtualMemory)

# NtClose
k32_func3 = ctypes.CFUNCTYPE(NTSTATUS, HANDLE)
NT_Close = k32_func3(addr_NtClose)

# ── Scan CW.EXE ──
PID = 37856  # CW.EXE PID from earlier

hProcess = HANDLE(0)
client_id = (ctypes.c_ulonglong * 2)(PID, 0)  # UniqueProcess = PID
oa_buf = ctypes.create_string_buffer(24)  # sizeof(OBJECT_ATTRIBUTES) = 24
# Initialize OBJECT_ATTRIBUTES with zeros (no inheritance, no name)
struct.pack_into('<IHHP', oa_buf, 0, 24, 0, 0, 0)  # Length, RootDirectory, ObjectName, Attributes

status = NT_OpenProcess(ctypes.byref(hProcess), 0x1F0FFF, ctypes.byref(oa_buf), ctypes.byref(client_id))
print(f'NtOpenProcess status: 0x{status:08x}')

if status != 0 or not hProcess:
    print(f'❌ Cannot open process (status=0x{status:08x})')
    exit(1)

print(f'✅ Opened PID {PID}')

# ── Search for AES keys ──
SAMPLE_FILE = r'D:\TCGAME\TCGameApps\exacted\story\DLG_PVE_DUNGEON46.TET'
with open(SAMPLE_FILE, 'rb') as f:
    ENC_SAMPLE = f.read()

def test_key_candidate(key_bytes):
    """Test if a 32-byte key can decrypt the sample"""
    if len(key_bytes) != 32:
        return False
    for mode, iv in [(AES.MODE_CBC, b'\x00' * 16), (AES.MODE_ECB, None)]:
        try:
            if mode == AES.MODE_ECB:
                dec = AES.new(key_bytes, mode).decrypt(ENC_SAMPLE)
            else:
                dec = AES.new(key_bytes, mode, iv=iv).decrypt(ENC_SAMPLE)
            # Check for high entropy or structure
            if sum(32 <= b < 127 for b in dec[:32]) > 20:
                return True, dec[:64]
        except:
            pass
    return False, None

print(f'Scanning memory for AES-256 keys...')
found_keys = []
buf_size = 65536
buf = ctypes.create_string_buffer(buf_size)
mbi_buf = ctypes.create_string_buffer(48)  # sizeof(MEMORY_BASIC_INFORMATION) = 48
bytes_read = ctypes.c_size_t(0)

addr = 0
scanned = 0
while addr < 0x7FFFFFFF0000:
    # VirtualQueryEx via direct syscall
    status = NT_ReadVirtualMemory(hProcess, ctypes.c_void_p(addr), mbi_buf, 48, ctypes.byref(bytes_read))
    if status != 0:
        addr += 0x10000
        continue
    
    # Parse MBI
    mbi = struct.unpack_from('<QQIIQIII', mbi_buf, 0)
    base_addr, region_size, state, protect = mbi[0], mbi[4], mbi[5], mbi[6]
    
    if state == 0x1000 and (protect & 0x02 or protect & 0x04):  # MEM_COMMIT and PAGE_READWRITE or PAGE_READWRITE
        to_read = min(region_size, buf_size)
        status = NT_ReadVirtualMemory(hProcess, ctypes.c_void_p(base_addr), buf, to_read, ctypes.byref(bytes_read))
        if status == 0 and bytes_read.value > 32:
            data = buf[:bytes_read.value]
            # Search for 32-byte high-entropy blocks (AES key candidate)
            for i in range(0, len(data) - 32, 8):
                chunk = data[i:i+32]
                if len(set(chunk)) >= 28:  # High entropy
                    result, sample = test_key_candidate(chunk)
                    if result:
                        hex_key = chunk.hex()
                        if hex_key not in [k[0] for k in found_keys]:
                            found_keys.append((hex_key, sample, base_addr + i))
                            print(f'  ✅ FOUND KEY: {hex_key}')
                            print(f'     Sample: {sample[:48]}')
    
    scanned += 1
    if scanned % 1000 == 0:
        print(f'  Scanned: {addr // (1024*1024)} MB, keys found: {len(found_keys)}')
    
    addr = base_addr + region_size

print(f'\nScan complete. Found {len(found_keys)} key candidates')
for hex_key, sample, addr in found_keys:
    print(f'  @ 0x{addr:x}: {hex_key}')
    # Save key
    with open(r'D:\TCGAME\TCGameApps\exacted\aes_key_runtime.txt', 'w') as f:
        f.write(hex_key)
    print(f'  ✅ Saved to aes_key_runtime.txt')

NT_Close(hProcess)
k32.VirtualFree(exec_mem, 0, 0x8000)
print('Done')
