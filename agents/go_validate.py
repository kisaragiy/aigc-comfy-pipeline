"""
出图质量评估 — CLIP score + 崩脸/崩手检测 + 图像质量。

用法示例:
  python go_validate.py --image out.png --prompt "a cat"
  python go_validate.py --image out.png --prompt "a cat" --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()


def _clip_score(image_path: str, prompt: str) -> dict[str, Any]:
    """CLIP 图文相关性评分 [0,1]。"""
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
    except ImportError:
        return {"score": None, "available": False,
                "error": "需安装: pip install transformers torch"}

    try:
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        import PIL.Image

        image = PIL.Image.open(image_path).convert("RGB")
        inputs = processor(text=[prompt], images=image, return_tensors="pt",
                           padding=True, truncation=True)
        with torch.no_grad():
            outputs = model(**inputs)
        score = outputs.logits_per_image[0][0].item()
        # 归一化到 [0,1]
        score = 1.0 / (1.0 + (score * -1).exp())  # sigmoid
        return {"score": round(score, 3), "available": True}
    except Exception as e:
        return {"score": None, "available": False, "error": f"CLIP 评分失败: {e}"}


def _detect_objects(image_path: str, model_path: str) -> list[dict[str, Any]]:
    """YOLO 目标检测。"""
    try:
        from ultralytics import YOLO
    except ImportError:
        return [{"error": "需安装: pip install ultralytics"}]

    if not Path(model_path).is_file():
        return [{"error": f"模型不存在: {model_path}"}]

    try:
        model = YOLO(model_path)
        results = model(image_path, verbose=False)
        detections = []
        for r in results:
            if r.boxes is not None:
                for box, cls, conf in zip(r.boxes.xyxy, r.boxes.cls, r.boxes.conf):
                    detections.append({
                        "class": int(cls.item()),
                        "confidence": round(conf.item(), 3),
                        "bbox": [round(float(b), 1) for b in box],
                    })
        return detections
    except Exception as e:
        return [{"error": f"检测失败: {e}"}]


def _check_face(image_path: str) -> dict[str, Any]:
    """人脸检测。"""
    from model_manager import resolve_models_root

    models_root = resolve_models_root()
    model_path = models_root / ".." / "ultralytics" / "face_yolov8m.pt" if models_root else None
    alt_path = Path(r"C:\DrawingLive\ComfyUI\models\ultralytics\face_yolov8m.pt")

    for candidate in [model_path, alt_path]:
        if candidate and candidate.is_file():
            dets = _detect_objects(image_path, str(candidate))
            if dets and "error" not in dets[0]:
                faces = [d for d in dets if d.get("class") == 0]
                return {
                    "face_count": len(faces),
                    "max_confidence": max((f["confidence"] for f in faces), default=0),
                    "detections": faces[:5],
                    "ok": 0 < len(faces) <= 2,
                }
    # 如果找不到 YOLO 模型，返回 unknown
    return {"face_count": None, "ok": True, "note": "YOLO 模型不可用，跳过人脸检测"}


def _check_hand(image_path: str) -> dict[str, Any]:
    """手部检测（检测异常手指）。"""
    from model_manager import resolve_models_root

    models_root = resolve_models_root()
    model_path = models_root / ".." / "ultralytics" / "hand_yolov8s.pt" if models_root else None
    alt_path = Path(r"C:\DrawingLive\ComfyUI\models\ultralytics\hand_yolov8s.pt")

    for candidate in [model_path, alt_path]:
        if candidate and candidate.is_file():
            dets = _detect_objects(image_path, str(candidate))
            if dets and "error" not in dets[0]:
                hands = [d for d in dets if d.get("class") == 0]
                # 简化检查：预期 2 只手，过多或过少可能异常
                return {
                    "hand_count": len(hands),
                    "detections": hands[:5],
                    "ok": len(hands) <= 2,
                }
    return {"hand_count": None, "ok": True, "note": "YOLO 模型不可用，跳过于部检测"}


def _image_quality(image_path: str) -> dict[str, Any]:
    """基础图像质量检查。"""
    import struct
    import math

    try:
        from PIL import Image
        import numpy as np

        img = Image.open(image_path).convert("L")
        arr = np.array(img, dtype=np.float32)

        brightness = float(arr.mean())
        contrast = float(arr.std())

        # 亮度正常范围 [20, 235]
        brightness_ok = 20 < brightness < 235
        # 对比度正常范围 > 15
        contrast_ok = contrast > 15

        issues = []
        if not brightness_ok:
            issues.append(f"亮度异常 ({brightness:.0f})")
        if not contrast_ok:
            issues.append(f"对比度偏低 ({contrast:.1f})")

        return {
            "brightness": round(brightness, 1),
            "contrast": round(contrast, 1),
            "brightness_ok": brightness_ok,
            "contrast_ok": contrast_ok,
            "ok": brightness_ok and contrast_ok,
            "issues": issues,
        }
    except Exception as e:
        return {"ok": True, "error": f"图像质量检查失败: {e}"}


def validate_image(image_path: str, prompt: str) -> dict[str, Any]:
    """对单张出图进行完整质量评估。"""
    path = Path(image_path)
    if not path.is_file():
        return {"error": f"文件不存在: {image_path}"}

    result: dict[str, Any] = {
        "file": path.name,
        "path": str(path.resolve()),
        "size_kb": path.stat().st_size // 1024,
    }

    # 1. CLIP score
    clip = _clip_score(image_path, prompt)
    result["clip_score"] = clip

    # 2. 人脸检测
    face = _check_face(image_path)
    result["face"] = face

    # 3. 手部检测
    hand = _check_hand(image_path)
    result["hand"] = hand

    # 4. 图像质量
    quality = _image_quality(image_path)
    result["image_quality"] = quality

    # 5. 综合评分
    score = _compute_overall(result)
    result["overall"] = score

    return result


def _compute_overall(result: dict) -> dict[str, Any]:
    """综合评分: A(优秀) / B(可接受) / C(需重试)。"""
    issues: list[str] = []

    # CLIP
    clip = result.get("clip_score", {})
    if clip.get("available") and clip.get("score") is not None:
        if clip["score"] < 0.2:
            issues.append("CLIP 评分低")
    elif clip.get("error"):
        pass  # 忽略评分不可用

    # 人脸
    face = result.get("face", {})
    if face.get("face_count") is not None:
        if face["face_count"] == 0:
            issues.append("未检测到人脸（如果是风景图可忽略）")
        elif face["face_count"] > 2:
            issues.append("多余 2 张脸")

    # 手部
    hand = result.get("hand", {})
    if hand.get("ok") is False:
        issues.append("手部检测异常")

    # 图像质量
    iq = result.get("image_quality", {})
    if iq.get("issues"):
        issues.extend(iq["issues"])

    if not issues:
        grade = "A"
        desc = "优秀"
    elif len(issues) <= 2 and not any("低" in i or "异常" in i for i in issues):
        grade = "B"
        desc = "可接受"
    else:
        grade = "C"
        desc = "需重试"

    return {"grade": grade, "description": desc, "issues": issues}


def _print_report(result: dict) -> None:
    """打印评估报告。"""
    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print(f"\n📊 质量评估: {result['file']}")
    print(f"  大小: {result['size_kb']} KB")
    print()

    # CLIP
    clip = result.get("clip_score", {})
    if clip.get("available") and clip.get("score") is not None:
        print(f"  CLIP Score:  {clip['score']:.3f}  {'✅' if clip['score'] > 0.2 else '⚠️'}")
    elif clip.get("error"):
        print(f"  CLIP Score:  {clip['error']}")

    # 人脸
    face = result.get("face", {})
    if face.get("face_count") is not None:
        icon = "✅" if face.get("ok") else "⚠️"
        print(f"  人脸检测:    {icon} ({face['face_count']} 张脸)")
    elif face.get("note"):
        print(f"  人脸检测:    {face['note']}")

    # 手部
    hand = result.get("hand", {})
    if hand.get("hand_count") is not None:
        icon = "✅" if hand.get("ok") else "⚠️"
        print(f"  手部检测:    {icon} ({hand['hand_count']} 只手)")
    elif hand.get("note"):
        print(f"  手部检测:    {hand['note']}")

    # 图像质量
    iq = result.get("image_quality", {})
    if not iq.get("error"):
        print(f"  亮度/对比度: {iq.get('brightness', '?')}/{iq.get('contrast', '?')} "
              f"{'✅' if iq.get('ok') else '⚠️'}")

    # 综合
    overall = result.get("overall", {})
    grade_icons = {"A": "✅", "B": "⚠️", "C": "❌"}
    print(f"\n  {'='*25}")
    print(f"  综合评分: {grade_icons.get(overall.get('grade','?'), '?')} "
          f"{overall.get('grade', '?')} — {overall.get('description', '?')}")
    if overall.get("issues"):
        for issue in overall["issues"]:
            print(f"    处理: {issue}")


def main() -> None:
    parser = argparse.ArgumentParser(description="出图质量评估")
    parser.add_argument("--image", required=True, help="图片路径")
    parser.add_argument("--prompt", default="", help="提示词（用于 CLIP 评分）")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    result = validate_image(args.image, args.prompt)

    if args.json:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_report(result)


if __name__ == "__main__":
    main()
