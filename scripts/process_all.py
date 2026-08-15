#!/usr/bin/env python3
"""处理已下载的视频 — 用本地mp4文件，不下重复"""
import json, time, os, base64, subprocess, shutil, re, requests

WORK = r'C:\Users\zwq\aigc-comfy-pipeline'
DL_DIR = r'C:\Users\zwq\hermes-workspace\downloads'
KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
HERMES_VENV = r'C:\Users\zwq\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
os.makedirs(KBASE, exist_ok=True)
os.chdir(WORK)

# BV编号与分类
REMAINING = [
    ('BV1wx411h7u4', '角色剧情/李世赫', 93),
    ('BV1t441187qM', '团本/首个十二人团本', 65),
    ('BV1dt411P72S', '宣传/釜山千面PV', 101),
    ('BV1cJ411T75k', '宣传/龙裔信仰时装', 61),
    ('BV1RJ411K7Ei', '活动/三周年庆', 170),
    ('BV11E411b7v1', '章节/釜山第2章PV', 74),
    ('BV13541187eN', '团本/海团介绍', 39),
    ('BV1PM4y1L7HJ', '团本/机械团介绍', 73),
    ('BV1xL4y187hY', '活动/五周年庆', 2395),
    ('BV1344y1t7vA', '宣传/所罗门礼服PV', 277),
    ('BV1Kb4y1a78n', '语音剧/第1集黑羊队', 1734),
    ('BV1Af4y1u7tm', '语音剧/第2集红狼队', 1917),
    ('BV1Qu411d7ou', '语音剧/第3集苍鹰队', 2039),
    ('BV1aP4y1L7LG', '语音剧/第4集褐鼠队', 1893),
    ('BV1d3411h7HJ', '语音剧/第2季第2集', 2179),
    ('BV1VS4y1C7yp', '宣传/白夜堡垒', 567),
    ('BV1ML4y1M75H', '语音剧/第2季第3集', 1946),
    ('BV1Aa411v7YW', '采访/塞特篇', 486),
    ('BV1eG411b7Jn', '团本/野兽团介绍', 90),
    ('BV12W411U74u', '宣传/黑暗光辉PV', 79),
    ('BV1L54y1A7KQ', '宣传/新首尔支部', 114),
    ('BV1Km4y1j7Sf', '宣传/火焰的悲剧', 96),
    ('BV1z94y1r7ko', '团本/火焰团介绍', 85),
    ('BV17mCzY4EnK', '宣传/殉教者之丘', 196),
    ('BV1WbeMzNEvY', '团本/D团介绍', 88),
    ('BV1krqGBYErN', '宣传/仁川港', 110),
]

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

def find_local(bv):
    """Find downloaded mp4 for this BV"""
    for f in os.listdir(DL_DIR):
        if f.startswith(bv) and f.endswith('.mp4'):
            return os.path.join(DL_DIR, f)
    return None

def get_info(bv):
    s = requests.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
    d = s.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}', timeout=15).json()
    return d['data'] if d.get('code')==0 else None

def transcribe(wav):
    r = subprocess.run([HERMES_VENV, '-c', f'''
import whisper
model=whisper.load_model("base",device="cpu")
r=model.transcribe(r"{wav}",language="ko")
for s in r.get("segments",[]): print(f"{{s['start']:.1f}}|{{s['end']:.1f}}|{{s['text'].strip()}}")
'''], capture_output=True, text=True, timeout=3600)
    return r.stdout

def vlm(fpath, prompt):
    with open(fpath,'rb') as f: b64 = base64.b64encode(f.read()).decode()
    p = {"model":"qwen3-vl","stream":False,"prompt":prompt,"images":[b64],"options":{"temperature":0.1}}
    pf = fpath+'.p.json'
    with open(pf,'w') as f: json.dump(p, f)
    r = subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
        'http://localhost:11434/api/generate','-H','Content-Type: application/json','-d',f'@{pf}'],
        capture_output=True, text=True, timeout=65)
    try: os.remove(pf)
    except: pass
    try: return json.loads(r.stdout).get('response','')
    except: return ''

log(f'{"="*40}')
log(f'处理 {len(REMAINING)} 个本地视频')
log(f'{"="*40}')

