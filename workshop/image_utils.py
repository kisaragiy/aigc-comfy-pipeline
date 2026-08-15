#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/image_utils.py — 图片公共工具（边缘防护）
====================================================
统一图片打开防护：缺图 → FileNotFoundError（友好）；损坏/格式不支持 → ValueError（友好）。
避免 UnidentifiedImageError 等原始异常直接暴露给用户。
"""

import os


def open_image_safe(path):
    """安全打开图片。

    Args:
        path: 图片路径

    Returns:
        PIL.Image

    Raises:
        FileNotFoundError: 路径不存在
        ValueError: 图片损坏或格式不支持
    """
    from PIL import Image
    if not os.path.exists(path):
        raise FileNotFoundError(f'图片不存在: {path}')
    if os.path.isdir(path):
        raise ValueError(f'路径是目录不是图片: {path}')
    try:
        return Image.open(path)
    except Exception as e:
        raise ValueError(f'图片损坏或格式不支持: {os.path.basename(path)}（{type(e).__name__}: {str(e)[:60]}）')
