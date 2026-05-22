"""
兼容入口（已合并到 go_knives_lora.py）。

请改用: python go_knives_lora.py --character caster <描述>
"""

from __future__ import annotations

import sys

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()


def main() -> None:
    print("提示: go_caster_lora.py 已合并，正在转发到 go_knives_lora.py --character caster", file=sys.stderr)
    sys.argv = [sys.argv[0], "--character", "caster", *sys.argv[1:]]
    from go_knives_lora import main as run

    run()


if __name__ == "__main__":
    main()
