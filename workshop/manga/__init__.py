"""漫画/分镜生成模块。"""

from workshop.manga.manga import (
    script_to_storyboard,
    storyboard_to_prompts,
    generate_panels,
    assemble_page,
    generate_manga_gallery,
)

__all__ = ["script_to_storyboard", "storyboard_to_prompts", "generate_panels", "assemble_page", "generate_manga_gallery"]
