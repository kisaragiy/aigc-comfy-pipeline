#!/usr/bin/env python3
"""Batch process Closers videos: download → audio(Whisper) → frames(2s) → VLM → archive"""
import json, time, os, sys, base64, subprocess, shutil, re

HERMES_VENV = r'C:\Users\zwq\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
WORKDIR = r'C:\Users\zwq\aigc-comfy-pipeline'
KBASE = r'C:\Users\zwq\knowledge\closers-lore\bilibili-archive'
os.makedirs(KBASE, exist_ok=True)
os.chdir(WORKDIR)

# Load catalog
with open(os.path.join(WORKDIR, 'scripts/closers_catalog.json')) as f:
    catalog = json.load(f)

# Priority: 角色剧情动画 + 章节动画
PRIORITY = {
    'BV1cx411h7DW': '角色剧情动画/李瑟钰',
    'BV1cx411h7nN': '角色剧情动画/蕾比雅',
    'BV16x411h7bA': '角色剧情动画/尤莉',
    'BV16x411h7VS': '角色剧情动画/J叔',
    'BV1rx411h7od': '角色剧情动画/米斯丁',
    'BV1Cx411h75v': '角色剧情动画/纳塔',
    'BV1ex411h7h4': '角色剧情动画/缇娜',
    'BV13x411z7j7': '角色剧情动画/薇尔莉',
    'BV13x411s7fT': '角色剧情动画/沃尔夫冈',
    'BV1HW411B7e4': '角色剧情动画/露娜',
    'BV1Gt411s7V1': '角色剧情动画/塞特',
    'BV1rJ411k7fn': '角色剧情动画/希冀之花',
    'BV1FD4y1U7TF': '角色剧情动画/银河',
    'BV1WU4y147L2': '角色剧情动画/露西',
    'BV1Ss411w7nt': '角色剧情动画/白',
    'BV1KW411E7Fz': '角色剧情动画/索玛',
    'BV1Gy411i7nS': '角色剧情动画/尹莉娅',
    'BV1rGKRzsEQ1': '角色剧情动画/特莉丝',
    'BV1qDLf6TEjh': '角色剧情动画/莫亚',
    'BV1cP411g768': '角色剧情动画/艾莉',
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
    'BV1nC4y1q7EH': '章节动画/博物馆第1季',
    'BV1UC4y1K7EK': '章节动画/博物馆第2季',
    'BV15b4y1G7hm': '章节动画/博物馆第3季',
    'BV1bQ4y1E77q': '章节动画/博物馆幕间',
}

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def parse_curl(url, headers=None):
    cmd = ['curl', '-s', '--noproxy', '*', '--max-time', '15']
    if headers:
        for k, v in headers.items():
            cmd.extend(['-H', f'{k}: {v}'])
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return json.loads(r.stdout) if r.stdout.strip() else {}

def download_video(bv, cid):
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    url = f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={cid}&qn=16&platform=html5&high_quality=1'
    d = parse_curl(url, {'User-Agent': ua, 'Referer': 'https://www.bilibili.com'})
    if d.get('code') != 0 or not d.get('data',{}).get('durl'):
        return None
    video_url = d['data']['durl'][0]['url']
    out = f'closers_temp_{bv}.mp4'
    subprocess.run(['curl', '-L', '--noproxy', '*', '--max-time', '120',
        '-H', f'User-Agent: {ua}', '-H', 'Referer: https://www.bilibili.com',
        '-o', out, video_url], capture_output=True, text=True, timeout=130)
    if os.path.exists(out) and os.path.getsize(out) > 10000:
        return out
    return None

def transcribe_audio(video_path):
    wav = video_path.replace('.mp4', '.wav')
    subprocess.run(['ffmpeg', '-i', video_path, '-vn', '-ar', '16000', '-ac', '1',
        '-c:a', 'pcm_s16le', '-y', wav], capture_output=True, timeout=30)
    if not os.path.exists(wav):
        return ''
    r = subprocess.run([HERMES_VENV, '-c', f'''
import whisper, json
model = whisper.load_model("base", device="cpu")
result = model.transcribe(r"{wav}", language="ko")
for seg in result.get("segments", []):
    print(f"{{seg['start']:.1f}}|{{seg['end']:.1f}}|{{seg['text'].strip()}}")
'''], capture_output=True, text=True, timeout=600)
    try:
        os.remove(wav)
    except:
        pass
    return r.stdout.strip()

def extract_frames(video_path, fps='1/2'):
    frame_dir = video_path.replace('.mp4', '_frames')
    if os.path.exists(frame_dir):
        shutil.rmtree(frame_dir)
    os.makedirs(frame_dir, exist_ok=True)
    subprocess.run(['ffmpeg', '-i', video_path, '-vf', f'fps={fps}', '-q:v', '2',
        '-y', f'{frame_dir}/frame_%04d.jpg'], capture_output=True, timeout=120)
    frames = sorted([f for f in os.listdir(frame_dir) if f.endswith('.jpg')])
    return frame_dir, frames

