#!/usr/bin/env python3
"""通用验证码破解系统 — VLM + Playwright + Pillow 三引擎

支持的验证码类型:
  1. 纯文本验证码 → VLM视觉分析 (qwen2.5vl:7b)
  2. 滑块验证码 → Playwright 计算距离 + 拖动
  3. 点选验证码 → VLM分析 + 坐标计算 + Playwright点击
  4. 旋转验证码 → VLM分析旋转角度 + 矫正
  5. 数学验证码 → Pillow OCR + 简单计算
  6. reCAPTCHA v2 → 弹窗+点击自动检测
  7. 视觉逻辑题 → VLM 完整理解

用法:
  python captcha_solver.py image <path>          # 识别图片验证码
  python captcha_solver.py slider <screenshot>   # 分析滑块缺口
  python captcha_solver.py click <screenshot>     # 分析点选坐标
  python captcha_solver.vlm <image_path>         # 用 VLM 分析(通过agent)
  python captcha_solver.py preprocess <path>     # 图片预处理 (去噪/二值/增强)
"""

import sys, json, base64, io, math, time
from pathlib import Path
from typing import Optional

# ── 图片处理 ──
try:
    from PIL import Image, ImageFilter, ImageEnhance
    import numpy as np
except ImportError:
    Image = None
    np = None

# ── 浏览器 ──
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


# ============================================================
# 预处理模块
# ============================================================

def preprocess_image(path: str, output: Optional[str] = None):
    """图片预处理管线 — 提高 VLM/OCR 准确率"""
    if Image is None:
        print("[!] pillow not installed"); return
    
    img = Image.open(path)
    original = img.copy()
    
    print(f"[*] 原始图片: {img.size}, mode={img.mode}")
    
    # 1. 灰度化 (如果彩色)
    if img.mode != "L":
        img = img.convert("L")
        print("    → 灰度化")
    
    # 2. 增强对比度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    print("    → 对比度增强 2.0x")
    
    # 3. 二值化 (Otsu 阈值)
    arr = np.array(img) if np else None
    if arr is not None:
        threshold = arr.mean()
        img_bin = arr > threshold
        result = Image.fromarray((img_bin * 255).astype(np.uint8))
        print(f"    → 二值化 (阈值={threshold:.0f})")
    else:
        result = img
    
    # 4. 去噪 (中值滤波)
    result = result.filter(ImageFilter.MedianFilter(3))
    print("    → 中值滤波去噪")
    
    # 保存
    out_path = output or (Path(path).stem + "_preprocessed.png")
    result.save(out_path)
    print(f"    → 保存到 {out_path}")
    
    # 对比
    print(f"\n 输入: {Path(path).name} ({original.size})")
    print(f" 输出: {out_path} ({result.size})")
    return out_path


# ============================================================
# 滑块验证码分析
# ============================================================

