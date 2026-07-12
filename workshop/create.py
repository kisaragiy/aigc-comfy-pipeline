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
    seed: int = -1,
    dry_run: bool = False,
    use_ollama: bool = False,
    output_dir: str | None = None,
    verbose: bool = False,
    gallery_dir: str | None = None,
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
        seed: 起始种子（自动递增）
        dry_run: 预览模式
        use_ollama: 使用 Ollama 增强 prompt 生成
        output_dir: 结果输出目录（保存 metadata.json）
        verbose: 详细信息

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

    if dry_run:
        candidate_list = []
        for i in range(count):
            s = seed + i if seed > 0 else seed
            candidate_list.append({"seed": s, "image": "", "dry_run": True})

        result = {
            "prompt": final_prompt,
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
                filename_prefix=f"create_{i:02d}",
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
        for sub, name in qr.get("images", []):
            p = comfy_root / "output" / sub / name
            if p.is_file():
                image_path = str(p.resolve())
                break

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
        "best": best,
        "candidates": candidates,
        "inspection_summary": summary,
        "had_errors": had_errors,
    }

    _maybe_save_output(result, output_dir)
    _register_output(result)  # 自动注册到产出管理系统

    # 生成 gallery HTML
    if gallery_dir and result.get("candidates"):
        gallery_path = _generate_gallery_html(result, gallery_dir)
        if gallery_path:
            print(f"  🖼️  Gallery: {gallery_path}")

    return result


def _maybe_save_output(result: dict[str, Any], output_dir: str | None) -> None:
    """如指定 output_dir，保存结构化的结果元数据到 JSON + 复制最优图。"""
    if not output_dir:
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 保存 JSON 元数据
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "prompt": result.get("prompt", ""),
        "inspection_summary": result.get("inspection_summary", ""),
        "best": {
            "seed": result.get("best", {}).get("seed", 0),
            "score": result.get("best", {}).get("score", -1),
            "image_relative": "",
            "inspect": _summarize_inspect(result.get("best", {}).get("inspect", {})),
        },
        "candidates_count": len(result.get("candidates", [])),
    }

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
    """生成全候选 HTML 画廊（self-contained），返回输出路径。"""
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
        images.append({
            "file": dest.name,
            "seed": c.get("seed", "?"),
            "score": c.get("score", -1),
            "summary": ins.get("summary", ""),
            "overall": ins.get("scores", {}).get("overall", 0) if ins else 0,
            "best": is_best,
            "error": False,
        })

    # 组装 HTML
    prompt_escaped = result.get("prompt", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    summary = result.get("inspection_summary", "")
    rows_html = ""
    for img in images:
        if img.get("error"):
            rows_html += f"""
<div class="card error">
  <div class="img-placeholder">❌ seed={img['seed']}</div>
  <div class="info">seed: {img['seed']} <span class="badge error-badge">ERROR</span></div>
</div>"""
            continue
        best_class = " best" if img.get("best") else ""
        score_tag = f"<span class='score'>CLIP: {img['score']:.2f}</span>" if img.get("score", -1) >= 0 else ""
        summary_tag = f"<span class='summary'>{img['summary']}</span>" if img.get("summary") else ""
        overall_tag = f"<span class='overall'>综合: {img.get('overall', 0):.2f}</span>" if img.get('overall', 0) > 0 else ""
        best_badge = " <span class='badge best-badge'>🏆 最优</span>" if img.get("best") else ""
        rows_html += f"""
<div class="card{best_class}">
  <img src="{img['file']}" loading="lazy" onclick="openModal(this.src)" />
  <div class="info">seed: {img['seed']} {score_tag} {overall_tag} {summary_tag}{best_badge}</div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>创作工坊 · Gallery</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#1a1a2e;color:#eee;font-family:system-ui,sans-serif;padding:20px}}
h1{{font-size:1.5rem;margin-bottom:8px;color:#e8a87c}}
.prompt{{color:#999;font-size:.85rem;margin-bottom:20px;padding:10px;background:#16213e;border-radius:8px;word-break:break-all}}
.summary-row{{margin-bottom:16px;font-size:.9rem;color:#aaa}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
.card{{background:#16213e;border-radius:10px;overflow:hidden;border:2px solid transparent;transition:transform .15s}}
.card:hover{{transform:translateY(-2px)}}
.card.best{{border-color:#e8a87c;box-shadow:0 0 12px rgba(232,168,124,.3)}}
.card img{{width:100%;height:auto;display:block;cursor:pointer}}
.card.error{{padding:20px;text-align:center;color:#666}}
.img-placeholder{{font-size:2rem;padding:40px 0;color:#555}}
.info{{padding:8px 10px;font-size:.8rem;display:flex;flex-wrap:wrap;gap:4px;align-items:center}}
.score{{color:#7ec8e3}}
.overall{{color:#a8e6cf}}
.summary{{color:#d4a5a5}}
.badge{{font-size:.7rem;padding:2px 6px;border-radius:4px}}
.best-badge{{background:#e8a87c33;color:#e8a87c}}
.error-badge{{background:#ff444433;color:#ff4444}}
/* modal */
#modal{{display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.9);cursor:zoom-out;align-items:center;justify-content:center}}
#modal.show{{display:flex}}
#modal img{{max-width:95vw;max-height:95vh;object-fit:contain;border-radius:4px}}
</style></head>
<body>
<h1>🖼️ 创作工坊 · Gallery</h1>
<div class="prompt">{prompt_escaped}</div>
<div class="summary-row">{f'质检: {summary}' if summary else ''} · 共 {len(images)} 张</div>
<div class="grid">{rows_html}</div>
<div id="modal" onclick="this.classList.remove('show')"><img id="modal-img" src="" alt=""/></div>
<script>
function openModal(src){{document.getElementById('modal-img').src=src;document.getElementById('modal').classList.add('show')}}
</script>
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