def analyze_frame(frame_path, prompt):
    with open(frame_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {
        'model': 'qwen3-vl:8b', 'stream': False,
        'prompt': prompt, 'images': [b64], 'options': {'temperature': 0.1}
    }
    # Write payload to temp file to avoid Windows cmdline length limit
    payload_path = frame_path + '.payload.json'
    with open(payload_path, 'w') as f:
        json.dump(payload, f)
    r = subprocess.run(['curl', '-s', '--noproxy', '*', '--max-time', '60',
        'http://127.0.0.1:11434/api/generate',
        '-H', 'Content-Type: application/json', '-d', f'@{payload_path}'],
        capture_output=True, text=True, timeout=65)
    try:
        os.remove(payload_path)
    except:
        pass
    try:
        d = json.loads(r.stdout)
        return d.get('response', '(empty)').strip()
    except:
        return '(parse error)'

def save_archive(bv, info, transcript, frame_results, cat_name):
    title = info.get('title', bv)
    duration = info.get('duration', 0)
    views = info.get('views', 0)
    frame_table = ''.join(f'| {t//60:02d}:{t%60:02d} | {a[:40]} |\n' for t, a in frame_results)
    transcript_text = ''
    if transcript:
        for line in transcript.split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 3:
                    transcript_text += f'| {int(float(parts[0])//60):02d}:{int(float(parts[0])%60):02d} | {parts[2][:60]} |\n'
    md = f"""# {title}

## 元数据
- BV号: {bv} | 分类: {cat_name} | 时长: {duration//60}:{duration%60:02d} | 播放: {views}

## 帧分析({len(frame_results)}帧)
| 时间 | 画面 |
|:----:|------|
{frame_table}
## 语音转录
| 时间 | 文本 |
|:----:|------|
{transcript_text if transcript_text else '(无对话/纯BGM)'}
"""
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
    path = os.path.join(KBASE, f'{bv}_{safe_name}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(md)
    return path

def process_video(bv, cat_name):
    log(f'▶️ {cat_name}: {bv}')
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    d = parse_curl(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}',
                   {'User-Agent': ua, 'Referer': 'https://www.bilibili.com'})
    if d.get('code') != 0:
        log(f'  ❌ API: {d.get("message","?")}')
        return False
    info = d['data']
    log(f'  标题: {info["title"]} ({info["duration"]}s)')
    
    video = download_video(bv, info.get('cid', 0))
    if not video:
        log(f'  ❌ Download failed'); return False
    log(f'  ✅ Download ({os.path.getsize(video)//1024}KB)')
    
    log(f'  🎤 Transcribing...')
    t0 = time.time()
    transcript = transcribe_audio(video)
    if transcript:
        log(f'  ✅ Whisper: {len(transcript.split(chr(10)))} segs in {time.time()-t0:.0f}s')
    
    log(f'  🖼️ Frames...')
    t0 = time.time()
    frame_dir, frames = extract_frames(video, '1/2')
    log(f'  ✅ {len(frames)} frames in {time.time()-t0:.0f}s')
    
    log(f'  👁️ VLM analyzing {min(len(frames),30)} frames...')
    frame_results = []
    sample = frames[:30] if len(frames) <= 30 else frames[:10] + frames[-10:] + frames[len(frames)//3:len(frames)//3+5] + frames[2*len(frames)//3:2*len(frames)//3+5]
    sample = sorted(set(sample))[:30]
    t0 = time.time()
    for fname in sample:
        fpath = os.path.join(frame_dir, fname)
        idx = int(re.search(r'(\d+)', fname).group(1))
        time_sec = (idx - 1) * 2
        result = analyze_frame(fpath, f'描述封印者动画截图：人物/服装/场景/色调。≤20字。')
        frame_results.append((time_sec, result))
        log(f'    {fname}: {result}')
    log(f'  ✅ VLM {len(frame_results)} frames in {time.time()-t0:.0f}s')
    
    path = save_archive(bv, info, transcript, frame_results, cat_name)
    log(f'  ✅ Archived: {path}')
    
    os.remove(video)
    if os.path.exists(frame_dir):
        shutil.rmtree(frame_dir)
    return True

# === Main ===
log(f'{"="*40}')
log(f'Starting batch: {len(PRIORITY)} videos')
log(f'{"="*40}')

log('Warming VLM...')
subprocess.run(['curl', '-s', '--noproxy', '*', '--max-time', '60',
    'http://127.0.0.1:11434/api/generate',
    '-H', 'Content-Type: application/json',
    '-d', '{"model":"qwen3-vl:8b","prompt":"warmup","keep_alive":"30m"}'],
    capture_output=True, timeout=70)
log('VLM ready')

ok, fail = 0, 0
for bv, cat in PRIORITY.items():
    try:
        if process_video(bv, cat): ok += 1
        else: fail += 1
    except Exception as e:
        log(f'  ❌ Error: {e}')
        fail += 1
    time.sleep(2)

log(f'{"="*40}')
log(f'Done! OK:{ok} Fail:{fail}')
log(f'{"="*40}')
