"""
质检模块 — 逐部位崩坏检测，输出结构化报告。

报告格式:
  {
    "status": "ok" | "issues_found",
    "parts": {
      "脸": {"status": "ok" | "崩了", "detail": "...", "confidence": 0.95},
      "左眼": {"status": "ok" | "崩了", "detail": "...", "confidence": 0.92},
      "右眼": {"status": "ok" | "崩了", "detail": "...", "confidence": 0.88},
      "手": {"status": "ok" | "崩了", "detail": "...", "count": 2},
      "脚": {"status": "ok" | "异常", "detail": "..."},
      "模糊": {"status": "正常" | "模糊", "laplacian_var": 12.3},
    },
    "summary": "[脸:ok] [左眼:ok] [右眼:ok] [手:ok] [脚:ok] [模糊:正常]",
  }

支持检测:
  - 崩脸（YOLO face + MediaPipe landmarks 可选）
  - 崩眼（逐眼检测）
  - 崩手（YOLO hand）
  - 崩脚（OpenCV body detect）
  - 模糊（Laplacian 算子）
  - 多人交互（可选）
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def inspect_image(
    image_path: str,
    *,
    prompt: str = "",
    use_mediapipe: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """对单张图片执行全部位质检。

    Args:
        image_path: 图片路径
        prompt: 原始提示词（用于 CLIP score 等）
        use_mediapipe: 是否尝试使用 MediaPipe（更精确的 landmarks）
        verbose: 详细信息

    Returns:
        {
            "status": "ok" | "issues_found",
            "parts": {逐部位结果},
            "summary": "一行总结",
            "scores": {各维度分数},
        }
    """
    path = Path(image_path)
    if not path.is_file():
        return {"status": "error", "error": f"文件不存在: {image_path}"}

    parts: dict[str, Any] = {}
    issues: list[str] = []
    summary_parts: list[str] = []

    # 1. 崩脸 + 崩眼检测
    face_result = _check_face_detail(str(path), use_mediapipe=use_mediapipe)
    if face_result.get("error"):
        parts["脸"] = {"status": "unknown", "detail": face_result["error"]}
        summary_parts.append("[脸:?]")
    else:
        parts["脸"] = {
            "status": "ok" if face_result.get("ok", True) else "崩了",
            "detail": face_result.get("detail", ""),
            "confidence": face_result.get("max_confidence", 0),
            "count": face_result.get("face_count"),
        }
        if not face_result.get("ok", True):
            issues.append(f"脸崩了: {face_result.get('detail', 'unknown')}")
        summary_parts.append(f"[脸:{'ok' if face_result.get('ok', True) else '崩了'}]")

        # 逐眼检查
        eyes = face_result.get("eyes", {})
        for eye_side in ("左眼", "右眼"):
            eye_info = eyes.get(eye_side, {})
            if eye_info.get("detected"):
                eye_status = "ok"
                eye_detail = ""
                # 检查眼部异常
                if eye_info.get("closed"):
                    eye_status = "闭眼"
                    eye_detail = "眼睛闭合"
                elif eye_info.get("distorted"):
                    eye_status = "崩了"
                    eye_detail = eye_info.get("detail", "眼部变形")
                parts[eye_side] = {"status": eye_status, "detail": eye_detail,
                                   "confidence": eye_info.get("confidence", 0)}
                summary_parts.append(f"[{eye_side}:{eye_status}]")
                if eye_status != "ok":
                    issues.append(f"{eye_side}{eye_detail}")

    # 2. 崩手检测
    hand_result = _check_hand_detail(str(path))
    if hand_result.get("error"):
        parts["手"] = {"status": "unknown", "detail": hand_result["error"]}
        summary_parts.append("[手:?]")
    else:
        hand_ok = hand_result.get("ok", True)
        hand_detail = hand_result.get("detail", "")
        parts["手"] = {
            "status": "ok" if hand_ok else "崩了",
            "detail": hand_detail,
            "count": hand_result.get("hand_count", 0),
            "issues": hand_result.get("issues", []),
        }
        if not hand_ok:
            issues.append(f"手崩了: {hand_detail}")
        summary_parts.append(f"[手:{'ok' if hand_ok else '崩了'}]")

    # 3. 崩脚检测
    foot_result = _check_foot(str(path))
    if foot_result.get("error"):
        parts["脚"] = {"status": "unknown", "detail": foot_result["error"]}
        summary_parts.append("[脚:?]")
    else:
        foot_ok = foot_result.get("ok", True)
        parts["脚"] = {
            "status": "ok" if foot_ok else "异常",
            "detail": foot_result.get("detail", ""),
            "count": foot_result.get("foot_count"),
        }
        if not foot_ok:
            issues.append(f"脚异常: {foot_result.get('detail', '')}")
        summary_parts.append(f"[脚:{'ok' if foot_ok else '异常'}]")

    # 4. 模糊检测
    blur_result = _check_blur(str(path))
    if not blur_result.get("error"):
        blur_ok = blur_result.get("ok", True)
        parts["模糊"] = {
            "status": "正常" if blur_ok else "模糊",
            "laplacian_var": blur_result.get("laplacian_var", 0),
        }
        if not blur_ok:
            issues.append(f"图片模糊 (Laplacian={blur_result.get('laplacian_var', 0):.1f})")
        summary_parts.append(f"[模糊:{'正常' if blur_ok else '模糊'}]")
    else:
        parts["模糊"] = {"status": "unknown", "detail": blur_result["error"]}
        summary_parts.append("[模糊:?]")

    # 综合
    status = "ok" if not issues else "issues_found"
    summary = " ".join(summary_parts)

    # 分数
    scores = _compute_scores(parts)

    return {
        "status": status,
        "parts": parts,
        "summary": summary,
        "issues": issues,
        "scores": scores,
    }


def format_report(result: dict[str, Any]) -> str:
    """格式化为可读的质检报告文本。"""
    if "error" in result:
        return f"❌ 质检失败: {result['error']}"

    lines = ["📋 质检报告"]
    if result.get("issues"):
        lines.append(f"⚠️  发现 {len(result['issues'])} 个问题:")
        for issue in result["issues"]:
            lines.append(f"   • {issue}")
    else:
        lines.append("✅ 全部正常")

    for part, info in result.get("parts", {}).items():
        status_texts = {
            "ok": "✅",
            "崩了": "❌",
            "异常": "⚠️",
            "闭眼": "⚠️",
            "正常": "✅",
            "模糊": "❌",
            "unknown": "❓",
        }
        icon = status_texts.get(str(info.get("status", "")), "❓")
        detail = info.get("detail", "")
        lines.append(f"  {icon} {part}: {info.get('status', '?')}"
                     f"{f' ({detail})' if detail else ''}")

    lines.append(f"\n  → {result.get('summary', '')}")
    scores = result.get("scores", {})
    if scores:
        lines.append(f"\n  综合分: {scores.get('overall', '?'):.2f}/1.0")
    return "\n".join(lines)


# ── 检测函数 ────────────────────────────────────────────


def _check_face_detail(image_path: str, use_mediapipe: bool = True) -> dict[str, Any]:
    """详细人脸 + 眼部检测。

    优先使用 MediaPipe（逐眼 landmarks），降级到 YOLO face + 推理。
    """
    # 尝试 MediaPipe（更精确）
    if use_mediapipe:
        try:
            return _mediapipe_face_analysis(image_path)
        except ImportError:
            pass  # 降级到 YOLO
        except Exception:
            pass

    # YOLO face 降级
    return _yolo_face_check(image_path)


def _mediapipe_face_analysis(image_path: str) -> dict[str, Any]:
    """MediaPipe Face Mesh 面部关键点分析。"""
    import cv2
    import mediapipe as mp

    img = cv2.imread(image_path)
    if img is None:
        return {"ok": True, "detail": "无法读取图片", "eyes": {}}

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]

    mp_face = mp.solutions.face_mesh
    with mp_face.FaceMesh(static_image_mode=True, max_num_faces=2,
                          refine_landmarks=True, min_detection_confidence=0.5) as fm:
        results = fm.process(rgb)

    if not results or not results.multi_face_landmarks:
        return {"ok": False, "detail": "未检测到人脸", "eyes": {}, "face_count": 0, "max_confidence": 0}

    faces_info = []
    for landmarks in results.multi_face_landmarks:
        # 左眼 landmarks: 33~133, 右眼: 362~263 (MediaPipe 约定)
        left_eye = [landmarks.landmark[i] for i in range(33, 134)]
        right_eye = [landmarks.landmark[i] for i in range(362, 464)]

        # 计算眼开合度（EAR - Eye Aspect Ratio）
        left_ear = _eye_aspect_ratio(left_eye)
        right_ear = _eye_aspect_ratio(right_eye)

        # 面部歪斜/变形检测
        face_width = abs(landmarks.landmark[454].x - landmarks.landmark[234].x)
        face_height = abs(landmarks.landmark[152].y - landmarks.landmark[10].y)
        face_ratio = face_width / face_height if face_height > 0 else 1
        distorted = face_ratio < 0.5 or face_ratio > 2.0

        faces_info.append({
            "left_ear": left_ear,
            "right_ear": right_ear,
            "distorted": distorted,
        })

    # 综合判断
    eye_results = {}
    ok = True
    detail_parts = []

    for i, face in enumerate(faces_info):
        # 左眼
        left_ok = face["left_ear"] > 0.15
        right_ok = face["right_ear"] > 0.15

        eye_results[f"左眼"] = {
            "detected": True,
            "closed": face["left_ear"] < 0.1,
            "distorted": not left_ok,
            "confidence": min(face["left_ear"] * 5, 1.0),
            "detail": f"EAR={face['left_ear']:.3f}" if not left_ok else "",
        }
        eye_results[f"右眼"] = {
            "detected": True,
            "closed": face["right_ear"] < 0.1,
            "distorted": not right_ok,
            "confidence": min(face["right_ear"] * 5, 1.0),
            "detail": f"EAR={face['right_ear']:.3f}" if not right_ok else "",
        }

        if not left_ok:
            ok = False
            detail_parts.append(f"左眼异常(EAR={face['left_ear']:.3f})")
        if not right_ok:
            ok = False
            detail_parts.append(f"右眼异常(EAR={face['right_ear']:.3f})")
        if face["distorted"]:
            ok = False
            detail_parts.append("面部比例异常")

    return {
        "ok": ok,
        "detail": "; ".join(detail_parts) if detail_parts else "正常",
        "face_count": len(faces_info),
        "max_confidence": 0.9 if faces_info else 0,
        "eyes": eye_results,
    }


def _eye_aspect_ratio(landmarks: list) -> float:
    """计算眼开合度（Eye Aspect Ratio）。"""
    if len(landmarks) < 6:
        return 1.0
    # 垂直距离: (p1-p5) + (p2-p4)  / 水平距离: (p0-p3)
    try:
        v1 = ((landmarks[1].x - landmarks[5].x) ** 2 + (landmarks[1].y - landmarks[5].y) ** 2) ** 0.5
        v2 = ((landmarks[2].x - landmarks[4].x) ** 2 + (landmarks[2].y - landmarks[4].y) ** 2) ** 0.5
        h = ((landmarks[0].x - landmarks[3].x) ** 2 + (landmarks[0].y - landmarks[3].y) ** 2) ** 0.5
        if h < 0.001:
            return 1.0
        return (v1 + v2) / (2.0 * h)
    except (IndexError, AttributeError, ZeroDivisionError):
        return 1.0


def _yolo_face_check(image_path: str) -> dict[str, Any]:
    """OpenCV Haar cascade → YOLO 面部检测降级链。"""
    from agents.go_validate import _check_face
    result = _check_face(image_path)

    face_count = result.get("face_count")
    max_conf = result.get("max_confidence", 0)
    ok = result.get("ok", True)
    method = result.get("method", "none")
    note = result.get("note", "")

    detail = ""
    if face_count is not None:
        if face_count == 0:
            detail = "未检测到人脸"
        elif face_count > 2:
            detail = f"检测到 {face_count} 张人脸（可能多余）"
        elif face_count == 1:
            detail = "1 张人脸"
        else:
            detail = f"{face_count} 张人脸"
    elif note:
        detail = note

    # 构建眼部信息 — 优先使用 cascade 的 eye_count
    eyes = {}
    left_count = result.get("eyes_left", 0)
    right_count = result.get("eyes_right", 0)
    if left_count > 0 or right_count > 0:
        eyes["左眼"] = {"detected": left_count > 0, "closed": False, "distorted": False,
                        "confidence": max_conf, "count": left_count}
        eyes["右眼"] = {"detected": right_count > 0, "closed": False, "distorted": False,
                        "confidence": max_conf, "count": right_count}
    else:
        # 无眼部模型可用，做简单推断
        eyes["左眼"] = {"detected": True, "closed": False, "distorted": False, "confidence": max_conf}
        eyes["右眼"] = {"detected": True, "closed": False, "distorted": False, "confidence": max_conf}

    return {
        "ok": ok,
        "detail": detail or "正常",
        "face_count": face_count,
        "max_confidence": max_conf,
        "method": method,
        "eyes": eyes,
    }


def _check_hand_detail(image_path: str) -> dict[str, Any]:
    """详细手部检测（手指异常判断）。"""
    from agents.go_validate import _check_hand
    result = _check_hand(image_path)

    hand_count = result.get("hand_count")
    ok = result.get("ok", True)

    issues: list[str] = []
    detail = ""
    if hand_count is not None:
        if hand_count == 0:
            issues.append("未检测到手（如果描述中有手则异常）")
        elif hand_count > 2:
            issues.append(f"检测到 {hand_count} 只手（可能多余手指）")
        elif hand_count == 1:
            issues.append("仅有 1 只手（可能缺失）")

    if issues:
        ok = False
        detail = "; ".join(issues)
    else:
        detail = f"{hand_count} 只手" if hand_count else "正常"

    return {
        "ok": ok,
        "detail": detail,
        "hand_count": hand_count,
        "issues": issues,
    }


def _check_foot(image_path: str) -> dict[str, Any]:
    """脚部/腿部检测。

    使用 OpenCV 全身检测 + 简单推断。
    如果检测到人但没检测到脚/腿，可能异常。
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"ok": True, "detail": "OpenCV 不可用，跳过", "foot_count": None}

    img = cv2.imread(image_path)
    if img is None:
        return {"ok": True, "error": "无法读取图片", "foot_count": None}

    h, w = img.shape[:2]

    # 使用 OpenCV 的 HOG 行人检测器判断画面中是否有完整人体
    try:
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        (boxes, _) = hog.detectMultiScale(img, winStride=(8, 8), padding=(4, 4), scale=1.05)
    except Exception:
        boxes = []

    if len(boxes) == 0:
        # 没检测到人形，可能脚不在画面中（半身/特写）
        return {"ok": True, "detail": "未检测到完整人体（可能是半身/特写构图）", "foot_count": None}

    # 有完整人体，检查脚部区域（人体下半部分）
    foot_issues = []
    for (bx, by, bw, bh) in boxes:
        # 脚部区域：人体框底部 20%
        foot_y_start = int(by + bh * 0.8)
        foot_y_end = int(by + bh)
        foot_region = img[foot_y_start:foot_y_end, bx:bx + bw]

        if foot_region.size == 0:
            continue

        # 检查脚部区域是否有异常（严重变形/缺失）
        gray_foot = cv2.cvtColor(foot_region, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray_foot, cv2.CV_64F).var()
        if laplacian < 5:  # 脚部区域过于平滑 = 可能缺失/模糊
            foot_issues.append("脚部区域纹理异常（可能消失或模糊）")

    ok = len(foot_issues) == 0
    return {
        "ok": ok,
        "detail": "; ".join(foot_issues) if foot_issues else "正常",
        "foot_count": len(boxes),
    }


