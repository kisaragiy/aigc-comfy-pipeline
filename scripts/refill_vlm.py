#!/usr/bin/env python3
"""补跑VLM分析: 重新分析12个空帧视频, 原地更新md文件"""
import json, time, os, base64, subprocess, shutil, re, glob

WORK = r'C:\Users\zwq\aigc-comfy-pipeline'
KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
os.chdir(WORK)

# BV编号 → 查找对应md文件的helper
def find_md(bv):
    for f in glob.glob(os.path.join(KBASE, f'{bv}_*.md')):
        return f
    return None

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

def get_video_info(bv):
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
    url = f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={cid}&qn=16&platform=html5&high_quality=1'
    d = s.get(url, timeout=15).json()
    if not d.get('data',{}).get('durl'): return None
    vurl = d['data']['durl'][0]['url']
    out = f'rf_{bv}.mp4'
    subprocess.run(['curl','-L','--noproxy','*','--max-time','120','-H','User-Agent: Mozilla/5.0','-o',out,vurl], capture_output=True, timeout=130)
    return out if os.path.exists(out) and os.path.getsize(out)>10000 else None

def extract_frames(vpath):
    d = vpath.replace('.mp4','_f')
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)
    subprocess.run(['ffmpeg','-i',vpath,'-vf','fps=1/2','-q:v','2','-y',f'{d}/f_%04d.jpg'], capture_output=True, timeout=120)
    return sorted([f for f in os.listdir(d) if f.endswith('.jpg')]), d

def vlm_analyze(frame_path):
    with open(frame_path,'rb') as f: b64 = base64.b64encode(f.read()).decode()
    p = json.dumps({"model":"qwen3-vl","stream":False,"prompt":"描述封印者动画截图：人物/服装/场景/色调。≤20字。","images":[b64],"options":{"temperature":0.1}})
    pf = frame_path+'.p.json'
    with open(pf,'w') as f: f.write(p)
    r = subprocess.run(['curl','-s','--noproxy','*','--max-time','60','http://localhost:11434/api/generate','-H','Content-Type: application/json','-d',f'@{pf}'], capture_output=True, text=True, timeout=65)
    try: os.remove(pf)
    except: pass
    try: return json.loads(r.stdout).get('response','')
    except: return ''

def update_md(md_path, frame_results):
    """Read md, replace empty frames with VLM results"""
    with open(md_path,'r',encoding='utf-8') as f: content = f.read()
    
    # Build frame lookup: time_sec → description
    lookup = {}
    for sec, desc in frame_results:
        lookup[f'| {sec//60:02d}:{sec%60:02d} |'] = desc
    
    # Replace empty frame lines
    new_lines = []
    for line in content.split('\n'):
        if line.startswith('|') and '|  |' in line:
            # This is an empty frame - find its key
            key = line[:10]  # "| 00:00 |" approx
            for time_key, desc in lookup.items():
                if time_key in line:
                    line = line.rstrip()
                    if line.endswith('|'):
                        line = line[:-1] + desc + ' |'
                    break
        new_lines.append(line)
    
    with open(md_path,'w',encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

# BV list that need VLM re-run
REPAIR = [
    'BV1cx411h7nN', 'BV16x411h7VS',  # 角色剧情
    'BV1ei4y1X7Sk', 'BV1qb4y1e7Vz', 'BV1TF411p7ar',  # 采访
    'BV1qS4y1f7qQ', 'BV19q4y187D7', 'BV1Km4y1d74K',
    'BV11b4y1W7mD', 'BV1aL4y1T7CE', 'BV1Aa411v7YW', 'BV15v4y1A7B5',
    'BV1Hs411H74o', 'BV1kt411Q7xt', 'BV1bQ4y1E77q',  # 章节
]

# Also add missing ones
EXTRA = ['BV1wx411h7u4']  # 李世赫 (was done manually early, might need VLM too)

log('='*40)
log(f'补跑VLM: {len(REPAIR)} 个视频')
log('='*40)

# Warm VLM
subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
    'http://localhost:11434/api/generate','-H','Content-Type: application/json',
    '-d','{"model":"qwen3-vl","prompt":"warm","keep_alive":"30m"}'],
    capture_output=True, timeout=70)
log('VLM ready')

ok, fail, skip = 0, 0, 0
for bv in REPAIR:
    md_path = find_md(bv)
    if not md_path:
        log(f'  ⏭️ {bv}: md文件未找到'); skip+=1; continue
    
    log(f'▶️ {bv}')
    info = get_video_info(bv)
    if not info:
        log(f'  ❌ API失败'); fail+=1; continue
    
    log(f'  {info["title"][:50]} ({info["duration"]}s)')
    
    video = download(bv, info.get('cid',0))
    if not video:
        log(f'  ❌ 下载失败'); fail+=1; continue
    log(f'  ✅ 下载 ({os.path.getsize(video)//1024}KB)')
    
    frames, fdir = extract_frames(video)
    log(f'  ✅ {len(frames)}帧')
    
    log(f'  👁️ VLM分析...')
    results = []
    sample = sorted(set(frames[:30]))[:30]
    t0 = time.time()
    for fn in sample:
        r = vlm_analyze(os.path.join(fdir,fn))
        sec = (int(re.search(r'(\d+)',fn).group(1))-1)*2
        results.append((sec, r))
        log(f'    {fn}: {r[:30] if r else "(空)"}')
    log(f'  ✅ {len(results)}帧 in {time.time()-t0:.0f}s')
    
    update_md(md_path, results)
    log(f'  ✅ 更新: {os.path.basename(md_path)}')
    
    os.remove(video)
    shutil.rmtree(fdir)
    ok += 1
    time.sleep(1)

log(f'✅ 完成! 成功:{ok} 失败:{fail} 跳过:{skip}')
