#!/usr/bin/env python3
"""Fix museum interlude - using file-based curl payload to avoid Windows cmdline limit"""
import json, time, os, base64, subprocess, re, requests, shutil

KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
bv = 'BV1bQ4y1E77q'
WORK = r'C:\Users\zwq\aigc-comfy-pipeline'
os.chdir(WORK)

# Find the md file
md_file = [f for f in os.listdir(KBASE) if f.startswith(bv+'_')][0]
md_path = os.path.join(KBASE, md_file)

# 1. Get video
ses = requests.Session()
ses.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
info = ses.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}', timeout=15).json()['data']
d = ses.get(f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={info["cid"]}&qn=16&platform=html5&high_quality=1', timeout=15).json()
subprocess.run(['curl','-L','--noproxy','*','--max-time','120','-H','User-Agent: Mozilla/5.0','-o','fx_museum.mp4', d['data']['durl'][0]['url']], capture_output=True, timeout=130)

# 2. Extract frames
if os.path.exists('fx_museum_f'): shutil.rmtree('fx_museum_f')
os.makedirs('fx_museum_f')
subprocess.run(['ffmpeg','-i','fx_museum.mp4','-vf','fps=1/2','-q:v','2','-y','fx_museum_f/f_%04d.jpg'], capture_output=True, timeout=120)
frames = sorted([f for f in os.listdir('fx_museum_f') if f.endswith('.jpg')])
print(f'Frames: {len(frames)}')

# 3. VLM using FILE-BASED payload (bypasses Windows cmdline limit)
results = {}
for fn in frames:
    fp = os.path.join('fx_museum_f', fn)
    sec = (int(re.search(r'(\d+)',fn).group(1))-1)*2
    with open(fp,'rb') as f: b64 = base64.b64encode(f.read()).decode()
    
    # Write payload to temp file
    payload = {"model":"qwen3-vl","stream":False,"prompt":"描述截图：人物/场景/色调/文字。≤15字。","images":[b64],"options":{"temperature":0.1}}
    pfile = fp + '.pl.json'
    with open(pfile, 'w') as f: json.dump(payload, f)
    
    # Curl using @file syntax
    r = subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
        'http://localhost:11434/api/generate','-H','Content-Type: application/json',
        '-d', f'@{pfile}'], capture_output=True, text=True, timeout=65)
    
    try: os.remove(pfile)
    except: pass
    try: resp = json.loads(r.stdout).get('response','')
    except: resp = ''
    results[sec] = resp
    if resp: print(f'  {sec}s: {resp[:40]}')

# 4. Update md
with open(md_path,'rb') as f: raw = f.read()
text = raw.decode('utf-8')
for sec, desc in results.items():
    if not desc: continue
    mm = f'{sec//60:02d}:{sec%60:02d}'
    old = f'| {mm} |  |'
    if old in text:
        text = text.replace(old, f'| {mm} | {desc} |', 1)
        print(f'  ✅ {mm}: {desc[:30]}')

with open(md_path,'wb') as f: f.write(text.encode('utf-8'))
os.remove('fx_museum.mp4'); shutil.rmtree('fx_museum_f')
print('✅ Done')
