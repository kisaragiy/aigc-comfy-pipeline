#!/usr/bin/env python3
"""Continuation batch: remaining 20 Closers videos"""
import json, time, os, sys, base64, subprocess, shutil, re, requests as req

HERMES_VENV = r'C:\Users\zwq\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
WORK = r'C:\Users\zwq\aigc-comfy-pipeline'
KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
os.makedirs(KBASE, exist_ok=True)
os.chdir(WORK)

# Remaining videos
REMAINING = {
    'BV1cx411h7nN': '角色剧情/蕾比雅',
    'BV16x411h7VS': '角色剧情/J叔',
    'BV1ei4y1X7Sk': '角色采访/白',
    'BV1qb4y1e7Vz': '角色采访/未来',
    'BV1TF411p7ar': '角色采访/李世赫',
    'BV1qS4y1f7qQ': '角色采访/缇娜',
    'BV19q4y187D7': '角色采访/蕾比雅',
    'BV1Km4y1d74K': '角色采访/李瑟钰',
    'BV11b4y1W7mD': '角色采访/金哲秀',
    'BV1aL4y1T7CE': '角色采访/露娜',
    'BV1Aa411v7YW': '角色采访/塞特',
    'BV15v4y1A7B5': '角色采访/薇尔莉',
    'BV11E411b7v1': '章节动画/釜山第2章',
    'BV16E411W7Uf': '章节动画/失忆审判者',
    'BV1kt411Q7xt': '章节动画/猎人之夜',
    'BV1Hs411H74o': '章节动画/异之章',
    'BV1nC4y1q7EH': '章节动画/博物馆1',
    'BV1UC4y1K7EK': '章节动画/博物馆2',
    'BV15b4y1G7hm': '章节动画/博物馆3',
    'BV1bQ4y1E77q': '章节动画/博物馆幕间',
}

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

def setup_session():
    """Cookie持久化Session"""
    s = req.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                      'Referer': 'https://www.bilibili.com/'})
    s.get('https://www.bilibili.com/', timeout=10)
    return s

def get_video(s, bv):
    d = s.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}', timeout=15).json()
    if d.get('code') != 0: return None
    return d['data']

def download(s, bv, cid):
    url = f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={cid}&qn=16&platform=html5&high_quality=1'
    d = s.get(url, timeout=15).json()
    if not d.get('data',{}).get('durl'): return None
    vurl = d['data']['durl'][0]['url']
    out = f'ct_{bv}.mp4'
    subprocess.run(['curl', '-L', '--noproxy', '*', '--max-time', '120',
        '-H', 'User-Agent: Mozilla/5.0', '-o', out, vurl], capture_output=True, timeout=130)
    return out if os.path.exists(out) and os.path.getsize(out) > 10000 else None

def transcribe(path):
    wav = path.replace('.mp4', '.wav')
    subprocess.run(['ffmpeg', '-i', path, '-vn', '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', '-y', wav], capture_output=True, timeout=60)
    r = subprocess.run([HERMES_VENV, '-c', f'''
import whisper
model=whisper.load_model("base",device="cpu")
r=model.transcribe(r"{wav}",language="ko")
for s in r.get("segments",[]): print(f"{{s['start']:.1f}}|{{s['end']:.1f}}|{{s['text'].strip()}}")
'''], capture_output=True, text=True, timeout=600)
    try: os.remove(wav)
    except: pass
    return r.stdout

def extract_frames(path):
    d = path.replace('.mp4','_f')
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)
    subprocess.run(['ffmpeg','-i',path,'-vf','fps=1/2','-q:v','2','-y',f'{d}/f_%04d.jpg'], capture_output=True, timeout=120)
    return sorted([f for f in os.listdir(d) if f.endswith('.jpg')]), d

