"""创作工坊模块 — 自然语言驱动的 AIGC 创作工坊。

子模块:
  engine/    Prompt 引擎 — 自然语言 → 专业绘画提示词
  inspect/   质检模块 — 逐部位崩坏检测
  manga/     漫画/分镜生成 — 剧本 → 八列分镜表 → 逐格生图 → 拼页
  video/     视频自动化 — 分镜驱动视频生成
"""

from __future__ import annotations
