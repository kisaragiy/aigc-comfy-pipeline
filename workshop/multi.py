#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/multi.py — 多人同框生成（B-multi）v1.0
================================================
B站 67K 热度场景：CP 图/同框图（二创核心）。
两人或多人同框 → 构图模式（couple/group/battle）。

用法:
  python -m agents workshop multi "角色A描述" "角色B描述" [--mode couple|group|battle]
"""

import argparse, os, sys, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 复用 wallpaper 的多人同框核心
from workshop.wallpaper import generate_multi, MULTI_COMPOSE


def main(argv=None):
    ap = argparse.ArgumentParser(prog='workshop multi', description='多人同框生成（CP/同框图）')
    ap.add_argument('desc', nargs='*', help='角色描述（1-3 个）: "角色A" "角色B"')
    ap.add_argument('--mode', choices=list(MULTI_COMPOSE.keys()), default='couple',
                    help='构图: couple(CP)/group(三人)/battle(对决)')
    ap.add_argument('--ref-a', default=None, help='角色A参考图（IPAdapter 防漂移）')
    ap.add_argument('--ref-b', default=None, help='角色B参考图（IPAdapter 防漂移）')
    ap.add_argument('--output', default=None, help='输出路径')
    ap.add_argument('--seed', type=int, default=-1)
    ap.add_argument('--count', type=int, default=1)
    args = ap.parse_args(argv)

    descs = args.desc
    if not descs:
        print('用法: multi "角色A" "角色B" [--mode couple|group|battle] [--ref-a 图] [--ref-b 图]')
        return 1
    if len(descs) == 1:
        # 单描述 + 模式补全
        generate_multi(descs[0], None, mode=args.mode, seed=args.seed,
                       output=args.output, count=args.count,
                       ref_a=args.ref_a, ref_b=args.ref_b)
    elif len(descs) >= 2:
        generate_multi(descs[0], ' '.join(descs[1:]), mode=args.mode,
                       seed=args.seed, output=args.output, count=args.count,
                       ref_a=args.ref_a, ref_b=args.ref_b)
    return 0


if __name__ == '__main__':
    sys.exit(main())