def vlm(frame_path):
    with open(frame_path,'rb') as f: b64 = base64.b64encode(f.read()).decode()
    p = json.dumps({"model":"qwen3-vl:8b","stream":False,"prompt":"描述封印者动画截图：人物/服装/场景/色调。≤20字。","images":[b64],"options":{"temperature":0.1}})
    pf = frame_path+'.p.json'
    with open(pf,'w') as f: f.write(p)
    r = subprocess.run(['curl','-s','--noproxy','*','--max-time','60','http://localhost:11434/api/generate','-H','Content-Type: application/json','-d',f'@{pf}'], capture_output=True, text=True, timeout=65)
    try: os.remove(pf)
    except: pass
    try: return json.loads(r.stdout).get('response','')
    except: return ''

def save(bv, info, transcript, frames, cat):
    t = info.get('title',bv)
    ft = ''.join(f'| {a//60:02d}:{a%60:02d} | {b[:40]} |\n' for a,b in frames)
    ts = ''
    if transcript:
        for l in transcript.strip().split('\n'):
            if '|' in l:
                p = l.split('|')
                if len(p)>=3: ts += f'| {int(float(p[0])//60):02d}:{int(float(p[0])%60):02d} | {p[2][:60]} |\n'
    md = f"""# {t}
## 元数据
- BV: {bv} | 分类: {cat} | 时长: {info.get('duration',0)//60}:{info.get('duration',0)%60:02d} | 播放: {info.get('stat',{}).get('view',0)}
## 帧分析({len(frames)}帧)
| 时间 | 画面 |
|:----:|------|
{ft}
## 语音转录
| 时间 | 文本 |
|:----:|------|
{ts if ts else '(无对话/纯BGM)'}
"""
    fn = re.sub(r'[\\/:*?"<>|]','_',t)[:50]
    p = os.path.join(KBASE, f'{bv}_{fn}.md')
    with open(p,'w',encoding='utf-8') as f: f.write(md)
    return p

log('='*40)
log(f'续跑: {len(REMAINING)} 个视频')
log('='*40)

# Warm VLM
subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
    'http://localhost:11434/api/generate','-H','Content-Type: application/json',
    '-d','{"model":"qwen3-vl:8b","prompt":"warm","keep_alive":"30m"}'], capture_output=True, timeout=70)
log('VLM ready')

s = setup_session()
ok, fail = 0, 0
for bv, cat in REMAINING.items():
    try:
        log(f'▶️ {cat}: {bv}')
        info = get_video(s, bv)
        if not info: log(f'  ❌ API失败'); fail+=1; continue
        log(f'  {info["title"][:50]} ({info["duration"]}s)')
        
        video = download(s, bv, info.get('cid',0))
        if not video: log(f'  ❌ 下载失败'); fail+=1; continue
        log(f'  ✅ {os.path.getsize(video)//1024}KB')
        
        log(f'  🎤 转录...')
        t0=time.time()
        tr = transcribe(video)
        if tr: log(f'  ✅ {len(tr.strip().split(chr(10)))} segs in {time.time()-t0:.0f}s')
        
        log(f'  🖼️ 抽帧...')
        t0=time.time()
        frames, fdir = extract_frames(video)
        log(f'  ✅ {len(frames)}帧 in {time.time()-t0:.0f}s')
        
        log(f'  👁️ VLM...')
        results=[]
        sample = sorted(set(frames[:30]))[:30]
        t0=time.time()
        for fn in sample:
            r = vlm(os.path.join(fdir,fn))
            sec = (int(re.search(r'(\d+)',fn).group(1))-1)*2
            results.append((sec, r))
            log(f'    {fn}: {r}')
        log(f'  ✅ {len(results)}帧 in {time.time()-t0:.0f}s')
        
        path = save(bv, info, tr, results, cat)
        log(f'  ✅ 归档: {path}')
        
        os.remove(video)
        if os.path.exists(fdir): shutil.rmtree(fdir)
        ok+=1
    except Exception as e:
        log(f'  ❌ 错误: {e}')
        fail+=1
    time.sleep(2)

log(f'✅ 完成! 成功:{ok} 失败:{fail}')
