#!/usr/bin/env python3
"""
VAD + Whisper 增强语音管线
- Silero VAD 检测语音段 → 区分"角色语音"vs"BGM/纯音乐"
- Whisper large-v3 (GPU) 转录 → 更高准确率
- 输出带标记的转录: 🗣️角色语音 / 🎵背景音乐

用法:
  python vad_enhanced.py transcribe <wav_file>          # 转录单个文件
  python vad_enhanced.py batch <directory>               # 批量处理目录
  python vad_enhanced.py merge <video> <output.md>       # 完整管线: 下载→VAD→Whisper→帧分析→归档
"""
import sys, os, json, time, torch, soundfile as sf
import numpy as np
from pathlib import Path

SILERO_PKG = os.path.dirname(__import__('silero_vad').__file__)
VAD_MODEL_PATH = os.path.join(SILERO_PKG, 'data', 'silero_vad.jit')
WHISPER_MODEL = 'large-v3'  # or 'base' for CPU fallback

class VADProcessor:
    """Silero VAD — 语音活动检测"""
    def __init__(self, device='cpu'):
        from silero_vad import utils_vad
        self.model = utils_vad.init_jit_model(VAD_MODEL_PATH, device=device)
    
    def get_speech_segments(self, audio_path, merge_gap=1.0):
        """返回 [(start, end, is_speech), ...]"""
        from silero_vad import utils_vad
        audio, sr = sf.read(audio_path)
        total_dur = len(audio) / sr
        
        ts = utils_vad.get_speech_timestamps(audio, self.model, return_seconds=True, sampling_rate=sr)
        
        # Merge close segments
        merged = []
        for t in ts:
            if merged and t['start'] - merged[-1]['end'] < merge_gap:
                merged[-1]['end'] = t['end']
            else:
                merged.append(dict(t))
        
        # Build full timeline with speech/non-speech labels
        segments = []
        prev_end = 0
        for s in merged:
            if s['start'] > prev_end + 0.3:
                segments.append((prev_end, s['start'], False))  # non-speech
            segments.append((s['start'], s['end'], True))  # speech
            prev_end = s['end']
        if prev_end < total_dur:
            segments.append((prev_end, total_dur, False))
        
        return segments, total_dur


class WhisperTranscriber:
    """Whisper — 语音转文字"""
    def __init__(self, model_name='base', device='cpu'):
        import whisper
        self.model = whisper.load_model(model_name, device=device)
        self.device = device
    
    def transcribe(self, audio_path, language='ko'):
        result = self.model.transcribe(audio_path, language=language)
        return result['segments']


def merge_vad_whisper(vad_segments, whisper_segments):
    """VAD + Whisper 合并: 每段Whisper标记is_speech"""
    merged = []
    for seg in whisper_segments:
        s, e, text = seg['start'], seg['end'], seg['text'].strip()
        if not text:
            continue
        is_speech = any(
            s < speech_end and e > speech_start
            for speech_start, speech_end, is_sp in vad_segments
            if is_sp
        )
        merged.append({
            'start': s, 'end': e, 'text': text,
            'is_speech': is_speech,
            'label': '🗣️' if is_speech else '🎵'
        })
    return merged


def format_output(segments, vad_info, vlm_frames=None):
    """格式化成知识库格式"""
    lines = []
    lines.append(f"## 语音转录 (VAD增强)")
    lines.append(f"总时长: {vad_info:.0f}s | {sum(1 for s in segments if s['is_speech'])}段语音")
    lines.append(f"")
    lines.append(f"| {'标记':4s} | {'时间':14s} | {'文本'} |")
    lines.append(f"| {'-'*4} | {'-'*14} | {'-'*40} |")
    
    for s in segments:
        t = f"{int(s['start']//60):02d}:{int(s['start']%60):02d}-{int(s['end']//60):02d}:{int(s['end']%60):02d}"
        lines.append(f"| {s['label']} | {t} | {s['text'][:60]} |")
    
    return '\n'.join(lines)


def process_audio(audio_path, whisper_model='base', language='ko'):
    """完整流程: 音频 → VAD → Whisper → 合并"""
    print(f"[VAD] 加载模型...")
    vad = VADProcessor(device='cpu')
    
    print(f"[VAD] 检测语音段...")
    vad_segs, total_dur = vad.get_speech_segments(audio_path)
    speech_count = sum(1 for _, _, sp in vad_segs if sp)
    print(f"  → {speech_count} 段语音 / {len(vad_segs)} 段总")
    
    print(f"[Whisper] 转录 ({whisper_model})...")
    wh = WhisperTranscriber(model_name=whisper_model, device='cpu')
    t0 = time.time()
    whisper_segs = wh.transcribe(audio_path, language=language)
    print(f"  → {len(whisper_segs)} 段, 耗时 {time.time()-t0:.0f}s")
    
    merged = merge_vad_whisper(vad_segs, whisper_segs)
    speech_texts = [s for s in merged if s['is_speech']]
    bgm_texts = [s for s in merged if not s['is_speech']]
    print(f"\n  语音段: {len(speech_texts)} | BGM误抓: {len(bgm_texts)}")
    
    return merged, total_dur


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'transcribe' and len(sys.argv) >= 3:
        audio = sys.argv[2]
        model = sys.argv[3] if len(sys.argv) >= 4 else 'base'
        segments, dur = process_audio(audio, model)
        print(format_output(segments, dur))
    
    elif cmd == 'test':
        # Quick test with our sample file
        test_file = os.path.join(os.path.dirname(__file__) or '.', 'vt.wav')
        if os.path.exists(test_file):
            segs, dur = process_audio(test_file, 'base')
            print(format_output(segs, dur))
        else:
            print("No test file found. Run the VAD test first to create vt.wav")
    
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
