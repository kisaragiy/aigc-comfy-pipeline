"""质检假阴性对比：Ultralytics YOLO vs OpenCV Cascade + 新版 3 层检测链。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from workshop.inspect.inspector import _ultralytics_face_check, _yolo_face_check, _mediapipe_face_analysis


def safe_detector(detector_fn, path_str):
    """包装检测器，捕获异常。"""
    try:
        return detector_fn(path_str)
    except Exception as e:
        return {"error": str(e), "face_count": 0, "ok": False}


def run_comparison(image_dir: str | Path) -> dict:
    img_dir = Path(image_dir)
    images = sorted(img_dir.glob("*.png")) + sorted(img_dir.glob("*.jpg"))
    if not images:
        return {"error": f"目录 {image_dir} 没有图片", "total": 0}

    results = []
    for img_path in images[:60]:  # 最多处理 60 张
        ps = str(img_path)
        mp = safe_detector(_mediapipe_face_analysis, ps)
        yolo = safe_detector(_ultralytics_face_check, ps)
        cv = safe_detector(_yolo_face_check, ps)

        mp_faces = mp.get("face_count", 0)
        yolo_faces = yolo.get("face_count", 0)
        cv_faces = cv.get("face_count", 0)
        mp_ok = mp_faces > 0
        yolo_ok = yolo_faces > 0
        cv_ok = cv_faces > 0

        if not mp_ok and yolo_ok:
            fn_type = "YOLO救回"
        elif not mp_ok and not yolo_ok and cv_ok:
            fn_type = "Cascade救回"
        elif mp_ok:
            fn_type = "都检出了" if yolo_ok else "仅MediaPipe"
        else:
            fn_type = "都没检出"

        results.append({
            "name": img_path.name,
            "mp": mp_faces, "yolo": yolo_faces, "cv": cv_faces,
            "mp_ok": mp_ok, "yolo_ok": yolo_ok, "cv_ok": cv_ok,
            "yolo_conf": round(yolo.get("max_confidence", 0), 3),
            "type": fn_type,
        })

    n = len(results)
    if n == 0:
        return {"total": 0}

    mp_ok_n = sum(1 for r in results if r["mp_ok"])
    yolo_ok_n = sum(1 for r in results if r["yolo_ok"])
    yolo_saved = sum(1 for r in results if r["type"] == "YOLO救回")
    cascade_saved = sum(1 for r in results if r["type"] == "Cascade救回")
    none_n = sum(1 for r in results if r["type"] == "都没检出")

    return {
        "total": n,
        "mp_ok": mp_ok_n,
        "yolo_ok": yolo_ok_n,
        "yolo_saved": yolo_saved,
        "cascade_saved": cascade_saved,
        "none_n": none_n,
        "mp_only": sum(1 for r in results if r["type"] == "仅MediaPipe"),
        "fn_before_pct": round((1 - mp_ok_n / n) * 100, 1),
        "fn_after_pct": round((1 - yolo_ok_n / n) * 100, 1),
        "improvement_pct": round((yolo_saved / n) * 100, 1),
        "fn_list": [r for r in results if r["type"] == "YOLO救回"],
        "details": results,
    }


def print_report(r: dict) -> None:
    print("=" * 60)
    print("质检假阴性对比报告")
    print("=" * 60)
    print(f"图片总数: {r['total']}")
    print(f"MediaPipe: {r['mp_ok']}/{r['total']} ({100 - r['fn_before_pct']}% 检出)")
    print(f"YOLO:      {r['yolo_ok']}/{r['total']} ({100 - r['fn_after_pct']}% 检出)")
    print(f"YOLO 救回(假阴性): {r['yolo_saved']}")
    print(f"Cascade 救回:       {r['cascade_saved']}")
    print(f"都没检出:           {r['none_n']}")
    print(f"仅 MediaPipe 检出:  {r['mp_only']}")
    print()
    print(f"假阴性率: {r['fn_before_pct']}% → {r['fn_after_pct']}%")
    print(f"改善:     {r['improvement_pct']}%")
    print()
    if r["fn_list"]:
        print("YOLO 救回的图片 (MediaPipe 漏检):")
        for img in r["fn_list"][:10]:
            print(f"  ✅ {img['name']}: YOLO={img['yolo']}脸 conf={img['yolo_conf']}")
    else:
        print("✅ 没有新增 YOLO 检出")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", nargs="?", default=r"C:\DrawingLive\ComfyUI\output")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    result = run_comparison(args.dir)
    if "error" in result:
        print(result["error"])
        sys.exit(1)
    print_report(result)
    if args.verbose:
        for d in result["details"]:
            print(f"  {d['name']:40s} MP={d['mp']} YOLO={d['yolo']}({d['yolo_conf']}) CV={d['cv']} → {d['type']}")
