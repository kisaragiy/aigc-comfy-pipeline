"""
Output Gallery — 自动生成 HTML 画廊展示所有产出。

用法示例:
  python go_gallery.py
  python go_gallery.py --output gallery.html
  python go_gallery.py --type video
  python go_gallery.py --serve
  python go_gallery.py --serve --port 8080
"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()

from output_manager import list_runs  # noqa: E402

GALLERY_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0f1115; color: #e8eaed; font-family: 'Segoe UI', sans-serif; }
header { padding: 1.5rem 1rem; border-bottom: 1px solid #2a2f3a; text-align: center; }
header h1 { font-size: 1.4rem; margin-bottom: 0.3rem; }
header .stats { color: #9aa0a6; font-size: 0.85rem; }
.filters { margin-top: 0.8rem; }
.filter-btn { background: #1a1d24; color: #9aa0a6; border: 1px solid #2a2f3a;
  padding: 0.35rem 0.9rem; border-radius: 20px; cursor: pointer; margin: 0.15rem;
  font-size: 0.85rem; transition: all 0.2s; }
.filter-btn:hover { border-color: #6ea8fe; }
.filter-btn.active { background: #6ea8fe; color: #fff; border-color: #6ea8fe; }
#gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem; padding: 1rem; }
.card { background: #1a1d24; border-radius: 12px; overflow: hidden;
  border: 1px solid #2a2f3a; transition: border-color 0.2s; }
.card:hover { border-color: #6ea8fe; }
.card .images { position: relative; }
.card .images img { width: 100%; aspect-ratio: 1; object-fit: cover;
  display: block; background: #2a2f3a; }
.card .meta { padding: 0.6rem 0.8rem; }
.cmd-badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 10px;
  font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }
.cmd-badge.flux { background: #6ea8fe33; color: #6ea8fe; }
.cmd-badge.lora { background: #a78bfa33; color: #a78bfa; }
.cmd-badge.ipa { background: #34d39933; color: #34d399; }
.cmd-badge.multi { background: #fbbf2433; color: #fbbf24; }
.cmd-badge.sweep { background: #f472b633; color: #f472b6; }
.cmd-badge.video { background: #f59e0b33; color: #f59e0b; }
.cmd-badge.serve { background: #6366f133; color: #6366f1; }
.cmd-badge.video-batch { background: #f59e0b33; color: #f59e0b; }
.cmd-badge.sweep-video { background: #f59e0b33; color: #f59e0b; }
.card .images video { width: 100%; aspect-ratio: 1; object-fit: cover;
  display: block; background: #2a2f3a; }
.time { color: #9aa0a6; font-size: 0.75rem; margin-left: 0.4rem; }
.prompt { color: #e8eaed; font-size: 0.82rem; margin: 0.4rem 0;
  line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.params { margin-top: 0.25rem; }
.tag { display: inline-block; background: #2a2f3a; color: #9aa0a6;
  padding: 0.05rem 0.4rem; border-radius: 6px; font-size: 0.7rem;
  margin: 0.1rem; white-space: nowrap; max-width: 120px; overflow: hidden;
  text-overflow: ellipsis; }
.empty { text-align: center; padding: 4rem 1rem; color: #9aa0a6; }
.empty h2 { font-size: 1.2rem; margin-bottom: 0.5rem; }
footer { text-align: center; padding: 1.5rem; color: #555; font-size: 0.75rem; }
/* Compare */
.compare-bar { display: none; position: fixed; bottom: 0; left: 0; right: 0;
  background: #1a1d24; border-top: 1px solid #6ea8fe; padding: 0.8rem 1rem;
  justify-content: center; gap: 1rem; align-items: center; z-index: 100; }
.compare-bar.active { display: flex; }
.compare-bar .count { color: #9aa0a6; font-size: 0.85rem; }
.compare-btn { background: #6ea8fe; color: #fff; border: none;
  padding: 0.5rem 1.5rem; border-radius: 8px; cursor: pointer; font-size: 0.85rem; }
.compare-btn:disabled { opacity: 0.4; cursor: default; }
.card .cmp-cb { position: absolute; top: 8px; right: 8px; z-index: 10;
  width: 22px; height: 22px; cursor: pointer; accent-color: #6ea8fe; }
.overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85);
  z-index: 200; justify-content: center; align-items: center; padding: 2rem; }
.overlay.active { display: flex; }
.overlay .pair { display: flex; gap: 1rem; max-width: 90vw; max-height: 90vh; }
.overlay .pair > div { flex: 1; min-width: 0; }
.overlay .pair img, .overlay .pair video { width: 100%; max-height: 80vh;
  object-fit: contain; border-radius: 8px; }
.overlay .pair .label { color: #9aa0a6; font-size: 0.8rem; margin-top: 0.3rem;
  text-align: center; }
.overlay .close { position: absolute; top: 1rem; right: 1.5rem;
  color: #fff; font-size: 2rem; cursor: pointer; background: none; border: none; }
/* Sort */
.sort-bar { margin-top: 0.5rem; display: flex; gap: 0.5rem; justify-content: center; }
.sort-btn { background: none; color: #9aa0a6; border: none; cursor: pointer;
  font-size: 0.8rem; padding: 0.2rem 0.6rem; border-radius: 4px; }
.sort-btn:hover { color: #e8eaed; }
.sort-btn.active { color: #6ea8fe; font-weight: bold; }
"""

