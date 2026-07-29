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

# VLM 审美评分（可选）
_VLM_SCORER = None


def _get_vlm_scorer() -> Any:
    """懒加载 VLM 评分器。"""
    global _VLM_SCORER
    if _VLM_SCORER is None:
        try:
            from agents.aesthetic_scorer import AestheticScorer
            _VLM_SCORER = AestheticScorer(auto_start=False, verbose=False)
        except Exception:
            _VLM_SCORER = False  # 标记为不可用
    return _VLM_SCORER if _VLM_SCORER is not False else None


def aesthetic_score(image_path: str) -> dict[str, Any]:
    """VLM 审美评分（调用 Qwen3.5-9B）。"""
    scorer = _get_vlm_scorer()
    if scorer is None:
        return {"available": False, "error": "VLM scorer not available"}
    return scorer.score(image_path)


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


def _check_face_mediapipe(image_path: str) -> dict[str, Any] | None:
    """MediaPipe Face Detection — 对动漫脸效果好，无需额外模型文件。"""
    try:
        import mediapipe as mp
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return None
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        with mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.3
        ) as fd:
            results = fd.process(rgb)
            if results.detections:
                faces = []
                for d in results.detections:
                    box = d.location_data.relative_bounding_box
                    h, w, _ = img.shape
                    faces.append({
                        "x": int(box.xmin * w),
                        "y": int(box.ymin * h),
                        "w": int(box.width * w),
                        "h": int(box.height * h),
                        "confidence": round(d.score[0], 3),
                    })
                return {
                    "face_count": len(faces),
                    "max_confidence": max(f["confidence"] for f in faces),
                    "detections": faces[:5],
                    "ok": 0 < len(faces) <= 2,
                    "method": "mediapipe",
                }
    except ImportError:
        pass  # mediapipe not installed — skip
    except Exception:
        pass
    return None


def _check_face(image_path: str) -> dict[str, Any]:
    """人脸检测 — YOLO → OpenCV Haar cascade 降级。"""
    from model_manager import resolve_models_root

    models_root = resolve_models_root()
    model_path = models_root / ".." / "ultralytics" / "face_yolov8m.pt" if models_root else None
    alt_path = Path(r"C:\DrawingLive\ComfyUI\models\ultralytics\face_yolov8m.pt")

    # 尝试 YOLO
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
                    "method": "yolo",
                }

    # 降级：MediaPipe Face Detection（对动漫脸更友好，无需模型文件）
    mp_result = _check_face_mediapipe(image_path)
    if mp_result:
        return mp_result

    # 最终降级：OpenCV Haar cascade（built-in）
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            face_count = len(faces)
            max_conf = 0.7 if face_count > 0 else 0  # Haar doesn't give confidence scores

            # 眼部检测（对前 2 张脸做 cascaded eye detection）
            eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
            left_eyes, right_eyes = 0, 0
            for (x, y, w, h) in faces[:2]:
                face_roi = gray[y : y + h, x : x + w]
                eyes = eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=3, minSize=(10, 10))
                for (ex, ey, ew, eh) in eyes:
                    if ex + ew / 2 < w / 2:
                        left_eyes += 1
                    else:
                        right_eyes += 1

            return {
                "face_count": face_count,
                "max_confidence": max_conf,
                "detections": [{"x": int(x), "y": int(y), "w": int(w), "h": int(h), "confidence": max_conf}
                               for (x, y, w, h) in faces[:5]],
                "ok": 0 < face_count <= 2,
                "method": "haar",
                "eyes_left": left_eyes,
                "eyes_right": right_eyes,
            }
    except Exception:
        pass

    # 所有方法都不可用
    return {"face_count": None, "ok": True, "note": "人脸检测模型不可用，跳过"}


def _check_hand(image_path: str) -> dict[str, Any]:
    """手部检测 — YOLO → OpenCV 上半身推断降级。"""
    from model_manager import resolve_models_root

    models_root = resolve_models_root()
    model_path = models_root / ".." / "ultralytics" / "hand_yolov8s.pt" if models_root else None
    alt_path = Path(r"C:\DrawingLive\ComfyUI\models\ultralytics\hand_yolov8s.pt")

    # 尝试 YOLO
    for candidate in [model_path, alt_path]:
        if candidate and candidate.is_file():
            dets = _detect_objects(image_path, str(candidate))
            if dets and "error" not in dets[0]:
                hands = [d for d in dets if d.get("class") == 0]
                return {
                    "hand_count": len(hands),
                    "detections": hands[:5],
                    "ok": len(hands) <= 2,
                    "method": "yolo",
                }

    # 降级到 OpenCV 上半身检测（至少能判断画面中有人需要画手）
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            upper_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_upperbody.xml")
            bodies = upper_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(60, 60))
            body_count = len(bodies)
            # 没有手部模型，但可以报告身体数量作为参考
            return {
                "hand_count": None,
                "body_count": body_count,
                "ok": True,
                "note": f"手部模型不可用，检测到 {body_count} 个上半身" if body_count > 0 else "未检测到人物",
                "method": "haar-body",
            }
    except Exception:
        pass

    return {"hand_count": None, "ok": True, "note": "手部检测模型不可用，跳过"}


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

    # 6. VLM 审美评分（可选）
    vlm = aesthetic_score(image_path)
    if vlm.get("available"):
        result["aesthetic"] = {
            "face_score": vlm.get("face_score", -1),
            "composition_score": vlm.get("composition_score", -1),
            "color_score": vlm.get("color_score", -1),
            "overall_score": vlm.get("overall_score", -1),
            "feedback": vlm.get("overall_feedback", vlm.get("feedback", "")),
        }
    else:
        result["aesthetic"] = {"available": False}

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
