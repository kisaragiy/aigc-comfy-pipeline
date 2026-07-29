"""质检模块 — 逐部位崩坏检测 + 视觉标注 + 失败诊断。"""

from workshop.inspect.inspector import inspect_image, format_report, annotate_image
from workshop.inspect.diagnose import diagnose

__all__ = ["inspect_image", "format_report", "annotate_image", "diagnose"]