GALLERY_JS = """\
// Type filter
document.querySelectorAll('.filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
    this.classList.add('active');
    var filter = this.dataset.filter;
    document.querySelectorAll('.card').forEach(function(card) {
      card.style.display = (filter === 'all' || card.dataset.command === filter) ? '' : 'none';
    });
  });
});
// Compare
var selected = {};
document.querySelectorAll('.cmp-cb').forEach(function(cb) {
  cb.addEventListener('change', function() {
    if (this.checked) {
      selected[this.dataset.id] = this.dataset.index;
    } else {
      delete selected[this.dataset.id];
    }
    var n = Object.keys(selected).length;
    document.querySelector('.compare-bar').classList.toggle('active', n > 0);
    document.querySelector('.compare-bar .count').textContent = n + ' selected';
    document.querySelector('.compare-btn').disabled = n !== 2;
  });
});
document.querySelector('.compare-btn').addEventListener('click', function() {
  var ids = Object.keys(selected).slice(0, 2);
  var overlays = document.querySelectorAll('.overlay-item');
  for (var i = 0; i < 2; i++) {
    var idx = parseInt(selected[ids[i]]);
    var card = document.querySelectorAll('.card')[idx];
    overlays[i].innerHTML = card.querySelector('.images').innerHTML;
    var label = (card.querySelector('.cmd-badge') || {}).textContent || '';
    var ts = (card.querySelector('.time') || {}).textContent || '';
    overlays[i].innerHTML += '<div class="label">' + label + ' ' + ts + '</div>';
  }
  document.querySelector('.overlay').classList.add('active');
});
document.querySelector('.overlay .close').addEventListener('click', function() {
  document.querySelector('.overlay').classList.remove('active');
});
// Sort
function sortGallery(method) {
  var gallery = document.getElementById('gallery');
  var cards = Array.from(gallery.querySelectorAll('.card'));
  cards.sort(function(a, b) {
    if (method === 'newest') {
      return b.dataset.ts.localeCompare(a.dataset.ts);
    } else if (method === 'oldest') {
      return a.dataset.ts.localeCompare(b.dataset.ts);
    } else {
      return (a.dataset.command || '').localeCompare(b.dataset.command || '');
    }
  });
  cards.forEach(function(c) { gallery.appendChild(c); });
  document.querySelectorAll('.sort-btn').forEach(function(b) {
    b.classList.toggle('active', b.dataset.sort === method);
  });
}
document.querySelectorAll('.sort-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    sortGallery(this.dataset.sort);
  });
});
"""


def _get_output_dir() -> Path:
    """获取 outputs/ 目录。"""
    return Path(__file__).resolve().parents[1] / "outputs"


def _has_video(run: dict[str, Any]) -> bool:
    """检查 run 是否包含视频文件。"""
    for img in run.get("images", []):
        if img.lower().endswith((".mp4", ".webm", ".mov")):
            return True
    return False