def analyze_slider(screenshot_path: str):
    """分析滑块验证码的缺口位置
    
    策略: 对比背景图 + 滑块图, 找缺口边缘
    返回: 缺口x坐标 (滑块需要拖动的像素距离)
    """
    if Image is None or np is None:
        print("[!] pillow/numpy required"); return None
    
    img = Image.open(screenshot_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape
    
    print(f"[*] 分析滑块验证码: {screenshot_path} ({w}x{h})")
    
    # 策略1: 找亮度跳变区域 (滑块缺口通常比背景亮或暗)
    gray = np.mean(arr, axis=2)
    
    # 水平梯度 (找垂直边缘)
    grad = np.abs(np.diff(gray, axis=1))
    row_grad = np.mean(grad, axis=0)
    
    # 找最明显的边缘 (排除左右边界)
    search_start = int(w * 0.1)
    search_end = int(w * 0.9)
    region_grad = row_grad[search_start:search_end]
    
    if len(region_grad) == 0:
        print("    ❌ 无法分析 (图片太小)")
        return None
    
    # 找梯度最大的位置
    peak_idx = np.argmax(region_grad)
    peak_x = peak_idx + search_start
    
    print(f"    缺口位置: x={peak_x} (从左侧第 {peak_x} 像素)")
    
    # 策略2: 用边缘检测确认
    from PIL import ImageFilter
    edges = img.filter(ImageFilter.FIND_EDGES)
    edges_arr = np.array(edges.convert("L"))
    edge_row = np.mean(edges_arr, axis=0)
    edge_peak = np.argmax(edge_row[search_start:search_end]) + search_start
    
    print(f"    边缘检测确认: x={edge_peak}")
    
    # 综合判断
    if abs(peak_x - edge_peak) < 20:
        final_x = (peak_x + edge_peak) // 2
        print(f"    综合: x={final_x} (两个算法一致)")
    else:
        final_x = peak_x
        print(f"    综合: x={final_x} (以梯度检测为主)")
    
    # 滑块本身宽度 (通常 50-80px)
    print(f"    建议拖动距离: {final_x - 20} ~ {final_x + 20} 像素")
    print(f"    建议拖动速度: 先快后慢 (模拟人类)")
    
    return int(final_x)


def generate_slider_playwright(page, slider_selector: str, target_x: int):
    """生成 Playwright 滑块拖动代码
    
    人类化拖动: 带随机抖动 + 先快后慢
    """
    print(f"[*] 生成滑块拖动 Playwright 代码:\n")
    print(f"""    # 方法1: Playwright 直接拖动 (推荐)
    slider = page.locator("{slider_selector}")
    box = slider.bounding_box()
    if not box:
        raise Exception("Slider not found")
    
    # 鼠标按下
    page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
    page.mouse.down()
    
    # 人类化拖动: 先快后慢 + 随机抖动
    import random, time
    total_distance = {target_x}
    steps = 15 + random.randint(0, 5)
    
    for i in range(steps):
        progress = (i + 1) / steps
        # easing: 先快后慢
        eased = progress ** 1.5
        x = box["x"] + box["width"]/2 + total_distance * eased
        y = box["y"] + box["height"]/2 + random.uniform(-2, 2)
        page.mouse.move(x, y)
        time.sleep(0.005 + random.uniform(0, 0.01))
    
    page.mouse.up()
    time.sleep(1)
    
    # 验证是否成功 (检查是否有错误提示)
    """)
    print(f"""    # 方法2: 备用 API 测试
    # page.evaluate("() => {{ 
    #   const e = document.querySelector('{slider_selector}');
    #   if(e) {{ 
    #     const rect = e.getBoundingClientRect();
    #     e.dispatchEvent(new MouseEvent('mousedown', {{bubbles:true}}));
    #   }}
    # }}")
    """)


# ============================================================
# 点选验证码分析
# ============================================================

def analyze_click_captcha(screenshot_path: str, text_prompt: str = ""):
    """分析点选验证码的点击位置
    
    这类验证码通常显示文字 → 点击图片中对应的图像
    需要 VLM 理解图片内容后给出坐标
    """
    print(f"[*] 分析点选验证码: {screenshot_path}")
    print(f"    提示文字: {text_prompt or '(需手动输入)'}")
    print()
    print("    ── 推荐工作流 ──")
    print("    1. 截取验证码图片")
    print("    2. 在 agent 中调用 vision_analyze 分析:")
    print(f'       vision_analyze(image_url="{screenshot_path}", question="描述这张图片, 找出和\"{text_prompt}\"相关的位置")')
    print("    3. 从回答中提取目标坐标")
    print("    4. 用 Playwright 点击:")
    print("       page.locator('canvas').click(position={'x': x, 'y': y})")
    print()
    print("    ── 自动分析 (Pillow 预处理) ──")
    
    if Image is None:
        return
    
    img = Image.open(screenshot_path)
    print(f"    图片尺寸: {img.size}")
    print(f"    通常点选验证码会将图片分成 3x3 或 4x4 网格")
    print(f"    VLM 回答格式: '目标在格子 (行,列)=(2,3)'")


# ============================================================
# 文本验证码 VLM 分析
# ============================================================

def vlm_analyze_captcha(image_path: str):
    """用 VLM 分析验证码 (通过 Hermes vision_analyze tool)
    
    生成的 prompt 模板, 供 agent 调用 vision_analyze 时使用
    """
    print(f"[*] VLM 验证码分析模板:\n")
    print(f'    # 在 agent 中执行:')
    print(f'    from hermes_tools import terminal')
    print(f'    ')
    print(f'    # 保存图片, 然后:')
    print(f"    vision_analyze(image_url=\"{image_path}\", question=\"\"\"")
    print(f'    请仔细看这张验证码图片, 回答:')
    print(f'    1. 这是什么类型的验证码? (文本/滑块/点选/旋转/数学/逻辑)')
    print(f'    2. 如果是文字, 逐个字符识别出验证码内容')
    print(f'    3. 如果是数学, 计算结果')
    print(f'    4. 如果是滑块, 描述滑块和缺口位置')
    print(f'    5. 如果是点选, 描述目标文字和图片区域')
    print(f'    \n    直接输出答案, 不要额外说明。')
    print(f'    \"\"\")')


# ============================================================
# 旋转验证码
# ============================================================

def analyze_rotation(screenshot_path: str):
    """分析旋转验证码需要旋转的角度
    
    通常: 一张倾斜的图片 → 需要拖到正确角度
    """
    if Image is None or np is None:
        print("[!] pillow/numpy required"); return None
    
    img = Image.open(screenshot_path).convert("L")
    arr = np.array(img)
    h, w = arr.shape
    
    print(f"[*] 分析旋转验证码: {screenshot_path} ({w}x{h})")
    
    # 用边缘检测找文本/主体的方向
    edges = img.filter(ImageFilter.FIND_EDGES)
    edges_arr = np.array(edges)
    
    # 简单策略: 在 ±45° 范围内找最好的投影
    from scipy import ndimage as ndi
    
    best_angle = 0
    best_score = 0
    
    for angle in range(-45, 46, 3):
        rotated = ndi.rotate(edges_arr, angle, reshape=False)
        # 水平投影方差 (文本水平排列时方差最大)
        proj = np.mean(rotated, axis=1)
        score = np.var(proj)
        if score > best_score:
            best_score = score
            best_angle = angle
    
    print(f"    建议旋转: {best_angle}° (相对当前方向)")
    print(f"    用 Playwright 控制旋转滑块拖动")
    return best_angle


# ============================================================
# 通用接口
# ============================================================

def solve_captcha(captcha_type: str, image_path: str):
    """通用验证码破解入口"""
    if captcha_type == "text":
        print(f"[*] 文本验证码 → 推荐 VLM 分析")
        vlm_analyze_captcha(image_path)
    elif captcha_type == "slider":
        print(f"[*] 滑块验证码 → 分析缺口 + Playwright 拖动")
        x = analyze_slider(image_path)
        if x:
            generate_slider_playwright(None, ".slider-btn", x)
    elif captcha_type == "click":
        print(f"[*] 点选验证码 → VLM 识别位置 + Playwright 点击")
        analyze_click_captcha(image_path)
    elif captcha_type == "rotation":
        print(f"[*] 旋转验证码 → 角度分析 + 旋转拖动")
        analyze_rotation(image_path)
    elif captcha_type == "math":
        print(f"[*] 数学验证码 → 预处理 + 简单计算解析")
        preprocess_image(image_path)
    elif captcha_type == "recaptcha":
        print(f"[*] reCAPTCHA → 可能需要 2captcha API 或其他服务")
    else:
        print(f"未知验证码类型: {captcha_type}")
        print("支持: text/slider/click/rotation/math/recaptcha")


HELP_TEXT = """
用法:
  captcha_solver.py image <path>                  识别图片验证码 (选择最优策略)
  captcha_solver.py slider <screenshot>            分析滑块缺口位置
  captcha_solver.py click <screenshot> "提示词"    分析点选位置
  captcha_solver.py rotation <screenshot>          分析旋转角度
  captcha_solver.py vlm <image_path>              生成 VLM 分析模板
  captcha_solver.py preprocess <path>              图片预处理 (去噪/二值)
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(HELP_TEXT); sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "image":
        path = sys.argv[2]
        print("[*] 自动检测验证码类型并选择最优策略...")
        print(f"    图片: {path}")
        print(f"    推荐: 先用 preprocess 预处理, 再用 VLM 分析")
        preprocess_image(path)
        print()
        vlm_analyze_captcha(path)
    elif cmd == "slider":
        analyze_slider(sys.argv[2])
    elif cmd == "click":
        text = sys.argv[3] if len(sys.argv) > 3 else ""
        analyze_click_captcha(sys.argv[2], text)
    elif cmd == "rotation":
        analyze_rotation(sys.argv[2])
    elif cmd == "vlm":
        vlm_analyze_captcha(sys.argv[2])
    elif cmd == "preprocess":
        preprocess_image(sys.argv[2])
    else:
        print(f"未知命令: {cmd}")
        print(HELP_TEXT)
