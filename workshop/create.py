"""
端到端创作管线 — "一句话出高质量图，自动质检，自动挑最好的"。

流程:
  NL 描述 → Prompt 引擎 → generate_with_quality × N → 逐张质检 → 排序选最优

用法 (CLI):
  python -m agents workshop create "银发少女校服教室窗边逆光" --count 6 --inspect
  python -m agents workshop create "prompt" --style anime --ref ref.png --count 4
  python -m agents workshop create "prompt" --ollama  # 使用 Ollama 优化 prompt
  python -m agents workshop create "prompt" --output ./my_create

返回:
  {
    "prompt": "优化后的提示词",
    "best": {"image": "路径", "score": 0.95, "inspect": {...}},
    "candidates": [{"image": "path", "inspect": {...}}, ...],
    "summary": "[脸:ok] [手:ok] [模糊:正常]",
  }
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.comfy_utils import (
    check_comfy_health,
    generate_with_quality,
    resolve_comfy_root,
)
from workshop.engine import nls_to_prompt, ref_analyze_to_prompt


def create_from_nl(
    nl_text: str,
    *,
    count: int = 4,
    style_hint: str | None = None,
    ref_path: str | None = None,
    preset: str | None = None,
    min_score: float = 0.0,
    retry: int = 0,
    no_validate: bool = False,
    inspect: bool = True,
    negative_prompt: str = "",
    seed: int = -1,
    dry_run: bool = False,
    use_ollama: bool = False,
    output_dir: str | None = None,
    verbose: bool = False,
    gallery_dir: str | None = None,
    clean: bool = False,
    ip_weight: float = 0.7,
    ip_balance: float = 0.5,
    lora_name: str | None = None,
    lora_strength: float = 1.0,
) -> dict[str, Any]:
    """自然语言描述 → 生成多张候选 → 质检排序 → 返回最优。

    Args:
        nl_text: 用户自然语言描述
        count: 生成候选数
        style_hint: 画风提示（anime/photoreal/cg/...）
        ref_path: 参考图路径（启用角色特征分析）
        preset: 质量预设
        min_score: 最低 CLIP 分
        retry: 最大重试次数
        no_validate: 跳过 CLIP 验证
        inspect: 是否执行逐部位质检
        negative_prompt: 负向提示词（不设置时使用风格预设默认值）
        seed: 起始种子（自动递增）
        dry_run: 预览模式
        use_ollama: 使用 Ollama 增强 prompt 生成
        output_dir: 结果输出目录（保存 metadata.json）
        verbose: 详细信息
        clean: 生成前清理输出目录旧文件

    Returns:
        {
            "prompt": "最终使用的提示词",
            "best": {...},
            "candidates": [...],
            "inspection_summary": "...",
        }
    """
    # 1. 检查 ComfyUI 状态
    if not dry_run:
        comfy_ok = check_comfy_health()
        if not comfy_ok:
            return {
                "prompt": nl_text,
                "best": {},
                "candidates": [],
                "error": "ComfyUI 未连接",
                "inspection_summary": "",
            }

    # 1b. 清理输出目录
    if clean and output_dir:
        out_path = Path(output_dir)
        if out_path.is_dir():
            import shutil
            gallery_path = out_path / "gallery"
            if gallery_path.is_dir():
                shutil.rmtree(str(gallery_path))
            for old in out_path.glob("*"):
                if old.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".json", ".html"}:
                    old.unlink()
            if verbose:
                print(f"🧹 已清理: {output_dir}/")

    # 2. 生成专业提示词
    ollama_avail = use_ollama

    if ref_path and Path(ref_path).is_file():
        analysis = ref_analyze_to_prompt(ref_path, nl_text, ollama_available=ollama_avail)
        final_prompt = analysis["prompt"]
        if verbose:
            print(f"📎 参考图分析: {analysis.get('character_desc', '')[:60]}...")
    else:
        final_prompt = nls_to_prompt(nl_text, style_hint=style_hint, ollama_available=ollama_avail)

    if verbose:
        print(f"📝 Prompt ({'Ollama' if ollama_avail else '模板'}): {final_prompt[:120]}...")

    # 2b. 负向提示词：用户指定优先，否则使用风格预设默认值
    if not negative_prompt:
        from workshop.engine.engine import _detect_style, STYLE_PRESETS
        detected = _detect_style(nl_text, style_hint)
        style_neg = STYLE_PRESETS.get(detected, {}).get("negative", "")
        # Ollama 路径的 negative 由模型自行处理，模板路径用预设
        if style_neg and not ollama_avail:
            negative_prompt = style_neg
        if verbose and negative_prompt:
            print(f"  ⛔ 负向: {negative_prompt[:80]}...")

    # 2c. 自动从 NL 文本检测负向关键词（追加到现有负向）
    from workshop.engine.engine import _detect_negative
    auto_neg = _detect_negative(nl_text)
    if auto_neg:
        if negative_prompt:
            negative_prompt += ", " + auto_neg
        else:
            negative_prompt = auto_neg
        if verbose:
            print(f"  🔍 自动负向: {auto_neg[:80]}")

    if dry_run:
        candidate_list = []
        for i in range(count):
            s = seed + i if seed > 0 else seed
            candidate_list.append({"seed": s, "image": "", "dry_run": True})

        result = {
            "prompt": final_prompt,
            "negative_prompt": negative_prompt,
            "best": candidate_list[0] if candidate_list else {},
            "candidates": candidate_list,
            "dry_run": True,
            "inspection_summary": "",
        }
        _maybe_save_output(result, output_dir)
        return result

    # 3. 生成多张候选
    from agents.go_flux import build_flux_workflow

    candidates: list[dict[str, Any]] = []
    comfy_root = resolve_comfy_root()
    had_errors = False

    for i in range(count):
        s = seed + i if seed > 0 else -1
        print(f"\r  [{i+1}/{count}] 生成中 seed={s}...", end="", flush=True)

        try:
            qr = generate_with_quality(
                build_flux_workflow, final_prompt,
                preset=preset,
                min_score=min_score,
                max_retries=retry,
                no_validate=no_validate,
                seed=s,
                negative_prompt=negative_prompt,
                filename_prefix=f"create_{i:02d}",
                ref_image=ref_path,
                ip_weight=ip_weight,
                ip_balance=ip_balance,
                lora_name=lora_name,
                lora_strength=lora_strength,
            )
        except Exception as exc:
            had_errors = True
            print(f"\r  [{i+1}/{count}] ❌ seed={s}: {exc}")
            candidates.append({
                "seed": s,
                "image": "",
                "score": -1,
                "error": str(exc),
                "retries": 0,
            })
            continue

        # 提取图片路径
        image_path = ""
        for img_entry in qr.get("images", []):
            if isinstance(img_entry, str):
                # 绝对路径格式（generate_with_quality 返回）
                p = Path(img_entry)
                if p.is_file():
                    image_path = str(p.resolve())
                    break
            else:
                # 旧格式 (subfolder, name) tuple — 兼容
                try:
                    sub, name = img_entry
                    p = comfy_root / "output" / sub / name
                    if p.is_file():
                        image_path = str(p.resolve())
                        break
                except (ValueError, TypeError):
                    pass

        candidate = {
            "seed": qr.get("seed", 0),
            "image": image_path,
            "score": qr.get("score", -1),
            "retries": qr.get("retries", 0),
        }
        candidates.append(candidate)

        score_str = f"score={candidate['score']:.2f}" if candidate['score'] >= 0 else "score=?"
        img_tag = "✅" if image_path else "❌"
        print(f"\r  [{i+1}/{count}] {img_tag} seed={candidate['seed']} {score_str}  ")

    # 4. 逐张质检
    if inspect and candidates:
        if verbose:
            print(f"  🔍 质检 {len(candidates)} 张...")
        else:
            print()
        for c in candidates:
            if c.get("error"):
                c["inspect"] = {"status": "error", "error": c["error"]}
            elif c["image"] and Path(c["image"]).is_file():
                from workshop.inspect import inspect_image
                try:
                    ir = inspect_image(c["image"], prompt=final_prompt, use_mediapipe=False)
                    c["inspect"] = ir
                except Exception as exc:
                    c["inspect"] = {"status": "error", "error": str(exc)}
            else:
                c["inspect"] = {"status": "error", "error": "无图片"}

    # 5. 排序选最优
    def _rank_key(c: dict[str, Any]) -> tuple:
        ins = c.get("inspect", {})
        no_inspect = 1 if ins.get("status") == "error" else 0
        insp_score = ins.get("scores", {}).get("overall", 0.5) if ins else 0.5
        clip = c.get("score", 0)
        if clip < 0:
            clip = 0
        combined = insp_score * 0.5 + clip * 0.5
        return (no_inspect, -combined)

    candidates.sort(key=_rank_key)

    best = candidates[0] if candidates else {}
    summary = best.get("inspect", {}).get("summary", "")

    result = {
        "prompt": final_prompt,
        "negative_prompt": negative_prompt,
        "best": best,
        "candidates": candidates,
        "inspection_summary": summary,
        "had_errors": had_errors,
        "ref_image": ref_path,
        "ip_weight": ip_weight,
        "ip_balance": ip_balance,
    }

    _maybe_save_output(result, output_dir)
    _register_output(result)  # 自动注册到产出管理系统

    # 生成 gallery HTML
    if gallery_dir and result.get("candidates"):
        gallery_path = _generate_gallery_html(result, gallery_dir)
        if gallery_path:
            print(f"  🖼️  Gallery: {gallery_path}")

    return result


def _maybe_save_output(result: dict[str, Any], output_dir: str | None, extra_meta: dict[str, Any] | None = None) -> None:
    """如指定 output_dir，保存结构化的结果元数据到 JSON + 复制最优图。

    Args:
        result: create_from_nl() 的完整结果
        output_dir: 输出目录路径
        extra_meta: 额外元数据（如引擎推测信息），由调用方补充
    """
    if not output_dir:
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 逐候选摘要（不保存图片路径，仅存储轻量信息）
    candidates_info = []
    for c in result.get("candidates", []):
        ins = c.get("inspect", {})
        candidates_info.append({
            "seed": c.get("seed", 0),
            "score": c.get("score", -1),
            "retries": c.get("retries", 0),
            "error": c.get("error"),
            "inspect_status": ins.get("status", ""),
            "inspect_overall": ins.get("scores", {}).get("overall", 0) if ins else 0,
            "inspect_summary": ins.get("summary", ""),
        })

    # 保存 JSON 元数据
    from agents import __version__ as pipeline_version
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "version": pipeline_version,
        "prompt": result.get("prompt", ""),
        "negative_prompt": result.get("negative_prompt", ""),
        "candidates_count": len(result.get("candidates", [])),
        "ref_image": result.get("ref_image"),
        "ip_weight": result.get("ip_weight"),
        "ip_balance": result.get("ip_balance"),
        "best": {
            "seed": result.get("best", {}).get("seed", 0),
            "score": result.get("best", {}).get("score", -1),
            "image_relative": "",
            "inspect": _summarize_inspect(result.get("best", {}).get("inspect", {})),
        },
        "candidates": candidates_info,
    }

    # 合并额外元数据（如引擎推测）
    if extra_meta:
        meta.update(extra_meta)

    # 复制最优图
    best_img = result.get("best", {}).get("image", "")
    if best_img and Path(best_img).is_file():
        import shutil
        dest = out / "best.png"
        shutil.copy2(best_img, str(dest))
        meta["best"]["image_relative"] = "best.png"

    (out / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _register_output(result: dict[str, Any]) -> None:
    """将 create 结果自动注册到 output_manager（支持 python -m agents outputs list 查看）。"""
    best = result.get("best", {})
    img_path = best.get("image", "")
    if not img_path or not Path(img_path).is_file():
        return

    try:
        from agents.output_manager import save_run

        metadata = {
            "prompt": result.get("prompt", ""),
            "inspection_summary": result.get("inspection_summary", ""),
            "candidates": len(result.get("candidates", [])),
        }
        save_run("workshop-create", [img_path], metadata)
    except Exception:
        pass  # output_manager 不可用时静默跳过


def _generate_gallery_html(result: dict[str, Any], output_dir: str) -> str:
    """生成全候选 HTML 画廊（self-contained），返回输出路径。

    候选按综合分降序排列（最优在前），引擎推测信息显示在页面标题区。
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    candidates = result.get("candidates", [])
    best_img = result.get("best", {}).get("image", "")

    # 复制所有候选图到 gallery 目录
    images: list[dict[str, Any]] = []
    for i, c in enumerate(candidates):
        src = c.get("image", "")
        if not src or not Path(src).is_file():
            images.append({"file": "", "error": True, "seed": c.get("seed", "?")})
            continue
        ext = Path(src).suffix or ".png"
        dest = out / f"candidate_{i:02d}{ext}"
        try:
            import shutil
            shutil.copy2(src, str(dest))
        except Exception:
            pass
        is_best = (src == best_img)
        ins = c.get("inspect", {})
        ins_scores = ins.get("scores", {}) if ins else {}
        images.append({
            "file": dest.name,
            "seed": c.get("seed", "?"),
            "score": c.get("score", -1),
            "summary": ins.get("summary", ""),
            "overall": ins_scores.get("overall", 0),
            "parts": {k: v for k, v in ins_scores.items() if k != "overall"},
            "best": is_best,
            "error": False,
        })

    # 按综合分降序排序（最优在前）
    images.sort(key=lambda x: (x.get("best", False), x.get("error", True), -x.get("overall", 0)))

    # 引擎推测信息（可选）
    prompt_escaped = result.get("prompt", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    negative = result.get("negative_prompt", "")
    negative_escaped = negative.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    summary = result.get("inspection_summary", "")
    rows_html = ""

    # 引擎推测信息（可选）
    engine = result.get("engine_detection", {})
    engine_html = ""
    if engine:
        style_str = engine.get("style", "")
        comp_str = engine.get("composition", "")
        light_str = engine.get("lighting", "")
        auto_neg = engine.get("auto_negative", "")
        parts = [f"🎨 风格: {style_str}", f"📐 构图: {comp_str[:30]}", f"💡 光照: {light_str[:30]}"]
        if auto_neg:
            parts.append(f"⛔ 自动负向: {auto_neg[:30]}")
        engine_html = '<div class="engine">' + " · ".join(parts) + "</div>"

    # 参考图展示（可选）
    ref_path = result.get("ref_image")
    ref_html = ""
    if ref_path:
        ref_rel = Path(ref_path).name
        try:
            import shutil
            ref_dest = out / ref_rel
            shutil.copy2(ref_path, str(ref_dest))
            iw = result.get("ip_weight", 0.7)
            ib = result.get("ip_balance", 0.5)
            ref_html = f'''
<div class="ref-section">
  <div class="ref-label">📎 参考图 · 权重 {iw} · 平衡 {ib}</div>
  <img src="{ref_rel}" class="ref-img" onclick="window.open('{ref_rel}','_blank')"/>
</div>'''
        except Exception:
            pass
    # Build JS images array for keyboard navigation
    js_images: list[str] = []
    for _rank, img in enumerate(images, 1):
        if not img.get("error") and img.get("file"):
            js_images.append(img["file"])
    import json
    js_parts = json.dumps([{k: v for k, v in img.items() if k in ("parts", "overall")} for img in images])
    js_ref_image = json.dumps(ref_rel) if ref_path else "null"

    for _rank, img in enumerate(images, 1):
        if img.get("error"):
            rows_html += f"""\n<div class="card error">
  <div class="img-placeholder">❌ #{_rank} seed={img['seed']}</div>
  <div class="info">seed: {img['seed']} <span class="badge error-badge">ERROR</span></div>
</div>"""
            continue
        best_class = " best" if img.get("best") else ""
        score_tag = f"<span class='score'>CLIP: {img['score']:.2f}</span>" if img.get("score", -1) >= 0 else ""
        summary_tag = f"<span class='summary'>{img['summary']}</span>" if img.get("summary") else ""
        overall_tag = f"<span class='overall'>综合: {img.get('overall', 0):.2f}</span>" if img.get('overall', 0) > 0 else ""
        best_badge = " <span class='badge best-badge'>🏆 最优</span>" if img.get("best") else ""
        copy_btn = f"<span class='copy-seed' onclick='navigator.clipboard.writeText(\"{img['seed']}\");this.textContent=\"✅\"'>📋</span>" if img.get("seed") != "?" else ""
        parts = img.get("parts", {})
        parts_tags = ""
        if parts:
            part_map = {"脸": "Face", "左眼": "L-Eye", "右眼": "R-Eye", "手": "Hand", "脚": "Foot", "模糊": "Blur"}
            score_bar = ""
            for pk, pv in parts.items():
                pname = part_map.get(pk, pk[:4])
                bar_w = int(pv * 60)
                bar_cls = "bar-ok" if pv >= 0.8 else "bar-warn" if pv >= 0.3 else "bar-bad"
                score_bar += f'<span class="sbar"><span class="sbar-label">{pname}</span><span class="sbar-track"><span class="sbar-fill {bar_cls}" style="width:{bar_w}px"></span></span><span class="sbar-val">{pv:.1f}</span></span>'
            parts_tags = f'<div class="score-bar">{score_bar}</div>'
        file_name = img.get("file", "")
        nav_idx = js_images.index(file_name) if file_name in js_images else -1
        onclick = f"openModal({nav_idx})" if nav_idx >= 0 else "this.classList.remove('show')"
        rows_html += f"""\n<div class="card{best_class}">
  <img src="{img['file']}" loading="lazy" onclick="{onclick}" />
  <div class="info">#{_rank} · seed: {img['seed']} {copy_btn} {score_tag} {overall_tag} {summary_tag}{best_badge}</div>
  {parts_tags}
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>创作工坊 · Gallery</title>
<style>
:root, .dark{{--bg:#1a1a2e;--fg:#eee;--card:#16213e;--prompt:#999;--neg:#d4a5a5;--prompt-bg:#16213e;--neg-bg:#1f1f35;--engine:#7ec8e3;--engine-bg:#1f1f35;--summary:#aaa;--best:#e8a87c;--best-shadow:rgba(232,168,124,.3);--score:#7ec8e3;--overall:#a8e6cf;--summary-color:#d4a5a5;--heading:#e8a87c;--ref-label:#7ec8e3;--error:#666;--placeholder:#555;--modal-bg:rgba(0,0,0,.9);--dl-bg:rgba(0,0,0,.6);--dl-color:#eee;--dl-border:rgba(255,255,255,.2);--dl-hover:rgba(80,80,80,.8);--counter-bg:rgba(0,0,0,.6);--zoom-bg:rgba(0,0,0,.7)}}
.light{{--bg:#f5f5f7;--fg:#1d1d1f;--card:#ffffff;--prompt:#555;--neg:#b91c1c;--prompt-bg:#f0f0f2;--neg-bg:#fee2e2;--engine:#0369a1;--engine-bg:#e0f2fe;--summary:#666;--best:#d97706;--best-shadow:rgba(217,119,6,.2);--score:#0369a1;--overall:#059669;--summary-color:#b91c1c;--heading:#d97706;--ref-label:#0369a1;--error:#999;--placeholder:#ccc;--modal-bg:rgba(255,255,255,.95);--dl-bg:rgba(255,255,255,.8);--dl-color:#333;--dl-border:rgba(0,0,0,.2);--dl-hover:rgba(200,200,200,.9);--counter-bg:rgba(0,0,0,.5);--zoom-bg:rgba(0,0,0,.5)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--fg);font-family:system-ui,sans-serif;padding:20px}}
h1{{font-size:1.5rem;margin-bottom:8px;color:var(--heading)}}
.toolbar{{display:flex;gap:8px;align-items:center;margin-bottom:8px}}
.theme-btn{{background:var(--card);color:var(--fg);border:1px solid var(--fg);border-radius:6px;padding:4px 10px;font-size:.8rem;cursor:pointer;opacity:.7}}
.theme-btn:hover{{opacity:1}}
.prompt{{color:var(--prompt);font-size:.85rem;margin-bottom:8px;padding:10px;background:var(--prompt-bg);border-radius:8px;word-break:break-all}}
.negative{{color:var(--neg);font-size:.82rem;margin-bottom:4px;padding:4px 10px;background:var(--neg-bg);border-radius:6px;word-break:break-all}}
.engine{{color:var(--engine);font-size:.82rem;margin-bottom:12px;padding:4px 10px;background:var(--engine-bg);border-radius:6px}}
.summary-row{{margin-bottom:16px;font-size:.9rem;color:var(--summary)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
.card{{background:var(--card);border-radius:10px;overflow:hidden;border:2px solid transparent;transition:transform .15s}}
.card:hover{{transform:translateY(-2px)}}
.card.best{{border-color:var(--best);box-shadow:0 0 12px var(--best-shadow)}}
.card img{{width:100%;height:auto;display:block;cursor:pointer}}
.card.error{{padding:20px;text-align:center;color:var(--error)}}
.img-placeholder{{font-size:2rem;padding:40px 0;color:var(--placeholder)}}
.info{{padding:8px 10px;font-size:.8rem;display:flex;flex-wrap:wrap;gap:4px;align-items:center}}
.parts{{padding:0 10px 8px;display:flex;flex-wrap:wrap;gap:3px}}
.part{{padding:1px 6px;border-radius:4px;font-size:.72rem;font-weight:600}}
.p-ok{{background:#1a3a2a;color:#4ade80}}
.p-warn{{background:#3a3a1a;color:#facc15}}
.p-bad{{background:#3a1a1a;color:#f87171}}
.score{{color:var(--score)}}
.overall{{color:var(--overall)}}
.summary{{color:var(--summary-color)}}
.badge{{font-size:.7rem;padding:2px 6px;border-radius:4px}}
.best-badge{{background:#e8a87c33;color:var(--best)}}
.error-badge{{background:#ff444433;color:#ff4444}}
.copy-seed{{cursor:pointer;font-size:.85rem;padding:0 4px;user-select:none;opacity:.6}}
.copy-seed:hover{{opacity:1}}
.sort-note{{font-size:.75rem;color:var(--summary);margin-left:8px}}
/* score bar */
.score-bar{{display:flex;flex-wrap:wrap;gap:2px 6px;padding:4px 10px 6px}}
.sbar{{display:inline-flex;align-items:center;gap:2px;font-size:.68rem}}
.sbar-label{{color:var(--summary);min-width:28px}}
.sbar-track{{display:inline-block;width:60px;height:6px;background:var(--card);border-radius:3px;overflow:hidden}}
.sbar-fill{{height:100%;border-radius:3px;transition:width .3s}}
.bar-ok{{background:#4ade80}}
.bar-warn{{background:#facc15}}
.bar-bad{{background:#f87171}}
.sbar-val{{color:var(--summary);min-width:20px}}
.ref-section{{margin-bottom:16px;padding:10px;background:var(--card);border-radius:8px;text-align:center}}
.ref-label{{font-size:.82rem;color:var(--ref-label);margin-bottom:6px}}
.ref-img{{max-height:180px;border-radius:6px;cursor:pointer;border:1px solid var(--fg);opacity:.8}}
.ref-img:hover{{opacity:1}}
/* modal */
#modal{{display:none;position:fixed;inset:0;z-index:1000;background:var(--modal-bg);cursor:zoom-out;align-items:center;justify-content:center}}
#modal.show{{display:flex}}
#modal-zoom-container{{display:flex;align-items:center;justify-content:center;width:100%;height:100%;overflow:hidden;cursor:zoom-in}}
#modal-zoom-inner{{position:relative;transition:transform .1s ease;transform-origin:center center;will-change:transform}}
#modal-zoom-inner img{{display:block;max-width:95vw;max-height:95vh;object-fit:contain;border-radius:4px;user-select:none;-webkit-user-drag:none}}
#modal-overlay{{position:absolute;inset:0;pointer-events:none}}
.ov-badge{{position:absolute;padding:2px 6px;border-radius:4px;font-size:.72rem;font-weight:600;transform:translate(-50%,-50%);white-space:nowrap}}
.ov-ok{{background:#1a3a2acc;color:#4ade80;border:1px solid #4ade8080}}
.ov-warn{{background:#3a3a1acc;color:#facc15;border:1px solid #facc1580}}
.ov-bad{{background:#3a1a1acc;color:#f87171;border:1px solid #f8717180}}
.ov-ov{{background:#1a2a3acc;color:#7ec8e3;border:1px solid #7ec8e380;transform:none}}
#modal-zoom-level{{position:fixed;bottom:70px;left:50%;transform:translateX(-50%);background:var(--zoom-bg);color:var(--fg);padding:2px 10px;border-radius:8px;font-size:.75rem;display:none;pointer-events:none}}
#modal-counter{{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);background:var(--counter-bg);color:var(--fg);padding:4px 14px;border-radius:12px;font-size:.82rem;pointer-events:none}}
#modal-dl{{position:fixed;top:20px;right:20px;background:var(--dl-bg);color:var(--dl-color);text-decoration:none;padding:6px 14px;border-radius:8px;font-size:1.1rem;cursor:pointer;z-index:1001;border:1px solid var(--dl-border);transition:background .15s}}
#modal-dl:hover{{background:var(--dl-hover)}}
#modal-slide-status{{position:fixed;top:20px;left:20px;background:var(--dl-bg);color:var(--dl-color);padding:4px 12px;border-radius:8px;font-size:.78rem;display:none;pointer-events:none}}
#modal-compare-btn{{position:fixed;top:20px;left:90px;background:var(--dl-bg);color:var(--dl-color);border:1px solid var(--dl-border);padding:4px 12px;border-radius:8px;font-size:.78rem;cursor:pointer;display:none;z-index:1001;transition:background .15s}}
#modal-compare-btn:hover{{background:var(--dl-hover)}}
#modal-compare-overlay{{position:absolute;inset:0;background-size:cover;background-position:center;opacity:0;pointer-events:none;transition:opacity .3s;border-radius:4px}}
#modal-compare-overlay.show{{opacity:0.4}}
</style></head>
<body class="dark">
<div class="toolbar">
  <h1>🖼️ 创作工坊 · Gallery</h1>
  <button class="theme-btn" onclick="toggleTheme()" title="切换主题">☀️</button>
</div>
{ref_html}
<div class="prompt">{prompt_escaped}</div>
{('<div class="negative">⛔ 负向: ' + negative_escaped + '</div>') if negative else ''}
{engine_html}
<div class="summary-row">{f'质检: {summary}' if summary else ''} · 共 {len(images)} 张<span class="sort-note" title="按综合分降序 · 🏆 最优在前">  已排序</span></div>
<div class="grid">{rows_html}</div>
|<div id="modal" onclick="closeModal(event)">
|  <div id="modal-counter"></div>
|  <div id="modal-zoom-container" ondblclick="resetZoom()">
|    <div id="modal-zoom-inner">
|      <img id="modal-img" src="" alt="" draggable="false"/>
|      <div id="modal-overlay"></div>
|    </div>
|  </div>
<a id="modal-dl" href="#" download="gallery.png" onclick="event.stopPropagation();" title="下载当前图片">⬇</a>
<div id="modal-zoom-level"></div>
<div id="modal-slide-status">▶ 播放中</div>
<button id="modal-compare-btn" onclick="toggleCompare()" title="对比参考图 (C)">🔍 对比</button>
</div>
|<script>
|var images = {js_images};
|var partsData = {js_parts};
|var refImage = {js_ref_image};
|var currentIdx = -1;
|var zoom = 1, panX = 0, panY = 0, isPanning = false, startX, startY;
|var container = document.getElementById('modal-zoom-container');
|var inner = document.getElementById('modal-zoom-inner');
|var mImg = document.getElementById('modal-img');
|var overlay = document.getElementById('modal-overlay');
|var zoomLevel = document.getElementById('modal-zoom-level');
|var compareBtn = document.getElementById('modal-compare-btn');
|var compareShown = false;
|if (refImage) compareBtn.style.display = 'block';
|
|function toggleCompare(){{
|    compareShown = !compareShown;
|    compareBtn.textContent = compareShown ? '🔍 原图' : '🔍 对比';
|    if (compareShown) {{
|        inner.style.backgroundImage = 'url(' + refImage + ')';
|        inner.style.backgroundSize = 'contain';
|        inner.style.backgroundRepeat = 'no-repeat';
|        inner.style.backgroundPosition = 'center';
|        mImg.style.opacity = '0.5';
|    }} else {{
|        inner.style.backgroundImage = '';
|        mImg.style.opacity = '1';
|    }}
|}}
|
function closeModal(e){{
    if (e.target === e.currentTarget || e.target.id === 'modal-img' || e.target.id === 'modal-zoom-container' || e.target.id === 'modal-zoom-inner') {{
        document.getElementById('modal').classList.remove('show');
        currentIdx = -1; resetZoom(); resetCompare();
    }}
}}
function openModal(idx){{
    currentIdx = idx; resetZoom(); resetCompare();
    mImg.src = images[idx];
|    document.getElementById('modal').classList.add('show');
|    updateCounter(); updateDownload(); updateOverlay();
|}}
|function updateCounter(){{
|    var c = document.getElementById('modal-counter');
|    if (currentIdx >= 0 && images.length > 1) {{
|        c.textContent = (currentIdx + 1) + ' / ' + images.length + ' ← →';
|        c.style.display = 'block';
|    }} else {{ c.style.display = 'none'; }}
|}}
|function updateDownload(){{
|    var dl = document.getElementById('modal-dl');
|    if (currentIdx >= 0 && images[currentIdx]) {{
|        dl.href = images[currentIdx];
|        dl.download = images[currentIdx].split('/').pop() || 'gallery.png';
|        dl.style.display = 'block';
|    }} else {{ dl.style.display = 'none'; }}
|}}
|function updateOverlay(){{
|    overlay.innerHTML = '';
|    if (currentIdx < 0 || !partsData[currentIdx]) return;
|    var p = partsData[currentIdx].parts || {{}};
|    var parts_list = [
|        ['Face', 0.5, 0.2], ['L-Eye', 0.35, 0.3], ['R-Eye', 0.65, 0.3],
|        ['Hand', 0.5, 0.7], ['Foot', 0.5, 0.85], ['Blur', 0.85, 0.05]
|    ];
|    parts_list.forEach(function(item){{
|        var key = item[0], x = item[1], y = item[2];
|        var val = p[key];
|        if (val === undefined) return;
|        var badge = document.createElement('span');
|        badge.className = 'ov-badge ' + (val >= 0.8 ? 'ov-ok' : val >= 0.3 ? 'ov-warn' : 'ov-bad');
|        badge.textContent = key + ' ' + val.toFixed(1);
|        badge.style.left = (x * 100) + '%'; badge.style.top = (y * 100) + '%';
|        overlay.appendChild(badge);
|    }});
|    var ov = partsData[currentIdx].overall || 0;
|    if (ov > 0) {{
|        var ob = document.createElement('span');
|        ob.className = 'ov-badge ov-ov';
|        ob.textContent = '综合 ' + ov.toFixed(2);
|        ob.style.left = '3%'; ob.style.top = '3%';
|        overlay.appendChild(ob);
|    }}
|}}
|// Zoom & Pan
|function applyTransform(){{
|    inner.style.transform = 'scale(' + zoom + ') translate(' + panX + 'px,' + panY + 'px)';
|    zoomLevel.textContent = (zoom * 100).toFixed(0) + '%';
|    zoomLevel.style.display = zoom > 1 ? 'block' : 'none';
|}}
function resetZoom(){{
    zoom = 1; panX = 0; panY = 0; applyTransform();
}}
function resetCompare(){{
    if (compareShown) toggleCompare();
}}
|container.addEventListener('wheel', function(e){{
|    e.preventDefault();
|    var delta = e.deltaY > 0 ? -0.1 : 0.1;
|    zoom = Math.max(0.5, Math.min(10, zoom + delta));
|    applyTransform();
|}});
|container.addEventListener('mousedown', function(e){{
|    if (zoom > 1) {{ isPanning = true; startX = e.clientX - panX; startY = e.clientY - panY; inner.style.cursor = 'grabbing'; }}
|}});
|window.addEventListener('mousemove', function(e){{
|    if (!isPanning) return;
|    panX = e.clientX - startX; panY = e.clientY - startY;
|    inner.style.transform = 'scale(' + zoom + ') translate(' + panX + 'px,' + panY + 'px)';
|}});
|window.addEventListener('mouseup', function(){{
|    isPanning = false; inner.style.cursor = 'default';
|}});
// Theme toggle
function toggleTheme(){{
    var b = document.body;
    if (b.className === 'dark') {{
        b.className = 'light'; localStorage.setItem('gallery-theme', 'light');
    }} else {{
        b.className = 'dark'; localStorage.setItem('gallery-theme', 'dark');
    }}
}}
(function(){{
    var t = localStorage.getItem('gallery-theme');
    if (t) document.body.className = t;
    document.querySelector('.theme-btn').textContent = t === 'light' ? '🌙' : '☀️';
}})();
// Slideshow
var slideTimer = null;
function toggleSlide(){{
    if (slideTimer) {{ clearInterval(slideTimer); slideTimer = null; document.getElementById('modal-slide-status').style.display = 'none'; return; }}
    if (currentIdx < 0 || images.length < 2) return;
    document.getElementById('modal-slide-status').style.display = 'block';
    slideTimer = setInterval(function(){{
        if (currentIdx < images.length - 1) {{
            currentIdx++; mImg.src = images[currentIdx]; resetZoom();
            updateCounter(); updateDownload(); updateOverlay();
        }} else {{
            clearInterval(slideTimer); slideTimer = null;
            document.getElementById('modal-slide-status').style.display = 'none';
        }}
    }}, 3000);
}}
// Update keyboard nav to support slideshow
document.addEventListener('keydown', function(e){{
    if (currentIdx < 0) return;
    if (e.key === ' ') {{ e.preventDefault(); toggleSlide(); return; }}
    if (e.key === 'c' || e.key === 'C') {{ e.preventDefault(); if (refImage) toggleCompare(); return; }}
    if (e.key === 'ArrowLeft' && currentIdx > 0) {{
        if (slideTimer) toggleSlide();
        currentIdx--; mImg.src = images[currentIdx]; resetZoom();
        updateCounter(); updateDownload(); updateOverlay(); e.preventDefault();
    }} else if (e.key === 'ArrowRight' && currentIdx < images.length - 1) {{
        if (slideTimer) toggleSlide();
        currentIdx++; mImg.src = images[currentIdx]; resetZoom();
        updateCounter(); updateDownload(); updateOverlay(); e.preventDefault();
    }} else if (e.key === 'Escape') {{
        if (slideTimer) toggleSlide();
        document.getElementById('modal').classList.remove('show');
        currentIdx = -1; resetZoom();
    }}
}});
|</script>
</body></html>"""

    gallery_file = out / "index.html"
    gallery_file.write_text(html, encoding="utf-8")
    return str(gallery_file.resolve())


def _summarize_inspect(ins: dict[str, Any]) -> dict[str, Any]:
    """压缩质检结果，只保留关键信息。"""
    if not ins:
        return {}
    return {
        "status": ins.get("status", "?"),
        "summary": ins.get("summary", ""),
        "overall": ins.get("scores", {}).get("overall", 0),
    }


def _make_slug(text: str, max_len: int = 16) -> str:
    """从文本中提取短 slug（用于子目录名）。"""
    import re
    cleaned = re.sub(r'[\\/:*?"<>|]', "", text).strip()
    # 取前 max_len 个字符
    return cleaned[:max_len] or "prompt"


def create_batch(
    prompts_file: str,
    *,
    dry_run: bool = False,
    count: int = 4,
    style_hint: str | None = None,
    ref_path: str | None = None,
    preset: str | None = None,
    min_score: float = 0.0,
    retry: int = 0,
    no_validate: bool = False,
    inspect: bool = True,
    seed: int = 0,
    negative_prompt: str = "",
    use_ollama: bool = False,
    output_dir: str | None = None,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """从文本文件批量执行多条 prompt 的完整创作管线。

    Args:
        prompts_file: 文件路径，每行一条 prompt（空行和 # 注释行跳过）
        其余参数同 create_from_nl，共享给每条 prompt。

    Returns:
        每条 prompt 的结果列表（含 prompt_text + error 字段）。
    """
    # 1. 解析文件
    fp = Path(prompts_file)
    if not fp.is_file():
        print(f"❌ 批量文件不存在: {prompts_file}")
        return []

    lines = fp.read_text(encoding="utf-8").splitlines()
    prompts = []  # list of (prompt_text, ref_path_or_none)
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 支持 "prompt | ref_path" 格式
        if "|" in stripped:
            parts = stripped.split("|", 1)
            p_text = parts[0].strip()
            p_ref = parts[1].strip()
            prompts.append((p_text, p_ref if p_ref else None))
        else:
            prompts.append((stripped, None))

    if not prompts:
        print("❌ 批量文件中没有有效的 prompt")
        return []

    total = len(prompts)
    print(f"\n{'='*60}")
    print(f"📦 批量管线: {total} 条 prompt")
    print(f"{'='*60}")

    # 2. 准备输出目录
    batch_root = Path(output_dir) if output_dir else Path.cwd() / "_batch_output"
    batch_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0

    for idx, (prompt_text, prompt_ref) in enumerate(prompts, start=1):
        slug = _make_slug(prompt_text)
        sub_dir = str(batch_root / f"{idx:03d}_{slug}")
        print(f"\n[{idx}/{total}] 📝 {prompt_text[:60]}{'...' if len(prompt_text) > 60 else ''}")
        if prompt_ref:
            print(f"      ┗ 📎 ref: {prompt_ref}")
        print(f"      ┗ 📁 {sub_dir}")

        try:
            result = create_from_nl(
                prompt_text,
                count=count,
                style_hint=style_hint,
                ref_path=prompt_ref or ref_path,
                preset=preset,
                min_score=min_score,
                retry=retry,
                no_validate=no_validate,
                inspect=inspect,
                dry_run=dry_run,
                seed=seed,
                negative_prompt=negative_prompt,
                use_ollama=use_ollama,
                output_dir=sub_dir,
                verbose=verbose,
            )

            has_error = result.get("error") or result.get("had_errors")
            status = "❌" if has_error else "✅"
            ok_count += 0 if has_error else 1
            fail_count += 1 if has_error else 0

            best = result.get("best", {})
            best_seed = best.get("seed", "?")
            best_score = best.get("score", -1)
            score_str = f"score={best_score:.2f}" if best_score >= 0 else "score=?"
            candidates = result.get("candidates", [])
            print(f"      ┗ {status} best=seed={best_seed} {score_str}  |  候选 {len(candidates)} 张")

            result["prompt_text"] = prompt_text
            result["output_dir"] = sub_dir
            results.append(result)

        except Exception as exc:
            fail_count += 1
            print(f"      ┗ ❌ 异常: {exc}")
            results.append({
                "prompt_text": prompt_text,
                "error": str(exc),
                "best": {},
                "candidates": [],
            })

    # 3. 批量汇总
    print(f"\n{'='*60}")
    print(f"📊 批量汇总: {total} 条 | ✅ {ok_count} 成功 | ❌ {fail_count} 失败")
    for idx, (pt, r) in enumerate(zip(prompts, results), start=1):
        prompt_text = pt[0] if isinstance(pt, tuple) else pt
        has_err = r.get("error") or r.get("had_errors")
        best = r.get("best", {})
        seed = best.get("seed", "?")
        score = best.get("score", -1)
        score_s = f"score={score:.2f}" if score >= 0 else "score=?"
        print(f"  [{idx}/{total}] {'✅' if not has_err else '❌'} {prompt_text[:50]} → seed={seed} {score_s}")
    print(f"{'='*60}\n")

    # 4. 保存批量元数据
    batch_meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total": total,
        "success": ok_count,
        "fail": fail_count,
        "prompts": [
            {
                "text": r.get("prompt_text", ""),
                "output_dir": r.get("output_dir", ""),
                "best_seed": r.get("best", {}).get("seed", 0),
                "best_score": r.get("best", {}).get("score", -1),
                "error": r.get("error"),
            }
            for r in results
        ],
    }
    (batch_root / "batch_metadata.json").write_text(
        json.dumps(batch_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  📁 批量元数据: {batch_root / 'batch_metadata.json'}")

    # 5. 注册到产出管理系统（仅成功的）
    for r in results:
        if not r.get("error") and not r.get("had_errors"):
            _register_output(r)

    return results
