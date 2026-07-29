"""审核 Web UI 服务器 — Python 标准库 http.server，零额外依赖。"""

from __future__ import annotations

import json
import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from workshop.review import (
    VERDICTS,
    PRESET_TAGS,
    VERDICT_KEEP,
    VERDICT_DELETE,
    VERDICT_FAVORITE,
    VERDICT_RETRY,
    apply_verdict,
    generate_report,
    get_review_index,
    load_review,
    scan_output,
)

# ── HTML 模板 ────────────────────────────────────────────


def _gallery_html(images: list[dict], review_index: dict, tags: list[str], output_dir: str) -> str:
    """生成主 Gallery 页面 HTML。"""
    # 构建每张图片的 HTML
    cards = []
    for img in images:
        entry = review_index.get(img["path"])
        verdict = entry.get("verdict") if entry else None
        reviewed_at = entry.get("reviewed_at", "") if entry else ""
        comment = entry.get("comment", "") if entry else ""
        img_tags = entry.get("tags", []) if entry else []

        # 选择 verdict CSS class
        vc = ""
        if verdict == VERDICT_KEEP:
            vc = "verdict-keep"
        elif verdict == VERDICT_DELETE:
            vc = "verdict-delete"
        elif verdict == VERDICT_FAVORITE:
            vc = "verdict-fav"
        elif verdict == VERDICT_RETRY:
            vc = "verdict-retry"

        # 分数
        score = img.get("auto_score", -1.0)
        score_str = f"{score:.2f}" if score >= 0 else "—"
        ins = img.get("inspect", {})
        f_val = ins.get("face", ins.get("face", "—"))
        h_val = ins.get("hand", ins.get("hand", "—"))
        b_val = ins.get("blur", ins.get("blur", "—"))
        if f_val == "—":
            f_str = "—"
        else:
            f_str = "✓" if float(f_val) > 0.5 else "✗"
        h_str = "✓" if h_val != "—" and float(h_val) > 0.5 else ("✗" if h_val != "—" else "—")
        b_str = "✓" if b_val != "—" and float(b_val) > 0.5 else ("✗" if b_val != "—" else "—")

        best_mark = "⭐ " if img.get("is_best") else ""
        tags_html = " ".join(f'<span class="tag">{t}</span>' for t in img_tags)
        comment_html = f'<div class="comment-line">{comment}</div>' if comment else ""

        label = verdict if verdict else "待审"
        label_class = verdict if verdict else "pending"

        cards.append(f'''
    <div class="card {vc}" data-verdict="{verdict or ""}" data-scene="{img['scene_id']}" data-reviewed="{1 if verdict else 0}">
      <div class="card-img-wrap">
        <img loading="lazy" src="./{img['path']}" onclick="viewImage('{img['path']}')" alt="{img['path']}">
        <div class="card-verdict-label {label_class}">{label}</div>
      </div>
      <div class="card-info">
        <div class="card-title">{best_mark}{img['scene']}</div>
        <div class="card-meta">
          <span>seed: {img['seed']}</span>
          <span>评分: {score_str}</span>
        </div>
        <div class="card-inspect">
          <span title="脸">👤{f_str}</span>
          <span title="手">✋{h_str}</span>
          <span title="模糊">🌫️{b_str}</span>
        </div>
        {tags_html}
        {comment_html}
        <div class="card-actions">
          <button onclick="setVerdict('{img['path']}', '{VERDICT_KEEP}')" class="btn-keep" title="保留">✅</button>
          <button onclick="setVerdict('{img['path']}', '{VERDICT_DELETE}')" class="btn-delete" title="删除">❌</button>
          <button onclick="setVerdict('{img['path']}', '{VERDICT_FAVORITE}')" class="btn-fav" title="精选">⭐</button>
          <button onclick="setVerdict('{img['path']}', '{VERDICT_RETRY}')" class="btn-retry" title="重试">🔄</button>
          <button onclick="showDetail('{img['path']}')" class="btn-detail" title="详情">🔍</button>
        </div>
      </div>
    </div>''')

    cards_html = "\n".join(cards)
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>人工审核 — 面试样张</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; }}
.header {{ background: #16213e; padding: 16px 24px; position: sticky; top: 0; z-index: 100; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }}
.header h1 {{ font-size: 18px; color: #fff; }}
.filter-bar {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.filter-btn {{ padding: 6px 14px; border: 1px solid #333; border-radius: 6px; background: transparent; color: #aaa; cursor: pointer; font-size: 13px; transition: all .15s; }}
.filter-btn:hover {{ background: #2a2a4a; color: #fff; }}
.filter-btn.active {{ background: #4361ee; color: #fff; border-color: #4361ee; }}
.filter-btn .count {{ opacity: .6; margin-left: 4px; }}
#report-btn {{ margin-left: auto; padding: 6px 14px; border: 1px solid #f0c040; border-radius: 6px; background: transparent; color: #f0c040; cursor: pointer; font-size: 13px; }}
#report-btn:hover {{ background: #f0c04022; }}
.gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; padding: 20px; }}
.card {{ background: #16213e; border-radius: 10px; overflow: hidden; transition: transform .15s, box-shadow .15s; border: 2px solid transparent; }}
.card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
.card.verdict-keep {{ border-color: #2d6a4f; }}
.card.verdict-delete {{ border-color: #9b2226; opacity: .6; }}
.card.verdict-fav {{ border-color: #f0c040; }}
.card.verdict-retry {{ border-color: #e76f51; }}
.card-img-wrap {{ position: relative; cursor: pointer; }}
.card-img-wrap img {{ width: 100%; height: 200px; object-fit: cover; display: block; }}
.card-verdict-label {{ position: absolute; top: 6px; right: 6px; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.card-verdict-label.pending {{ background: #666; color: #fff; }}
.card-verdict-label.keep {{ background: #2d6a4f; color: #fff; }}
.card-verdict-label.delete {{ background: #9b2226; color: #fff; }}
.card-verdict-label.favorite {{ background: #f0c040; color: #1a1a2e; }}
.card-verdict-label.retry {{ background: #e76f51; color: #fff; }}
.card-info {{ padding: 10px 12px; }}
.card-title {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
.card-meta {{ font-size: 12px; color: #888; display: flex; gap: 12px; }}
.card-inspect {{ font-size: 12px; display: flex; gap: 10px; margin: 4px 0; }}
.tag {{ display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #2a2a4a; color: #aaa; margin: 2px 2px 0 0; }}
.comment-line {{ font-size: 11px; color: #aaa; font-style: italic; margin-top: 2px; }}
.card-actions {{ display: flex; gap: 4px; margin-top: 6px; }}
.card-actions button {{ width: 32px; height: 28px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all .1s; display: flex; align-items: center; justify-content: center; background: #2a2a4a; }}
.card-actions button:hover {{ transform: scale(1.15); }}
.btn-keep:hover {{ background: #2d6a4f; }}
.btn-delete:hover {{ background: #9b2226; }}
.btn-fav:hover {{ background: #f0c040; }}
.btn-retry:hover {{ background: #e76f51; }}
.btn-detail:hover {{ background: #4361ee; }}
.toast {{ position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); padding: 10px 24px; border-radius: 8px; color: #fff; font-size: 14px; z-index: 999; transition: all .3s; opacity: 0; pointer-events: none; }}
.toast.show {{ opacity: 1; }}

/* 详情弹窗 */
.modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 200; justify-content: center; align-items: center; }}
.modal.open {{ display: flex; }}
.modal-body {{ max-width: 90vw; max-height: 90vh; display: flex; gap: 20px; background: #16213e; border-radius: 10px; padding: 20px; }}
.modal-body img {{ max-height: 75vh; max-width: 65vw; object-fit: contain; border-radius: 6px; }}
.modal-side {{ width: 280px; overflow-y: auto; }}
.modal-side h3 {{ font-size: 16px; margin-bottom: 10px; }}
.modal-side .detail-row {{ font-size: 13px; margin: 6px 0; color: #aaa; }}
.modal-side .detail-row span {{ color: #e0e0e0; }}
.tag-select {{ display: flex; flex-wrap: wrap; gap: 4px; margin: 8px 0; }}
.tag-select button {{ padding: 3px 10px; border: 1px solid #444; border-radius: 4px; background: transparent; color: #aaa; cursor: pointer; font-size: 12px; }}
.tag-select button.active {{ background: #4361ee; border-color: #4361ee; color: #fff; }}
.modal-actions {{ margin-top: 12px; display: flex; gap: 6px; flex-wrap: wrap; }}
.modal-actions button {{ padding: 6px 14px; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }}
.modal-close {{ position: absolute; top: 16px; right: 24px; font-size: 28px; color: #fff; cursor: pointer; background: none; border: none; }}
textarea {{ width: 100%; padding: 6px; border: 1px solid #444; border-radius: 4px; background: #1a1a2e; color: #e0e0e0; font-size: 12px; resize: vertical; min-height: 40px; }}

/* 报告弹窗 */
.report-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 300; justify-content: center; align-items: center; }}
.report-overlay.open {{ display: flex; }}
.report-box {{ background: #16213e; border-radius: 10px; padding: 24px; max-width: 500px; width: 90%; }}
.report-box h2 {{ margin-bottom: 16px; }}
.report-box .rrow {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; border-bottom: 1px solid #2a2a4a; }}
.report-box .rrow:last-child {{ border-bottom: none; }}
</style>
</head>
<body>

<div class="header">
  <h1>🖼️ 人工审核</h1>
  <span style="font-size:13px;color:#888;">{output_dir}</span>
  <div class="filter-bar">
    <button class="filter-btn active" data-filter="all" onclick="setFilter('all')">全部 <span class="count" id="count-all">0</span></button>
    <button class="filter-btn" data-filter="pending" onclick="setFilter('pending')">待审 <span class="count" id="count-pending">0</span></button>
    <button class="filter-btn" data-filter="reviewed" onclick="setFilter('reviewed')">已审 <span class="count" id="count-reviewed">0</span></button>
    <button class="filter-btn" data-filter="keep" onclick="setFilter('keep')">✅ 保留 <span class="count" id="count-keep">0</span></button>
    <button class="filter-btn" data-filter="favorite" onclick="setFilter('favorite')">⭐ 精选 <span class="count" id="count-fav">0</span></button>
    <button class="filter-btn" data-filter="delete" onclick="setFilter('delete')">❌ 已删 <span class="count" id="count-del">0</span></button>
    <button class="filter-btn" data-filter="retry" onclick="setFilter('retry')">🔄 重试 <span class="count" id="count-retry">0</span></button>
  </div>
  <button id="report-btn" onclick="showReport()">📊 报告</button>
</div>

<div id="gallery" class="gallery">
  {cards_html}
</div>

<div id="toast" class="toast"></div>

<!-- 详情弹窗 -->
<div id="detail-modal" class="modal" onclick="closeModal(event)">
  <div class="modal-body" onclick="event.stopPropagation()">
    <img id="detail-img" src="" alt="">
    <div class="modal-side">
      <h3 id="detail-title"></h3>
      <div class="detail-row">种子: <span id="detail-seed"></span></div>
      <div class="detail-row">自动评分: <span id="detail-score"></span></div>
      <div class="detail-row">质检: <span id="detail-inspect"></span></div>
      <div class="detail-row">当前判决: <span id="detail-verdict" style="font-weight:600;"></span></div>
      <div style="margin-top:10px;">
        <label style="font-size:12px;color:#aaa;">标签</label>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin:6px 0;">
          {''.join(f'<button class="tag-preset" data-tag="{t}" onclick="togglePresetTag(this)">{t}</button>' for t in tags)}
        </div>
      </div>
      <label style="font-size:12px;color:#aaa;">备注</label>
      <textarea id="detail-comment" placeholder="输入备注..."></textarea>
      <div class="modal-actions">
        <button onclick="setFromDetail('{VERDICT_KEEP}')" style="background:#2d6a4f;color:#fff;">✅ 保留</button>
        <button onclick="setFromDetail('{VERDICT_DELETE}')" style="background:#9b2226;color:#fff;">❌ 删除</button>
        <button onclick="setFromDetail('{VERDICT_FAVORITE}')" style="background:#f0c040;color:#1a1a2e;">⭐ 精选</button>
        <button onclick="setFromDetail('{VERDICT_RETRY}')" style="background:#e76f51;color:#fff;">🔄 重试</button>
      </div>
    </div>
  </div>
  <button class="modal-close" onclick="closeModal()">&times;</button>
</div>

<!-- 报告弹窗 -->
<div id="report-modal" class="report-overlay" onclick="closeReport(event)">
  <div class="report-box" onclick="event.stopPropagation()">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h2>📊 审核报告</h2>
      <button onclick="closeReport()" style="background:none;border:none;color:#aaa;font-size:20px;cursor:pointer;">&times;</button>
    </div>
    <div id="report-content">加载中...</div>
  </div>
</div>

<script>
const IMG_API = '';

// ── 审核判决 ──
async function setVerdict(path, verdict) {{
    const tags = [];
    const comment = '';
    const resp = await fetch('/api/verdict', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{path, verdict, tags, comment}})
    }});
    const data = await resp.json();
    if (data.ok) {{
        showToast(verdictIcon(verdict) + ' 已标记为 ' + verdict);
        location.reload();
    }} else {{
        showToast('❌ ' + (data.error || '失败'), '#9b2226');
    }}
}}

function verdictIcon(v) {{
    return {{'keep':'✅','delete':'❌','favorite':'⭐','retry':'🔄'}}[v] || '❓';
}}

// ── 筛选 ──
let currentFilter = 'all';

function setFilter(filter) {{
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
    const cards = document.querySelectorAll('.card');
    cards.forEach(c => {{
        const v = c.dataset.verdict || '';
        if (filter === 'all') {{ c.style.display = ''; return; }}
        if (filter === 'pending') {{ c.style.display = v ? 'none' : ''; return; }}
        if (filter === 'reviewed') {{ c.style.display = v ? '' : 'none'; return; }}
        c.style.display = (v === filter) ? '' : 'none';
    }});
    updateCounts();
}}

function updateCounts() {{
    const cards = document.querySelectorAll('.card');
    if (!cards.length) return;
    let all = cards.length, pending = 0, reviewed = 0, keep = 0, fav = 0, del = 0, retry = 0;
    cards.forEach(c => {{
        const v = c.dataset.verdict || '';
        if (!v) pending++;
        else {{ reviewed++; if(v==='keep') keep++; if(v==='favorite') fav++; if(v==='delete') del++; if(v==='retry') retry++; }}
    }});
    document.getElementById('count-all').textContent = all;
    document.getElementById('count-pending').textContent = pending;
    document.getElementById('count-reviewed').textContent = reviewed;
    document.getElementById('count-keep').textContent = keep;
    document.getElementById('count-fav').textContent = fav;
    document.getElementById('count-del').textContent = del;
    document.getElementById('count-retry').textContent = retry;
}}

// ── 详情弹窗 ──
let detailPath = '';

function showDetail(path) {{
    detailPath = path;
    const card = [...document.querySelectorAll('.card')].find(c => c.querySelector('img[alt="' + path + '"]'));
    if (!card) return;
    const meta = card.querySelector('.card-meta').textContent;
    const seedMatch = meta.match(/seed: (\d+)/);
    const scoreMatch = meta.match(/评分: (\S+)/);
    document.getElementById('detail-img').src = './' + path;
    document.getElementById('detail-title').textContent = card.querySelector('.card-title').textContent;
    document.getElementById('detail-seed').textContent = seedMatch ? seedMatch[1] : '—';
    document.getElementById('detail-score').textContent = scoreMatch ? scoreMatch[1] : '—';
    document.getElementById('detail-inspect').textContent = card.querySelector('.card-inspect')?.textContent || '—';
    document.getElementById('detail-verdict').textContent = card.dataset.verdict || '待审';
    document.getElementById('detail-comment').value = '';

    // 标签
    document.querySelectorAll('.tag-preset').forEach(b => b.classList.remove('active'));
    document.getElementById('detail-modal').classList.add('open');
}}

function togglePresetTag(btn) {{
    btn.classList.toggle('active');
}}

function getSelectedTags() {{
    return [...document.querySelectorAll('.tag-preset.active')].map(b => b.dataset.tag);
}}

async function setFromDetail(verdict) {{
    const tags = getSelectedTags();
    const comment = document.getElementById('detail-comment').value;
    const resp = await fetch('/api/verdict', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{path: detailPath, verdict, tags, comment}})
    }});
    const data = await resp.json();
    if (data.ok) {{
        showToast(verdictIcon(verdict) + ' 已标记为 ' + verdict);
        closeModal();
        location.reload();
    }} else {{
        showToast('❌ ' + (data.error || '失败'), '#9b2226');
    }}
}}

function viewImage(path) {{
    showDetail(path);
}}

function closeModal(e) {{
    if (e && e.target !== e.currentTarget) return;
    document.getElementById('detail-modal').classList.remove('open');
}}

document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') closeModal();
}});

// ── Toast ──
function showToast(msg, bg='#2d6a4f') {{
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.style.background = bg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2000);
}}

// ── 报告 ──
async function showReport() {{
    document.getElementById('report-modal').classList.add('open');
    document.getElementById('report-content').textContent = '加载中...';
    try {{
        const resp = await fetch('/api/report');
        const data = await resp.json();
        let html = '';
        html += `<div class="rrow"><span>总张数</span><span>${{data.total}}</span></div>`;
        html += `<div class="rrow"><span>已审核</span><span>${{data.reviewed}}/${{data.total}}</span></div>`;
        html += `<div class="rrow"><span>待审核</span><span>${{data.pending}}</span></div>`;
        html += `<div class="rrow"><span>已删除 (移入 _trash)</span><span>${{data.trashed}}</span></div>`;
        if (data.verdicts) {{
            for (const [v, c] of Object.entries(data.verdicts)) {{
                html += `<div class="rrow"><span>${{verdictIcon(v)}} ${{v}}</span><span>${{c}}</span></div>`;
            }}
        }}
        if (data.tags && Object.keys(data.tags).length > 0) {{
            html += `<div style="margin-top:10px;font-weight:600;font-size:13px;">标签统计</div>`;
            for (const [t, c] of Object.entries(data.tags).sort((a,b) => b[1]-a[1])) {{
                html += `<div class="rrow"><span>#${{t}}</span><span>${{c}}</span></div>`;
            }}
        }}
        document.getElementById('report-content').innerHTML = html;
    }} catch(e) {{
        document.getElementById('report-content').textContent = '❌ 加载失败: ' + e;
    }}
}}

function closeReport(e) {{
    if (e && e.target !== e.currentTarget) return;
    document.getElementById('report-modal').classList.remove('open');
}}

// 初始化计数
updateCounts();

// Ctrl+Enter 提交详情
document.addEventListener('keydown', e => {{
    if (e.ctrlKey && e.key === 'Enter') {{
        const modal = document.getElementById('detail-modal');
        if (modal.classList.contains('open')) {{
            // 默认保留
            setFromDetail('{VERDICT_KEEP}');
        }}
    }}
}});
</script>
</body>
</html>'''



# ── HTTP 请求处理 ───────────────────────────────────────


class ReviewHandler(SimpleHTTPRequestHandler):
    """审核 HTTP 处理器。"""

    def __init__(self, *args, output_dir: str = ".", **kwargs):
        self._output_dir = output_dir
        self._images = scan_output(output_dir)
        self._review_index = get_review_index(self._images, output_dir)
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):
        """静默日志（仅打印错误）。"""
        if args and "404" in str(args[0]):
            print(f"[review] 404: {args}", file=sys.stderr)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            self._serve_gallery()
        elif path == "/api/list":
            self._serve_json({
                "images": self._images,
                "review_index": {k: v for k, v in self._review_index.items() if v.get("verdict")},
            })
        elif path == "/api/report":
            report = generate_report(self._output_dir)
            self._serve_json(report)
        elif path.startswith("/api/"):
            self.send_error(404, "Not Found")
        else:
            # 静态文件 — 用 SimpleHTTPRequestHandler 逻辑但限制在 output_dir
            self._serve_static(path)

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/verdict":
            self._handle_verdict()
        elif path == "/api/delete":
            self._handle_delete()
        else:
            self.send_error(404, "Not Found")

    # ── 路由实现 ──

    def _serve_gallery(self):
        """渲染主页面。"""
        html = _gallery_html(
            self._images,
            self._review_index,
            PRESET_TAGS,
            os.path.abspath(self._output_dir),
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html.encode())))
        self.end_headers()
        self.wfile.write(html.encode())

    def _serve_json(self, data):
        """返回 JSON 响应。"""
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str):
        """从 output_dir 提供静态文件（图片）。"""
        # 去掉开头的 /
        rel = path.lstrip("/")
        file_path = Path(self._output_dir) / rel

        if not file_path.is_file():
            self.send_error(404, f"File not found: {path}")
            return

        # 推断 Content-Type
        ext = file_path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        ct = content_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(data)
        except OSError as e:
            self.send_error(500, f"Error reading file: {e}")

    def _handle_verdict(self):
        """处理审核判决提交。"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            path = data.get("path", "")
            verdict = data.get("verdict", "")
            tags = data.get("tags", [])
            comment = data.get("comment", "")

            entry = apply_verdict(self._output_dir, path, verdict, tags, comment)

            self._serve_json({"ok": True, "entry": entry})
        except Exception as e:
            self.send_error(400, f"Bad request: {e}")

    def _handle_delete(self):
        """处理删除请求（同 verdict=delete）。"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            path = data.get("path", "")
            entry = apply_verdict(self._output_dir, path, "delete")

            self._serve_json({"ok": True, "entry": entry})
        except Exception as e:
            self.send_error(400, f"Bad request: {e}")


# ── 服务启动 ────────────────────────────────────────────


def serve(output_dir: str, port: int = 8765, no_browser: bool = False):
    """启动审核 Web UI 服务器。"""

    # 验证输出目录
    if not Path(output_dir).is_dir():
        print(f"❌ 输出目录不存在: {output_dir}", file=sys.stderr)
        sys.exit(1)

    # 先扫描确认有数据
    images = scan_output(output_dir)
    if not images:
        print(f"⚠️ 该目录下未扫描到可审核的图片", file=sys.stderr)
        print(f"   路径: {os.path.abspath(output_dir)}", file=sys.stderr)

    # 创建处理器工厂
    def handler_factory(*args, **kwargs):
        return ReviewHandler(*args, output_dir=output_dir, **kwargs)

    server = HTTPServer(("127.0.0.1", port), handler_factory)
    url = f"http://127.0.0.1:{port}"

    print(f"\n{'='*50}")
    print(f"  🖼️  人工审核系统")
    print(f"  {'='*50}")
    print(f"  输出目录: {os.path.abspath(output_dir)}")
    print(f"  扫描到: {len(images)} 张图片")
    print(f"  URL: {url}")
    print(f"  {'='*50}")
    print(f"  按 Ctrl+C 停止服务器\n")

    if not no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  服务器已停止")
        server.server_close()
