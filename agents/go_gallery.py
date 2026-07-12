"""
Output Gallery — 自动生成 HTML 画廊展示所有产出。

用法示例:
  python go_gallery.py
  python go_gallery.py --output gallery.html
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


GALLERY_CSS = """
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
.cmd-badge.run { background: #60a5fa33; color: #60a5fa; }
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
"""


def _get_output_dir() -> Path:
    """获取 outputs/ 目录。"""
    # 相对于该文件位置 ../outputs/
    return Path(__file__).resolve().parents[1] / "outputs"


def _build_html(runs: list[dict[str, Any]]) -> str:
    """构建自包含 HTML 画廊。"""
    cards: list[str] = []
    total_images = 0
    commands: set[str] = set()
    output_dir = _get_output_dir()

    for run in runs:
        cmd = run.get("command", "?")
        ts = (run.get("timestamp") or "?")[:19]
        rid = run.get("run_id", "")
        images = run.get("images", [])
        params = run.get("params", {})
        total_images += len(images)
        commands.add(cmd)

        # 图片
        imgs_html = ""
        run_path = output_dir / rid / "images"
        for img_name in images[:4]:  # 最多 4 张
            img_path = run_path / img_name
            if img_path.is_file():
                imgs_html += f'<img src="file:///{img_path.as_posix()}" loading="lazy" />'

        # 参数
        tags = ""
        for k, v in params.items():
            if k in ("prompt_id", "images"):
                continue
            val = str(v)[:50]
            tags += f'<span class="tag">{k}: {val}</span>'

        prompt = params.get("prompt", "")
        if isinstance(prompt, str) and len(prompt) > 90:
            prompt = prompt[:90] + "..."

        cards.append(f"""<div class="card" data-command="{cmd}">
  <div class="images">{imgs_html}</div>
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
<header>
  <h1>🎨 Output Gallery</h1>
  <div class="filters">
    <button class="filter-btn active" data-filter="all">All</button>
    {commands_list}
  </div>
  <div class="stats">{len(runs)} runs · {total_images} images</div>
</header>
<main id="gallery">{cards_html}</main>
<footer>generated {now}</footer>
<script>
document.querySelectorAll('.filter-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    this.classList.add('active');
    var filter = this.dataset.filter;
    document.querySelectorAll('.card').forEach(function(card) {{
      card.style.display = (filter === 'all' || card.dataset.command === filter) ? '' : 'none';
    }});
  }});
}});
</script>
</body>
</html>"""


def generate_gallery(output_path: Path) -> None:
    """生成输出画廊 HTML。"""
    runs = list_runs()
    html = _build_html(runs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"🎨 画廊已生成: {output_path}")
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
    args = parser.parse_args()

    if args.serve:
        # HTTP 服务模式
        output_path = Path(args.output or "outputs/gallery.html")
        print(f"🎨 画廊服务: http://127.0.0.1:{args.port}")
        print("  按 Ctrl+C 停止")

        # 生成初始画廊
        generate_gallery(output_path)

        # 启动 HTTP 服务
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
        generate_gallery(output_path)


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
