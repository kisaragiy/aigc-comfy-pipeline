#!/usr/bin/env python3
"""Final VLM refill v2 - using terminal grep to find files, then Python VLM"""
import json, time, os, base64, subprocess, re, sys

KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
WORK = r'C:\Users\zwq\aigc-comfy-pipeline'
os.chdir(WORK)

BV_LIST = ['BV15b4y1G7hm','BV16E411W7Uf','BV1nC4y1q7EH','BV1UC4y1K7EK']

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

def get_info(bv):
    import requests as req
    s = req.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
    d = s.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}', timeout=15).json()
    return d['data'] if d.get('code')==0 else None

log('='*40)
log(f'Final refill v2: {len(BV_LIST)} files')
log('='*40)

for bv in BV_LIST:
    import glob
    matches = glob.glob(os.path.join(KBASE, f'{bv}_*.md'))
    if not matches: log(f'  ⏭️ {bv}: not found'); continue
    md_path = matches[0]
    
    log(f'  ▶️ {bv}')
    info = get_info(bv)
    if not info: log(f'  ❌ API fail'); continue
    
    video = None
    for attempt in range(3):
        try:
            s = __import__('requests').Session()
            s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
            d = s.get(f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={info["cid"]}&qn=16&platform=html5&high_quality=1', timeout=15).json()
            vurl = d['data']['durl'][0]['url']
            out = f'rf2_{bv}.mp4'
            subprocess.run(['curl','-L','--noproxy','*','--max-time','120','-H','User-Agent: Mozilla/5.0','-o',out,vurl], capture_output=True, timeout=130)
            if os.path.exists(out) and os.path.getsize(out)>10000: video=out; break
        except Exception as e: log(f'  ⚠️ attempt {attempt+1}: {e}'); time.sleep(2)
    
    if not video: log(f'  ❌ download fail'); continue
    log(f'  ✅ download OK')
    
    fdir = video.replace('.mp4','_f')
    if os.path.exists(fdir): __import__('shutil').rmtree(fdir)
    os.makedirs(fdir)
    subprocess.run(['ffmpeg','-i',video,'-vf','fps=1/2','-q:v','2','-y',f'{fdir}/f_%04d.jpg'], capture_output=True, timeout=120)
    frames = sorted([f for f in os.listdir(fdir) if f.endswith('.jpg')])
    log(f'  ✅ {len(frames)} frames')
    
    results = {}
    for fn in frames[:30]:
        fpath = os.path.join(fdir, fn)
        with open(fpath,'rb') as f: b64 = base64.b64encode(f.read()).decode()
        payload = {"model":"qwen3-vl","stream":False,"prompt":"描述封印者动画截图：人物/服装/场景/色调、画面文字。≤20字。","images":[b64],"options":{"temperature":0.1}}
        pfile = fpath+'.p.json'
        with open(pfile,'w') as f: json.dump(payload, f)
        
        r = subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
            'http://localhost:11434/api/generate','-H','Content-Type: application/json','-d',f'@{pfile}'],
            capture_output=True, text=True, timeout=65)
        try: os.remove(pfile)
        except: pass
        try: resp = json.loads(r.stdout).get('response','')
        except: resp = ''
        
        sec = (int(re.search(r'(\d+)',fn).group(1))-1)*2
        results[sec] = resp
        log(f'    {fn} ({sec}s): {resp[:40]}')
    
    # Update md
    with open(md_path,'r',encoding='utf-8') as f: content = f.read()
    new_lines = []
    for line in content.split('\n'):
        if line.startswith('|') and '|  |' in line:
            m = re.match(r'^\| (\d{2}:\d{2}) \|', line)
            if m:
                parts = m.group(1).split(':')
                sec = int(parts[0])*60 + int(parts[1])
                if sec in results and results[sec]:
                    line = f'| {m.group(1)} | {results[sec]} |'
        new_lines.append(line)
    with open(md_path,'w',encoding='utf-8') as f: f.write('\n'.join(new_lines))
    log(f'  ✅ updated')
    
    os.remove(video)
    __import__('shutil').rmtree(fdir)

log('✅ Done')
