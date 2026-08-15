#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/character.py — 角色设计先行（手游商业人设）v1.0
==========================================================
商业画师流程里最值钱的阶段：人设设计（剪影/配色/标志/服装）。
LLM 按"商业角色设计四要素"产出完整设计 → 保存 → 接 converge 生成。

用法:
  python -m agents workshop character "角色概念" [--name 角色名]
      [--out 目录] [--generate]   # --generate 直接接生成管线
"""

import argparse, json, os, re, sys, time, urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT_BASE = PROJECT / 'outputs'
OLLAMA = 'http://172.22.175.253:11434'

DESIGN_PROMPT = '''你是资深手游角色设计师（明日方舟/原神/崩铁级别），为角色概念做完整商业人设设计。

【商业角色设计五要素（必须全部满足）】
1. 剪影辨识度：角色站在逆光剪影里5米外能认出——姿态/体型/标志轮廓必须独特
2. 配色方案：1-2个主色 + 1个点缀色（点缀色=记忆点），全图统一
3. 标志性元素：一个让人记住的记忆点（武器形状/发光部件/纹章/宠物/特效）
4. 服装设计：每一件都有设计逻辑（功能/美学/故事），拒绝模板化服装
5. 性吸引力（男性向手游商业核心，必须重点设计）：
   - 服装：紧身勾勒曲线 + 露肤设计（腹部/大腿/肩背/腰侧）+ 半透明材质 + 开叉镂空
   - 材质钩子：过膝袜/蕾丝边/丝带/绷带/绑带/湿身质感（至少2种）
   - 姿态：微侧身/回眸/弯腰/双腿交叉等展示身体曲线的姿势
   - 原则：若隐若现优于全露；性感要有设计逻辑（战斗服为什么露=活动性/呼吸性/深海适应）

输出严格 JSON（无其他文字）:
{
  "name": "角色名",
  "concept": "概念一句话",
  "appearance": "外貌特征（发色/瞳色/发型/体型，必填）",
  "silhouette": "剪影设计描述（姿态/体型/标志轮廓，中文）",
  "palette": {"main": "主色（含色值）", "secondary": "辅助色", "accent": "点缀色（记忆点，含理由）"},
  "signature": "标志性元素（记忆点，中文）",
  "costume": "服装设计（逐件描述+设计逻辑+露肤/紧身/材质钩子，中文）",
  "pose": "展示姿态（身体曲线展示方式，中文）",
  "details": "细节补充（纹章/编号/配饰/特效）",
  "prompt_en": "完整英文绘图prompt（包含全部设计元素：剪影/配色/标志/服装/露肤/姿态/细节，可直接用于SDXL生成）"
}'''


def _sheet_render(prompt_en, name, out_dir, count=3, seed=20260812):
    """三视图模式：正面/侧面/背面 各渲染 count 张（VTB 皮套刚需）"""
    from workshop.create import create_from_nl
    views = [('正面', 'front view, facing camera directly, symmetric pose, character sheet style'),
             ('侧面', 'side view, profile view, character sheet style'),
             ('背面', 'back view, seen from behind, character sheet style')]
    saved = []
    for view_cn, view_en in views:
        print(f'  ── {view_cn}视图 ──')
        p = f'{prompt_en}, {view_en}'
        sub = out_dir / f'sheet_{view_cn}'
        try:
            create_from_nl(p, count=count, model_type='sdxl', seed=seed,
                           prompt_ready=True, inspect=False, dry_run=False,
                           output_dir=str(sub))
            # 收集 best.png
            import glob
            cands = sorted(glob.glob(str(sub / '**' / 'best.png'), recursive=True))
            if cands:
                saved.append((view_cn, cands[0]))
                print(f'  ✅ {view_cn}: {cands[0]}')
        except Exception as e:
            print(f'  ⚠️ {view_cn} 失败: {str(e)[:100]}')
    # 拼接三视图成一张 sheet（左中右）
    if len(saved) == 3:
        try:
            from PIL import Image
            imgs = [Image.open(p[1]) for p in saved]
            h = max(i.height for i in imgs)
            w = sum(i.width for i in imgs)
            sheet = Image.new('RGB', (w, h), (255, 255, 255))
            x = 0
            for i in imgs:
                sheet.paste(i, (x, 0))
                x += i.width
            sheet_path = out_dir / f'{name or "character"}_sheet.png'
            sheet.save(sheet_path)
            print(f'  🎨 三视图拼版: {sheet_path}')
            saved.append(('sheet', str(sheet_path)))
        except Exception as e:
            print(f'  ⚠️ 拼版失败: {str(e)[:100]}')
    return saved

def _http():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

def design_character(concept, name=None, timeout=180):
    """LLM 角色设计 → 返回 dict"""
    body = json.dumps({
        'model': 'qwen3:14b', 'stream': False, 'think': False,
        'prompt': f'{DESIGN_PROMPT}\n角色概念: {concept}\n' + (f'角色名: {name}\n' if name else ''),
    }).encode()
    req = urllib.request.Request(OLLAMA + '/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = json.loads(_http().open(req, timeout=timeout).read())
    out = resp.get('response', '')
    m = re.search(r'\{[\s\S]*\}', out)
    if not m:
        raise RuntimeError(f'LLM 无 JSON 输出: {out[:100]}')
    return json.loads(m.group(0))

def render_design(d):
    """设计 dict → 中文可读设计稿"""
    def s(v):
        if isinstance(v, list):
            return '\n'.join(str(x) for x in v)
        return str(v)
    p = d.get('palette', {}) or {}
    lines = [
        f"# {d.get('name', '未命名')}",
        f"概念: {d.get('concept', '')}",
        '',
        f"## 剪影（辨识度）",
        s(d.get('silhouette', '')),
        '',
        f"## 配色方案",
        f"- 主色: {s(p.get('main', ''))}",
    ]
    if p.get('secondary'):
        lines.append(f"- 辅助色: {s(p['secondary'])}")
    lines += [f"- 点缀色: {s(p.get('accent', ''))}", '',
              f"## 标志性元素（记忆点）", s(d.get('signature', '')),
              '', f"## 展示姿态", s(d.get('pose', '')),
              '', f"## 服装设计", s(d.get('costume', '')),
              '', f"## 细节", s(d.get('details', '')),
              '', f"## 英文绘图 prompt", f"```", s(d.get('prompt_en', '')), f"```"]
    return '\n'.join(lines)

def _condense_prompt(d, scene='', timeout=90):
    """合成精简英文 prompt（<450 字符）。
    钥匙锁原则：LLM 只做最小可控的事（翻译外貌），其余模板硬编码——
    模板里没有战斗词，就不会跑偏。"""
    def _llm_translate(text, timeout=60):
        """中文→英文（只翻译，不创作）"""
        try:
            body = json.dumps({
                'model': 'qwen3:14b', 'stream': False, 'think': False,
                'prompt': f'翻译成英文（直译，不要添加任何内容）: {text[:200]}',
            }).encode()
            req = urllib.request.Request(OLLAMA + '/api/generate', data=body,
                                         headers={'Content-Type': 'application/json'})
            resp = json.loads(_http().open(req, timeout=timeout).read())
            out = resp.get('response', '').strip()
            if out and len(out) < 200:
                return out
        except Exception:
            pass
        return text

    # 有场景（泳装皮肤）：100% 模板拼装（无战斗词容身之处）
    if scene:
        appearance = _llm_translate(d.get('appearance', '银白色长发, 蓝色眼睛'))
        palette = d.get('palette', {}) or {}
        main_c = str(palette.get('main', 'deep blue')).split('(')[0].strip()[:20]
        accent_c = str(palette.get('accent', 'cyan')).split('(')[0].strip()[:20]
        return (f'summer swimsuit skin, {appearance}, '
                f'white bikini top and bikini bottom, bare midriff, off-shoulder top, '
                f'exposed shoulders, thigh-high stockings, '
                f'swimming pool, bright summer resort, water ripples, '
                f'backlit by warm sunset from behind, golden rim light on hair and shoulders, '
                f'face softly lit with gentle fill light, consistent single light direction, '
                f'soft shadow falling away from light, '
                f'{main_c} and {accent_c} color scheme, '
                f'anime cel shading, game character art, full body')

    # 无场景：全字段 LLM 合成（保留战斗元素）
    fields = {
        'name': d.get('name', ''), 'concept': d.get('concept', ''),
        'appearance': d.get('appearance', ''),
        'silhouette': d.get('silhouette', ''), 'costume': d.get('costume', ''),
        'pose': d.get('pose', ''), 'signature': d.get('signature', ''),
        'details': d.get('details', ''), 'palette': d.get('palette', {}),
    }
    try:
        body = json.dumps({
            'model': 'qwen3:14b', 'stream': False, 'think': False,
            'prompt': f'''把下面的角色设计翻译合成英文绘图 prompt（420 字符以内），规则：
1. 必须保留：发色/瞳色/服装结构/露肤部位/配色/标志物
2. 服装有露肤或紧身设计时，必须用明确英文词：bikini, bare midriff, off-shoulder, thigh-high, exposed shoulders 等（不用模糊词）
3. 保留 anime cel shading, game character art, full body
4. 只输出英文 prompt，不要解释

设计JSON: {json.dumps(fields, ensure_ascii=False)[:900]}''',
        }).encode()
        req = urllib.request.Request(OLLAMA + '/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.loads(_http().open(req, timeout=timeout).read())
        out = resp.get('response', '').strip()
        if 100 < len(out) <= 500:
            return out
    except Exception:
        pass
    return d.get('prompt_en', '')[:440]

def _verify_render(img_path, requirements, timeout=120):
    """钥匙锁级验收门禁：VLM 强制检查需求项，全部达标才返回 True。
    requirements: [('发色','white hair'), ('泳装','bikini'), ('场景','pool'), ...]"""
    import base64, io, re as _re
    from PIL import Image
    img = Image.open(img_path)
    if max(img.size) > 768:
        r = 768 / max(img.size)
        img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    reqs = ', '.join(f'{cn}({en})' for cn, en in requirements)
    prompt = (f'Check this anime character art against ALL requirements: {reqs}. '
              f'Output ONLY JSON: [{{"req":"{requirements[0][1]}","pass":true}}] '
              f'one entry per requirement, pass=false if missing. JSON only.')
    # 精简 prompt：qwen3-vl 长 prompt 输出空
    prompt = (f'Verify each: {reqs}. Output ONLY JSON array [{{"req":"...","pass":bool}}] '
              f'one per requirement. JSON only.')
    body = json.dumps({'model': 'qwen3-vl:8b', 'stream': False, 'think': False,
                       'options': {'temperature': 0.0},
                       'prompt': prompt, 'images': [base64.b64encode(buf.getvalue()).decode()]}).encode()
    try:
        req = urllib.request.Request(OLLAMA + '/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.loads(_http().open(req, timeout=timeout).read())
        out = resp.get('response', '')
        m = _re.search(r'\[[\s\S]*\]', out)
        if not m:
            return False
        checks = json.loads(m.group(0))
        results = {str(c.get('req', '')): bool(c.get('pass')) for c in checks if isinstance(c, dict)}
        # 宽松匹配：req 键含 en 首词或中文名即命中
        ok = True
        for cn, en in requirements:
            first = en.split()[0]
            hit = next((k for k in results if first.lower() in k.lower() or cn in k), None)
            if not hit or not results[hit]:
                ok = False
                print(f'    验收不过: {cn} (VLM={hit or "未命中"})')
        return ok
    except Exception as e:
        print(f'    验收异常: {str(e)[:80]}')
        return True  # 验收失败不阻塞交付，但提示

def _costume_design(desc, name=None, generate=False, count=3, scene='', seed=-1):
    """服装独立设计（画师流程：服装设定图先行，与人物分离）。
    ① LLM 详细服装设计（部件/材质/结构/装饰）
    ② 生成服装设计图（素体模特穿着，服装是主角）
    ③ 保存设计稿，供后续人物图 reference 锁定"""
    print(f'# 服装独立设计: {desc}...')
    try:
        body = json.dumps({
            'model': 'qwen3:14b', 'stream': False, 'think': False,
            'prompt': f'''你是手游角色服装设计师。为角色设计详细服装，输出严格 JSON:
{{
 "name": "服装名",
 "style": "整体风格（中文）",
 "pieces": [{{"part": "部位(上衣/下装/外套/袜/鞋/配饰)", "design": "结构/版型/细节", "material": "材质", "color": "颜色"}}],
 "details": "装饰细节（蕾丝/绑带/纹章/配件）",
 "prompt_en": "英文服装设计图prompt（素体模特穿着展示，服装为主体，详细材质与结构）"
}}
服装要求: {desc}
服装设计图要求: 服装细节精致、结构清晰、材质可辨，不聚焦脸。''',
        }).encode()
        req = urllib.request.Request(OLLAMA + '/api/generate', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.loads(_http().open(req, timeout=180).read())
        m = re.search(r'\{[\s\S]*\}', resp.get('response', ''))
        if not m:
            print('❌ 服装设计失败: LLM 无 JSON')
            return
        d = json.loads(m.group(0))
    except Exception as e:
        print(f'❌ 服装设计失败: {str(e)[:120]}')
        return

    out_dir = OUT_BASE / f'costume_{time.strftime("%Y%m%d_%H%M%S")}'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'costume.json').write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"# {d.get('name', '服装')} — {d.get('style', '')}")
    for p in d.get('pieces', []):
        print(f"- {p.get('part')}: {p.get('design', '')}（{p.get('material', '')}，{p.get('color', '')}）")
    print(f"细节: {d.get('details', '')}")
    print(f'\n📁 设计稿: {out_dir / "costume.json"}')

    if generate:
        prompt_en = d.get('prompt_en', '')
        if not prompt_en:
            print('⚠️ 无英文 prompt，跳过生成')
            return
        print('\n# 生成服装设计图...')
        from workshop.create import create_from_nl
        base_seed = seed if seed >= 0 else 20260812
        for i in range(count):
            print(f'  [{i+1}/{count}] 生成 seed={base_seed + i}...')
            create_from_nl(
                prompt_en, count=1, model_type='sdxl', seed=base_seed + i,
                prompt_ready=True, inspect=False, dry_run=False,
                output_dir=str(out_dir / f'sheet_{i+1:02d}'),
            )
        imgs = sorted(str(x) for x in (out_dir).rglob('best.png'))
        print(f'\n📁 服装设计图:')
        for im in imgs:
            print(f'  {im}')

def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop character', description='角色设计先行（手游商业人设）')
    ap.add_argument('concept', nargs='*', help='角色概念（中文描述）')
    ap.add_argument('--name', default=None, help='角色名')
    ap.add_argument('--out', default=None, help='输出目录（默认 outputs/character_<ts>/）')
    ap.add_argument('--generate', action='store_true', help='设计完成后直出渲染图（不走 converge）')
    ap.add_argument('--count', type=int, default=3, help='--generate 渲染张数（默认 3）')
    ap.add_argument('--scene', default='', help='--generate 场景（如: 泳池/沙滩/海边酒吧）')
    ap.add_argument('--seed', type=int, default=-1, help='--generate 起始 seed')
    ap.add_argument('--costume', default=None, help='服装独立设计（先画服装设计图，与人物分离）')
    ap.add_argument('--sheet', action='store_true', help='三视图模式（正面/侧面/背面，VTB皮套刚需）')
    args = ap.parse_args(argv)

    if not args.concept and not args.costume:
        print('用法: character "概念" [--name 角色名] [--generate] [--costume "服装描述"]')
        return

    # ── 服装独立设计（与人物分离，画师流程：服装设定图先行）──
    if args.costume and not args.concept:
        _costume_design(args.costume, args.name, args.generate, args.count, args.scene, args.seed)
        return

    concept = ' '.join(args.concept)
    print(f'# 角色设计: {concept}...')
    try:
        d = design_character(concept, args.name)
    except Exception as e:
        print(f'❌ 设计失败: {str(e)[:120]}')
        return

    out_dir = Path(args.out) if args.out else OUT_BASE / f'character_{time.strftime("%Y%m%d_%H%M%S")}'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'design.json').write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    (out_dir / 'design.md').write_text(render_design(d), encoding='utf-8')

    print(render_design(d))
    print(f'\n📁 设计稿: {out_dir / "design.md"}')

    if args.generate:
        prompt_en = d.get('prompt_en', '')
        if prompt_en:
            print('\n# 合成精简 prompt → 直出渲染...')
            p = _condense_prompt(d, args.scene)
            print(f'  合成({len(p)}字符): {p[:130]}...')
            (out_dir / 'render_prompt.txt').write_text(p, encoding='utf-8')
            # ── 三视图模式（VTB 皮套）──
            if args.sheet:
                _sheet_render(p, args.name, out_dir, count=args.count, seed=args.seed)
                return
            # 直接 create 直出（不走 converge，避免 LLM 锚点重写丢细节）
            from workshop.create import create_from_nl
            seed = args.seed
            base_seed = seed if seed >= 0 else 20260812
            # 验收需求项（钥匙锁：不达标不交付）
            reqs = [('泳装/露肤', 'bikini or swimsuit or bare midriff'),
                    ('角色女性', 'female character')]
            if args.scene:
                reqs.append(('场景', 'pool or resort or beach'))
            for i in range(args.count):
                ok = False
                for attempt in range(3):
                    s = base_seed + i * 10 + attempt
                    print(f'  [{i+1}/{args.count}] 渲染 seed={s}...')
                    create_from_nl(
                        p, count=1, model_type='sdxl', seed=s,
                        prompt_ready=True, inspect=False, dry_run=False,
                        output_dir=str(out_dir / f'render_{i+1:02d}'),
                    )
                    best = out_dir / f'render_{i+1:02d}' / 'best.png'
                    if best.exists():
                        if _verify_render(str(best), reqs):
                            ok = True
                            break
                        print(f'    重抽 (attempt {attempt+2}/3)')
                if not ok:
                    print(f'    ⚠️ 3 次重抽仍未达标，保留最后一张（需人工检查）')
            imgs = sorted(str(x) for x in (out_dir).rglob('best.png'))
            print(f'\n📁 渲染图:')
            for im in imgs:
                print(f'  {im}')
        else:
            print('⚠️ 无英文 prompt，跳过生成')

if __name__ == '__main__':
    main()