def _has_image(run: dict[str, Any]) -> bool:
    """检查 run 是否包含图片文件。"""
    for img in run.get("images", []):
        if not img.lower().endswith((".mp4", ".webm", ".mov")):
            return True
    return False


def _find_ffmpeg() -> str:
    """查找 ffmpeg 路径，返回空字符串表示未找到。"""
    import shutil
    return shutil.which("ffmpeg") or ""


def _get_video_duration(video_path: Path) -> float:
    """用 ffprobe 获取视频时长（秒）。"""
    import json
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", str(video_path)],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError):
        return 0.0


def _extract_poster(video_path: Path, poster_path: Path) -> bool:
    """从视频中间帧提取海报图。"""
    import subprocess

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return False
    duration = _get_video_duration(video_path)
    if duration <= 0:
        return False
    mid_time = duration / 2.0
    try:
        result = subprocess.run(
            [ffmpeg, "-y", "-ss", str(mid_time), "-i", str(video_path),
             "-vframes", "1", "-q:v", "2", str(poster_path)],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _get_poster_path(video_path: Path) -> Path:
    """获取视频对应的海报图路径。"""
    return video_path.parent / f"{video_path.stem}_poster.jpg"


def _build_html(runs: list[dict[str, Any]], media_type: str = "all", refresh_posters: bool = False) -> str:
    """构建自包含 HTML 画廊。

    Args:
        runs: 产出列表
        media_type: 过滤类型 (all/image/video)
    """
    if media_type == "image":
        runs = [r for r in runs if _has_image(r)]
    elif media_type == "video":
        runs = [r for r in runs if _has_video(r)]

    cards: list[str] = []
    total_images = 0
    total_videos = 0
    commands: set[str] = set()
    output_dir = _get_output_dir()

    for card_idx, run in enumerate(runs):
        cmd = run.get("command", "?")
        ts = (run.get("timestamp") or "?")[:19]
        rid = run.get("run_id", "")
        images = run.get("images", [])
        params = run.get("params", {})
        commands.add(cmd)

        imgs_html = ""
        run_path = output_dir / rid / "images"
        for img_name in images[:4]:
            media_path = run_path / img_name
            if not media_path.is_file():
                continue
            ext = media_path.suffix.lower()
            if ext in (".mp4", ".webm", ".mov"):
                total_videos += 1
                poster_path = _get_poster_path(media_path)
                if not poster_path.exists() and refresh_posters:
                    _extract_poster(media_path, poster_path)
                poster_attr = f' poster="file:///{poster_path.as_posix()}"' if poster_path.exists() else ""
                imgs_html += (
                    f'<video controls preload="metadata" muted playsinline{poster_attr} '
                    f'src="file:///{media_path.as_posix()}" />'
                )
            else:
                total_images += 1
                imgs_html += (
                    f'<img src="file:///{media_path.as_posix()}" loading="lazy" />'
                )

        tags = ""
        for k, v in params.items():
            if k in ("prompt_id", "images"):
                continue
            val = str(v)[:50]
            tags += f'<span class="tag">{k}: {val}</span>'

        prompt = params.get("prompt", "")
        if isinstance(prompt, str) and len(prompt) > 90:
            prompt = prompt[:90] + "..."

        cards.append(f"""<div class="card" data-command="{cmd}" data-ts="{ts}" data-idx="{card_idx}">
  <div class="images">
    <input type="checkbox" class="cmp-cb" data-id="{rid}" data-index="{card_idx}" />
    {imgs_html}
  </div>
  <div class="meta">
    <span class="cmd-badge {cmd}">{cmd}</span>
    <span class="time">{ts}</span>
    {f'<div class="prompt">{prompt}</div>' if prompt else ''}
    <div class="params">{tags}</div>
  </div>
</div>""")

    commands_list = " ".join(
        f'<button class="filter-btn" data-filter="{c}">{c}</button>'
        for c in sorted(commands)
    )

    # 类型过滤按钮
    type_filter_btns = ""
    for t, label in [("all", "All"), ("image", "Images"), ("video", "Videos")]:
        active = " active" if t == media_type else ""
        type_filter_btns += f'<button class="filter-btn{active}" data-type-filter="{t}">{label}</button>'

    cards_html = "\n".join(cards) if cards else (
        '<div class="empty"><h2>暂无产出</h2>'
        '<p>运行出图命令后，产出会自动显示在这里。</p></div>'
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIGC Pipeline — Output Gallery</title>
<style>{GALLERY_CSS}</style>
</head>
<body>
<div class="overlay">
  <button class="close">&times;</button>
  <div class="pair">
    <div class="overlay-item"></div>
    <div class="overlay-item"></div>
  </div>
</div>
<div class="compare-bar">
  <span class="count">0 selected</span>
  <button class="compare-btn" disabled>Compare</button>
</div>
<header>
  <h1>🎨 Output Gallery</h1>
  <div class="filters">
    <button class="filter-btn active" data-filter="all">All</button>
    {commands_list}
  </div>
  <div class="filters" style="margin-top:0.4rem">
    {type_filter_btns}
  </div>
  <div class="sort-bar">
    <button class="sort-btn active" data-sort="newest">Newest</button>
    <button class="sort-btn" data-sort="oldest">Oldest</button>
    <button class="sort-btn" data-sort="command">Command</button>
  </div>
  <div class="stats">{len(runs)} runs &middot; {total_images} images{f' &middot; {total_videos} videos' if total_videos else ''}</div>
</header>
<main id="gallery">{cards_html}</main>
<footer>generated {now}</footer>
<script>{GALLERY_JS}
// Type filter (re-fetch gallery with type param)
document.querySelectorAll('[data-type-filter]').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    var t = this.dataset.typeFilter;
    var params = new URLSearchParams(window.location.search);
    if (t === 'all') params.delete('type');
    else params.set('type', t);
    var url = window.location.pathname;
    var qs = params.toString();
    if (qs) url += '?' + qs;
    window.location.href = url;
  }});
}});
</script>
</body>
</html>"""


def generate_gallery(output_path: Path, media_type: str = "all", refresh_posters: bool = False) -> None:
    """生成输出画廊 HTML。"""
    runs = list_runs()
    html = _build_html(runs, media_type=media_type, refresh_posters=refresh_posters)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    type_label = {"all": "全部", "image": "图片", "video": "视频"}[media_type]
    print(f"🎨 画廊已生成 ({type_label}): {output_path}")
    webbrowser.open(output_path.resolve().as_uri())


def main() -> None:
    parser = argparse.ArgumentParser(description="Output Gallery — 产出画廊")
    parser.add_argument(
        "--output", default=None,
        help="输出 HTML 路径（默认 outputs/gallery.html）",
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="启动 HTTP 服务（浏览器实时查看）",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="HTTP 服务端口（默认 8765）",
    )
    parser.add_argument(
        "--type", choices=["all", "image", "video"], default="all",
        help="过滤类型: all(全部) / image(仅图片) / video(仅视频)",
    )
    parser.add_argument(
        "--refresh-posters", action="store_true",
        help="强制重新提取视频海报帧",
    )
    args = parser.parse_args()

    if args.serve:
        output_path = Path(args.output or "outputs/gallery.html")
        print(f"🎨 画廊服务: http://127.0.0.1:{args.port}")
        print("  按 Ctrl+C 停止")

        generate_gallery(output_path, media_type=args.type, refresh_posters=args.refresh_posters)

        server = HTTPServer(
            ("127.0.0.1", args.port),
            lambda *a, **kw: _GalleryHandler(output_path.parent, *a, **kw),
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止。")
    else:
        output_path = Path(args.output or "outputs/gallery.html")
        generate_gallery(output_path, media_type=args.type, refresh_posters=args.refresh_posters)


class _GalleryHandler(SimpleHTTPRequestHandler):
    """自定义 Handler，服务 outputs/ 目录下的文件。"""

    def __init__(
        self, directory: Path, *args: Any, **kwargs: Any
    ) -> None:
        super().__init__(*args, directory=str(directory), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"[gallery] {args[0]} {args[1]} {args[2]}\n")


if __name__ == "__main__":
    main()
