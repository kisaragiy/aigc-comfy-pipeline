#!/usr/bin/env python3
"""Quick VLM refill for remaining empty frames"""
import json, time, os, base64, subprocess, re, glob, sys

KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
WORK = r'C:\Users\zwq\aigc-comfy-pipeline'
os.chdir(WORK)

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

# Files still needing refill
NEED = [
    'BV15v4y1A7B5', 'BV1aL4y1T7CE', 'BV1bQ4y1E77q',
    'BV1Hs411H74o', 'BV1kt411Q7xt',
]

def read_md(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()

def write_md(path, content):
    with open(path,'w',encoding='utf-8') as f: f.write(content)

def get_info(bv):
    import requests as req
    s = req.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
    d = s.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}', timeout=15).json()
    if d.get('code')!=0: return None
    return d['data']

def download(bv, cid):
    import requests as req
    s = req.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
    d = s.get(f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={cid}&qn=16&platform=html5&high_quality=1', timeout=15).json()
    if not d.get('data',{}).get('durl'): return None
    vurl = d['data']['durl'][0]['url']
    out = f'rf_{bv}.mp4'
    subprocess.run(['curl','-L','--noproxy','*','--max-time','120','-H','User-Agent: Mozilla/5.0','-o',out,vurl], capture_output=True, timeout=130)
    return out if os.path.exists(out) and os.path.getsize(out)>10000 else None

log('='*40)
log(f'Final VLM refill: {len(NEED)} files')
log('='*40)

for bv in NEED:
    # Find matching md file
    matches = glob.glob(os.path.join(KBASE, f'{bv}_*.md'))
    if not matches:
        log(f'  ⏭️ {bv}: no md found'); continue
    md_path = matches[0]
    
    content = read_md(md_path)
    # Check if there are still empty frames
    empty_frames = 0
    for line in content.split('\n'):
        if line.startswith('|') and '|  |' in line:
            empty_frames += 1
    
    if empty_frames == 0:
        log(f'  ✅ {bv}: already complete'); continue
    
    log(f'  ▶️ {bv} ({empty_frames} empty frames)')
    
    info = get_info(bv)
    if not info: log(f'  ❌ API fail'); continue
    
    video = download(bv, info.get('cid',0))
    if not video: log(f'  ❌ download fail'); continue
    
    # Extract frames (no sampling - take exactly the ones that are empty)
    fdir = video.replace('.mp4','_f')
    if os.path.exists(fdir):
        import shutil; shutil.rmtree(fdir)
    os.makedirs(fdir)
    subprocess.run(['ffmpeg','-i',video,'-vf','fps=1/2','-q:v','2','-y',f'{fdir}/f_%04d.jpg'], capture_output=True, timeout=120)
    
    frames = sorted([f for f in os.listdir(fdir) if f.endswith('.jpg')])
    log(f'  ✅ {len(frames)} frames extracted')
    
    # VLM analyze up to 30 frames
    results = {}
    for fn in frames[:30]:
        fpath = os.path.join(fdir, fn)
        with open(fpath,'rb') as f: b64 = base64.b64encode(f.read()).decode()
        payload = {"model":"qwen3-vl","stream":False,"prompt":"描述封印者动画截图：人物/服装/场景/色调、画面文字。≤20字。","images":[b64],"options":{"temperature":0.1}}
        
        # Write payload to file to avoid Windows cmdline length limit
        pfile = fpath + '.pl.json'
        with open(pfile, 'w') as f:
            json.dump(payload, f)
        
        r = subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
            'http://localhost:11434/api/generate','-H','Content-Type: application/json',
            '-d', f'@{pfile}'],
            capture_output=True, text=True, timeout=65)
        try: os.remove(pfile)
        except: pass
        try:
            resp = json.loads(r.stdout).get('response','')
        except:
            resp = ''
        
        sec = (int(re.search(r'(\d+)',fn).group(1))-1)*2
        results[sec] = resp
        log(f'    {fn} ({sec}s): {resp[:40]}')
    
    # Update md: replace empty frame lines
    new_lines = []
    for line in content.split('\n'):
        if line.startswith('|') and '|  |' in line:
            # Find matching time
            match = re.match(r'^\| (\d{2}:\d{2}) \|', line)
            if match:
                time_key = match.group(1)
                parts = time_key.split(':')
                sec = int(parts[0])*60 + int(parts[1])
                if sec in results and results[sec]:
                    line = f'| {time_key} | {results[sec]} |'
        new_lines.append(line)
    
    write_md(md_path, '\n'.join(new_lines))
    log(f'  ✅ updated: {os.path.basename(md_path)}')
    
    os.remove(video)
    import shutil; shutil.rmtree(fdir)
    time.sleep(1)

log('✅ Done')
