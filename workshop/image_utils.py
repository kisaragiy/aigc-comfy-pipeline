#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/image_utils.py — 图片公共工具（边缘防护 + 元数据透传）
====================================================
统一图片打开防护：缺图 → FileNotFoundError（友好）；损坏/格式不支持 → ValueError（友好）。
避免 UnidentifiedImageError 等原始异常直接暴露给用户。

元数据透传（业界最佳实践）：ComfyUI 出图自带 PNG tEXt（prompt/workflow/parameters），
但 PIL 后处理（biztext/colorgrade/enhance 等）重新保存时会丢失——成品无法溯源。
save_image_with_meta() 把源图的 AI 生成参数透传到输出图，保证每一张成品可溯源。
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


# ComfyUI 元数据键（PNG tEXt chunks）——读取时扩展用；透传时全量保留
_META_KEYS = ('prompt', 'workflow', 'parameters', 'Description')


def read_png_meta(source_path, include_all=True):
    """读取源图的 AI 生成元数据（PNG tEXt chunks）。

    Args:
        source_path: 源图路径
        include_all: True 返回全部 tEXt 键（含后处理自定义键 colorgrade_params/biztext_*）；
                    False 只返回 ComfyUI 标准键（prompt/workflow/parameters/Description）

    Returns:
        dict: {key: value}，无元数据时返回空 dict
    """
    from PIL import Image
    meta = {}
    if not source_path or not os.path.exists(source_path):
        return meta
    try:
        with Image.open(source_path) as img:
            for k, v in img.info.items():
                if not v:
                    continue
                if include_all or k in _META_KEYS:
                    meta[k] = v
    except Exception:
        pass
    return meta


def save_image_with_meta(img, out_path, source_path=None, extra_meta=None):
    """保存图片并透传/写入 PNG 元数据（业界最佳：成品可溯源）。

    Args:
        img: PIL.Image 待保存
        out_path: 输出路径（.png 时写 tEXt；其他格式忽略元数据）
        source_path: 源图路径（读它的 tEXt 透传；None 跳过）
        extra_meta: 额外元数据 dict（如后处理参数记录）

    Returns:
        输出路径
    """
    from PIL import Image
    out_path = str(out_path)
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    img.save(out_path)  # 先正常保存（兼容所有格式）
    # PNG 才补元数据；出错不阻断主流程（元数据是增强不是核心）
    if not out_path.lower().endswith('.png'):
        return out_path
    if img.mode != 'RGB':
        img = img.convert('RGB')
    try:
        meta = {}
        meta.update(read_png_meta(source_path))
        if extra_meta:
            meta.update(extra_meta)
        if not meta:
            return out_path
        import json
        # 把 dict 值序列化（tEXt 只能存字符串；原始 json 字符串保留原样）
        fmt_meta = {}
        for k, v in meta.items():
            if isinstance(v, str):
                fmt_meta[k] = v
            elif isinstance(v, (dict, list)):
                fmt_meta[k] = json.dumps(v, ensure_ascii=False)
            else:
                fmt_meta[k] = str(v)
        # 重新以带元数据方式保存（PIL pnginfo 机制）
        from PIL.PngImagePlugin import PngInfo
        pnginfo = PngInfo()
        for k, v in fmt_meta.items():
            pnginfo.add_text(k, v[:20000])  # 单键上限保护
        img.save(out_path, format='PNG', pnginfo=pnginfo)
    except Exception:
        pass  # 元数据失败不阻断（无静默失败：主图已保存成功）
    return out_path
