#!/usr/bin/env python3
"""Final VLM refill v3 - fix remaining empty frames"""
import json, time, os, base64, subprocess, re, glob, requests

WORK = r'C:\Users\zwq\aigc-comfy-pipeline'
KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
os.chdir(WORK)
ses = requests.Session()
ses.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

# Find bv from md file path
def bv_from_path(p): return os.path.basename(p).split('_')[0]

# Find files with empty frames using bash: output is bv|total|empty
r = subprocess.run(['bash','-c','cd "'+KBASE+'" && for f in BV*.md; do [ "$f" = "index.md" ] && continue; t=$(grep -c "^| [0-9][0-9]:" "$f" 2>/dev/null); e=$(grep "^| [0-9][0-9]:" "$f" 2>/dev/null|grep -c "|  |$"); [ "$t" -gt 0 ] && [ "$e" -gt 0 ] && echo "$f|$t|$e"; done'], capture_output=True, text=True, timeout=10)

files_to_fix = []
for line in r.stdout.strip().split('\n'):
    line = line.strip()
    if not line: continue
    parts = line.split('|')
    if len(parts) >= 3:
        fname = parts[0].strip()
        try:
            total = int(parts[1])
            empty = int(parts[2])
        except ValueError: continue
        bv = fname.split('_')[0]
        fpath = os.path.join(KBASE, fname)
        files_to_fix.append((bv, fpath, total, empty))

log(f"Files to fix: {len(files_to_fix)}")
for bv, fp, t, e in files_to_fix:
    log(f"  {bv} ({t}帧, {e}空)")

for bv, md_path, total, empty in files_to_fix:
    log(f'\n▶️ {bv} ({empty} empty)')
    
    info = ses.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}', timeout=15).json()
    if info.get('code') != 0: log('  ❌ API'); continue
    info = info['data']
    
    # Download
    d = ses.get(f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={info["cid"]}&qn=16&platform=html5&high_quality=1', timeout=15).json()
    vurl = d['data']['durl'][0]['url']
    video = f'fv_{bv}.mp4'
    subprocess.run(['curl','-L','--noproxy','*','--max-time','120','-H','User-Agent: Mozilla/5.0','-o',video,vurl], capture_output=True, timeout=130)
    if not os.path.exists(video) or os.path.getsize(video) < 10000: log('  ❌ DL'); continue
    
    # Extract frames
    fdir = video.replace('.mp4','_f')
    if os.path.exists(fdir): __import__('shutil').rmtree(fdir)
    os.makedirs(fdir)
    subprocess.run(['ffmpeg','-i',video,'-vf','fps=1/2','-q:v','2','-y',f'{fdir}/f_%04d.jpg'], capture_output=True, timeout=120)
    frames = sorted([f for f in os.listdir(fdir) if f.endswith('.jpg')])
    
    # VLM
    results = {}
    for fn in frames:
        sec = (int(re.search(r'(\d+)',fn).group(1))-1)*2
        fpath = os.path.join(fdir, fn)
        with open(fpath,'rb') as f: b64 = base64.b64encode(f.read()).decode()
        payload = {"model":"qwen3-vl","stream":False,"prompt":"描述截图：人物/服装/场景/色调/文字。≤20字。","images":[b64],"options":{"temperature":0.1}}
        pfile = fpath+'.p.json'
        with open(pfile,'w') as f: json.dump(payload, f)
        r = subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
            'http://localhost:11434/api/generate','-H','Content-Type: application/json','-d',f'@{pfile}'],
            capture_output=True, text=True, timeout=65)
        try: os.remove(pfile); os.remove(pfile)  # sometimes .pl.json
        except: pass
        try:
            resp = json.loads(r.stdout).get('response','')
            results[sec] = resp
            if resp: log(f'    {fn} ({sec}s): {resp[:30]}')
        except: pass
    
    # Update md: replace EMPTY frame lines
    with open(md_path,'rb') as f: raw = f.read()
    text = raw.decode('utf-8')
    new_text = text
    for sec, desc in results.items():
        if not desc: continue
        mm = f"{sec//60:02d}:{sec%60:02d}"
        old = f"| {mm} |  |"
        new = f"| {mm} | {desc} |"
        if old in new_text:
            new_text = new_text.replace(old, new, 1)
    
    if new_text != text:
        with open(md_path,'wb') as f: f.write(new_text.encode('utf-8'))
        log(f'  ✅ updated')
    
    # Cleanup
    os.remove(video)
    __import__('shutil').rmtree(fdir)

log('\n✅ All done!')
