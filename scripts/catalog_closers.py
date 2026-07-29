"""Batch fetch video info for Closers videos"""
import json, time, sys, subprocess

BVS = """BV1wx411h7u4
BV1cx411h7DW
BV1cx411h7nN
BV16x411h7bA
BV16x411h7VS
BV1rx411h7od
BV1Cx411h75v
BV1ex411h7h4
BV13x411z7j7
BV13x411s7fT
BV1HW411B7e4
BV1Gt411s7V1
BV1t441187qM
BV1dt411P72S
BV1cJ411T75k
BV1RJ411K7Ei
BV11E411b7v1
BV1rJ411k7fn
BV16E411W7Uf
BV1FD4y1U7TF
BV13541187eN
BV1WU4y147L2
BV1PM4y1L7HJ
BV1xL4y187hY
BV1344y1t7vA
BV1Kb4y1a78n
BV1Af4y1u7tm
BV1Qu411d7ou
BV1aP4y1L7LG
BV1ei4y1X7Sk
BV1qb4y1e7Vz
BV1TF411p7ar
BV1qS4y1f7qQ
BV19q4y187D7
BV1d3411h7HJ
BV1VS4y1C7yp
BV1Km4y1d74K
BV11b4y1W7mD
BV1aL4y1T7CE
BV1ML4y1M75H
BV1Aa411v7YW
BV15v4y1A7B5
BV1eG411b7Jn
BV1cP411g768
BV1kt411Q7xt
BV12W411U74u
BV1Ss411w7nt
BV1Hs411H74o
BV1KW411E7Fz
BV1L54y1A7KQ
BV1Km4y1j7Sf
BV1z94y1r7ko
BV1nC4y1q7EH
BV1bQ4y1E77q
BV1UC4y1K7EK
BV15b4y1G7hm
BV1Gy411i7nS
BV17mCzY4EnK
BV1rGKRzsEQ1
BV1WbeMzNEvY
BV1krqGBYErN
BV1qDLf6TEjh""".strip().split('\n')

results = []
agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
for i, bv in enumerate(BVS):
    time.sleep(1.2)
    try:
        r = subprocess.run([
            'curl', '-s', '--noproxy', '*', '--max-time', '10',
            '-H', f'User-Agent: {agent}',
            '-H', 'Referer: https://www.bilibili.com',
            f'https://api.bilibili.com/x/web-interface/view?bvid={bv}'
        ], capture_output=True, text=True, timeout=15)
        d = json.loads(r.stdout)
        if d.get('code') == 0:
            dd = d['data']
            results.append({
                'bv': bv, 'title': dd['title'], 'duration': dd['duration'],
                'views': dd['stat']['view'], 'cid': dd.get('cid', 0),
                'aid': dd.get('aid', 0)
            })
            cat = '??'
            title = dd['title']
            if '角色' in title or '人物' in title or '角色' in title:
                cat = '角色'
            elif '章节' in title or '第' in title:
                cat = '章节'
            elif '访谈' in title or '采访' in title:
                cat = '访谈'
            elif '动画' in title or '预告' in title:
                cat = '动画'
            print(f'{i+1:2d}/{len(BVS)} {bv} [{cat}] {dd["title"][:40]:40s} {dd["duration"]}s')
        else:
            results.append({'bv': bv, 'title': f'ERR:{d.get("message","?")}', 'duration': 0, 'views': 0})
            print(f'{i+1:2d}/{len(BVS)} {bv} [ERR] {d.get("message","?")}')
    except Exception as e:
        results.append({'bv': bv, 'title': f'ERR:{str(e)[:30]}', 'duration': 0, 'views': 0})
        print(f'{i+1:2d}/{len(BVS)} {bv} [ERR] {str(e)[:30]}')

# Summary
total_dur = sum(r.get('duration', 0) for r in results)
total_views = sum(r.get('views', 0) for r in results)
print(f'\n=== Summary ===')
print(f'Total: {len(results)} videos')
print(f'Duration: {total_dur}s ({total_dur/60:.0f}min)')
print(f'Total views: {total_views}')
print(f'Auto-categorized:')
for r in results:
    t = r.get('title','')
    cat = '角色剧情动画' if '角色' in t else ('章节动画' if ('章' in t or '第' in t) else ('访谈' if '访谈' in t else ('其他')))
    print(f'  [{cat:6s}] {r["bv"]} {t[:50]}')

# Save results
with open('C:/Users/zwq/aigc-comfy-pipeline/closers_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'\nSaved to closers_catalog.json')
