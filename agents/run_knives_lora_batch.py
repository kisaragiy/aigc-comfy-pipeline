"""
兼容入口（已合并到 go_knives_lora.py --count）。

请改用: python go_knives_lora.py --count 4 <描述>
"""

from __future__ import annotations

import sys

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()


def main() -> None:
    print("提示: run_knives_lora_batch.py 已合并，正在转发到 go_knives_lora.py --count", file=sys.stderr)
    argv = [sys.argv[0]]
    rest = list(sys.argv[1:])
    if "--count" not in rest:
        argv.extend(["--count", "4"])
    argv.extend(rest)
    sys.argv = argv
    from go_knives_lora import main as run

    run()


if __name__ == "__main__":
    main()
