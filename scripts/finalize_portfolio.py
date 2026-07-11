# -*- coding: utf-8 -*-
"""
[已弃用] 请直接使用 scripts/bootstrap_portfolio.py。

finalize_portfolio.py 仅为 bootstrap_portfolio.main() 的简单封装。
计划在 V0.6.0 移除本文件。
"""
from __future__ import annotations

import sys

if __name__ == "__main__":
    print("⚠️  scripts/finalize_portfolio.py 已弃用，请改用 scripts/bootstrap_portfolio.py", file=sys.stderr)
    from bootstrap_portfolio import main

    main()