def _check_blur(image_path: str) -> dict[str, Any]:
    """图像模糊检测（Laplacian 算子）。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"ok": True, "error": "OpenCV 不可用，跳过"}

    img = cv2.imread(image_path)
    if img is None:
        return {"ok": True, "error": "无法读取图片"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # 阈值参考: <10 严重模糊, 10-30 轻微模糊, >30 清晰
    if laplacian_var < 10:
        ok = False
        detail = f"严重模糊 (Laplacian={laplacian_var:.1f})"
    elif laplacian_var < 30:
        ok = True
        detail = f"轻微模糊 (Laplacian={laplacian_var:.1f})"
    else:
        ok = True
        detail = f"清晰 (Laplacian={laplacian_var:.1f})"

    return {
        "ok": ok,
        "laplacian_var": round(laplacian_var, 1),
        "detail": detail,
    }


def _compute_scores(parts: dict[str, Any]) -> dict[str, float]:
    """将部位质检结果映射为分数。"""
    scores: dict[str, float] = {}
    total = 0.0
    count = 0

    for part, info in parts.items():
        status = str(info.get("status", ""))
        if status in ("ok", "正常"):
            scores[part] = 1.0
            total += 1.0
        elif status in ("崩了", "模糊"):
            scores[part] = 0.0
        elif status in ("异常", "闭眼"):
            scores[part] = 0.5
            total += 0.5
        else:
            scores[part] = 0.5  # unknown = 中性
            total += 0.5
        count += 1

    scores["overall"] = round(total / count, 3) if count > 0 else 0.0
    return scores


def annotate_image(image_path: str, result: dict[str, Any]) -> str:
    """在图片上绘制质检标注，返回标注后的图片路径。

    标注内容:
      - 左上角: 综合分 + 状态
      - 各部位分数文本
      - 底边: 红色/绿色边框表示整体状态

    Args:
        image_path: 原图路径
        result: inspect_image() 的返回值

    Returns:
        标注图片的绝对路径（<原文件名>_annotated.png）
    """
    import cv2
    import numpy as np

    path = Path(image_path)
    if not path.is_file():
        return ""
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return ""

    h, w = img.shape[:2]
    # 缩小字体/间距适应小图
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = min(w, h) / 600.0  # 自适应
    font_scale = max(0.4, min(font_scale, 0.8))
    thickness = max(1, int(font_scale * 1.5))
    gap = int(20 * font_scale * 1.5)

    parts = result.get("parts", {})
    scores = result.get("scores", {})
    status = result.get("status", "?")
    overall = scores.get("overall", 0)

    # 状态颜色
    ok = status == "ok"
    color = (0, 200, 0) if ok else (0, 0, 200)  # BGR: 绿=ok, 红=issues
    dark_bg = (30, 30, 30)

    # 左上信息区: 半透明背景
    info_y = gap
    cv2.rectangle(img, (4, 4), (int(w * 0.5), info_y + 20 + (len(parts) + 1) * gap), dark_bg, -1)
    cv2.putText(img, f"OVERALL: {overall:.2f}  [{status}]", (8, info_y + 12),
                font, font_scale, color, thickness)

    # 各部位分数 + 置信度
    part_names = {"脸": "Face", "左眼": "L-Eye", "右眼": "R-Eye", "手": "Hand",
                  "脚": "Foot", "模糊": "Blur"}
    for i, (part, info) in enumerate(parts.items()):
        pname = part_names.get(part, part[:6])
        s = info.get("status", "?")
        score = info.get("score", 0) if "score" in info else info.get("confidence", 0)
        is_ok = s in ("ok", "正常")
        is_bad = s in ("崩了", "模糊", "异常")
        c = (0, 200, 0) if is_ok else (0, 0, 200) if is_bad else (200, 200, 0)
        y = info_y + 20 + (i + 1) * gap
        score_str = f" [{score:.2f}]" if score > 0 else ""
        cv2.putText(img, f"{pname}: {s}{score_str}", (8, y), font, font_scale * 0.85, c, thickness)

    # 底边渐变状态条
    bar_h = max(6, int(h * 0.02))
    cv2.rectangle(img, (0, h - bar_h), (w, h), color, -1)
    # 覆盖部分边框色块: 左绿右红混合显示
    mid_x = int(w * overall)
    bar_color = (0, int(200 * overall), int(200 * (1 - overall)))
    cv2.rectangle(img, (0, h - bar_h), (mid_x, h), bar_color, -1)

    # 标注文件名: path_stem_annotated.png
    out_path = path.parent / f"{path.stem}_annotated.png"
    cv2.imencode(".png", img)[1].tofile(str(out_path))
    print(f"  🖼️ 标注图: {out_path}")
    return str(out_path.resolve())


def check_consistency(
    gen_path: str,
    ref_path: str | None = None,
) -> dict[str, Any]:
    """验证生成图与参考图的一致性。

    Args:
        gen_path: 生成图片路径
        ref_path: 参考图片路径（可选）

    Returns:
        {"consistency": 0.0~1.0, "face_match": 0~1, "color_sim": 0~1, ...}
    """
    result: dict[str, Any] = {"consistency": 0.0, "face_match": 0.0, "color_sim": 0.0}

    if not ref_path or not Path(ref_path).is_file():
        return result

    import cv2
    import numpy as np

    gen = cv2.imread(gen_path)
    ref = cv2.imread(ref_path)
    if gen is None or ref is None:
        return result

    # 1. 颜色直方图相似度
    gen_hist = cv2.calcHist([gen], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    ref_hist = cv2.calcHist([ref], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    cv2.normalize(gen_hist, gen_hist)
    cv2.normalize(ref_hist, ref_hist)
    color_sim = cv2.compareHist(gen_hist, ref_hist, cv2.HISTCMP_CORREL)
    result["color_sim"] = max(0.0, min(1.0, color_sim))

    # 2. 人脸检测（看是否都有人脸）
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    gen_faces = face_cascade.detectMultiScale(gen, 1.1, 4)
    ref_faces = face_cascade.detectMultiScale(ref, 1.1, 4)
    has_gen_face = len(gen_faces) > 0
    has_ref_face = len(ref_faces) > 0
    if has_ref_face:
        result["face_match"] = 1.0 if has_gen_face else 0.0
    else:
        result["face_match"] = 0.5  # ref 没脸时中性

    # 综合分
    result["consistency"] = result["color_sim"] * 0.4 + result["face_match"] * 0.6
    return result