# Warm VLM+Ollama
subprocess.run(['curl','-s','--noproxy','*','--max-time','60',
    'http://localhost:11434/api/generate','-H','Content-Type: application/json',
    '-d','{"model":"qwen3-vl","prompt":"warm","keep_alive":"30m"}'], capture_output=True, timeout=70)
log('VLM ready')

ok, fail = 0, 0
for bv, cat, dur in REMAINING:
    try:
        log(f'▶️ {cat}: {bv} ({dur}s)')
        
        # Use local file
        video = find_local(bv)
        if not video:
            log(f'  ❌ 本地未找到')
            fail+=1; continue
        log(f'  ✅ 使用本地文件')
        
        info = get_info(bv)
        if not info: log(f'  ⚠️ API失败'); info = {'title':bv,'stat':{'view':0}}
        
        # Audio -> Whisper
        wav = f'proc_{bv}.wav'
        subprocess.run(['ffmpeg','-i',video,'-vn','-ar','16000','-ac','1','-c:a','pcm_s16le','-y',wav], capture_output=True, timeout=60)
        t0 = time.time()
        tr = transcribe(wav)
        log(f'  🎤 Whisper in {time.time()-t0:.0f}s')
        try: os.remove(wav)
        except: pass
        
        # Frames
        fdir = f'proc_{bv}_f'
        if os.path.exists(fdir): shutil.rmtree(fdir)
        os.makedirs(fdir)
        fps_val = '1/2'
        subprocess.run(['ffmpeg','-i',video,'-vf',f'fps={fps_val}','-q:v','2','-y',f'{fdir}/f_%04d.jpg'], capture_output=True, timeout=120)
        frames = sorted([f for f in os.listdir(fdir) if f.endswith('.jpg')])
        log(f'  🖼️ {len(frames)}帧 (fps=1/2)')
        
        # VLM sample (skip for voice dramas - visual info minimal)
        results = []
        if '语音剧' not in cat:
            sample = sorted(set(frames[:30]))[:30]
            t0 = time.time()
            for fn in sample:
                sec = (int(re.search(r'(\d+)',fn).group(1))-1)*2
                prompt = '描述封印者截图：人物/服装/场景/色调/文字。≤20字。'
                if '团本' in cat: prompt = '描述BOSS战斗：BOSS外观/技能特效/攻击。≤20字。'
                resp = vlm(os.path.join(fdir,fn), prompt)
                results.append((sec, resp))
                if resp: log(f'    {fn} ({sec}s): {resp[:35]}')
            log(f'  ✅ VLM {len(results)}帧 in {time.time()-t0:.0f}s')
        else:
            log(f'  ⏭️ 语音剧跳过VLM')
        
        # Build archive
        title = info.get('title',bv)
        ft = ''.join(f'| {a//60:02d}:{a%60:02d} | {b[:40]} |\n' for a,b in results)
        ts_text = ''
        if tr:
            for line in tr.strip().split('\n'):
                if '|' in line:
                    p = line.split('|')
                    if len(p)>=3:
                        ts_text += f'| {int(float(p[0])//60):02d}:{int(float(p[0])%60):02d} | {p[2][:60]} |\n'
        md = f"""# {title}
## 元数据
- BV: {bv} | 分类: {cat} | 时长: {dur//60}:{dur%60:02d} | 播放: {info.get('stat',{}).get('view',0)}
## 帧分析({len(results)}帧)
| 时间 | 画面 |
|:----:|------|
{ft}
## 语音转录
| 时间 | 文本 |
|:----:|------|
{ts_text if ts_text else '(无对话/纯BGM)'}
"""
        fn = re.sub(r'[\\/:*?"<>|]','_',title)[:50]
        with open(os.path.join(KBASE, f'{bv}_{fn}.md'),'w',encoding='utf-8') as f: f.write(md)
        log(f'  ✅ 归档')
        
        shutil.rmtree(fdir)
        os.remove(wav) if os.path.exists(wav) else None
        ok+=1
    except Exception as e:
        log(f'  ❌ Error: {e}')
        fail+=1
    time.sleep(2)

log(f'✅ 完成! 成功:{ok} 失败:{fail}')
