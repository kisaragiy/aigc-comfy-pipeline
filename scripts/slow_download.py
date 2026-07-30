#!/usr/bin/env python3
"""慢慢下 — 只下载剩余24个B站视频, 不处理"""
import subprocess, time, os, json

WORK = r'C:\Users\zwq\hermes-workspace\downloads'
os.makedirs(WORK, exist_ok=True)
os.chdir(WORK)

COOKIES = r'C:\Users\zwq\hermes-workspace\bili_cookies.txt'

# Remaining BV numbers from the batch
BVS = [
    ('BV1dt411P72S', '宣传_釜山千面PV'),
    ('BV1cJ411T75k', '宣传_龙裔信仰时装'),
    ('BV1RJ411K7Ei', '活动_三周年庆'),
    ('BV11E411b7v1', '章节_釜山第2章PV'),
    ('BV13541187eN', '团本_海团介绍'),
    ('BV1PM4y1L7HJ', '团本_机械团介绍'),
    ('BV1xL4y187hY', '活动_五周年庆'),
    ('BV1344y1t7vA', '宣传_所罗门礼服PV'),
    ('BV1Kb4y1a78n', '语音剧_第1集黑羊队'),
    ('BV1Af4y1u7tm', '语音剧_第2集红狼队'),
    ('BV1Qu411d7ou', '语音剧_第3集苍鹰队'),
    ('BV1aP4y1L7LG', '语音剧_第4集褐鼠队'),
    ('BV1d3411h7HJ', '语音剧_第2季第2集'),
    ('BV1VS4y1C7yp', '宣传_白夜堡垒'),
    ('BV1ML4y1M75H', '语音剧_第2季第3集'),
    ('BV1Aa411v7YW', '采访_塞特篇'),
    ('BV1eG411b7Jn', '团本_野兽团介绍'),
    ('BV12W411U74u', '宣传_黑暗光辉PV'),
    ('BV1L54y1A7KQ', '宣传_新首尔支部'),
    ('BV1Km4y1j7Sf', '宣传_火焰的悲剧'),
    ('BV1z94y1r7ko', '团本_火焰团介绍'),
    ('BV17mCzY4EnK', '宣传_殉教者之丘'),
    ('BV1WbeMzNEvY', '团本_D团介绍'),
    ('BV1krqGBYErN', '宣传_仁川港'),
]

def log(m): print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)

log(f'开始慢速下载: {len(BVS)} 个视频')
log(f'保存到: {WORK}')

ok, fail = 0, 0
for bv, name in BVS:
    out = f'{bv}_{name}.mp4'
    if os.path.exists(out) and os.path.getsize(out) > 10000:
        log(f'  ⏭️ 已存在: {name}')
        ok += 1
        continue
    
    log(f'  ▶️ {name} ({bv})')
    try:
        r = subprocess.run(['yt-dlp', '--no-warnings',
            '-f', '30015+30216', '--merge-output-format', 'mp4',
            '--limit-rate', '500K',
            '--cookies', COOKIES,
            f'https://www.bilibili.com/video/{bv}',
            '-o', out],
            capture_output=True, text=True, timeout=600)
        if os.path.exists(out) and os.path.getsize(out) > 10000:
            sz = os.path.getsize(out) // 1024
            log(f'  ✅ {sz}KB')
            ok += 1
        else:
            log(f'  ❌ DL失败')
            fail += 1
    except subprocess.TimeoutExpired:
        # Check if partial download exists
        if os.path.exists(out) and os.path.getsize(out) > 10000:
            sz = os.path.getsize(out) // 1024
            log(f'  ⚠️ 超时但已下载 {sz}KB')
            ok += 1
        else:
            log(f'  ❌ 超时')
            fail += 1
    except Exception as e:
        log(f'  ❌ {str(e)[:60]}')
        fail += 1
    
    # Wait between videos to avoid rate limiting
    time.sleep(30)

log(f'\n✅ 完成! 成功:{ok} 失败:{fail}')
