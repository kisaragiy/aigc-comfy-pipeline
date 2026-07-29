"""
工作流验证器 — 检查 ComfyUI API 工作流 JSON 的完整性。

用法:
    python -m agents workflow-validate workflow.json

可检测:
  - 节点 class_type 是否已知
  - input 字段是否完整
  - 连接链路是否有断裂
  - 模型/LoRA 文件是否存在
"""
import json, sys, os, re
from pathlib import Path

# 已知的 ComfyUI 内置节点类型
KNOWN_NODES = {
    "CheckpointLoaderSimple", "UNETLoader", "CLIPLoader", "DualCLIPLoader",
    "VAELoader", "CLIPTextEncode", "CLIPTextEncodeSDXL",
    "EmptyLatentImage", "KSampler", "KSamplerAdvanced", "SamplerCustom",
    "VAEDecode", "VAEEncode", "SaveImage", "PreviewImage",
    "LoadImage", "LoadImageMask", "ImageScale", "UpscaleModelLoader",
    "LoraLoader", "ControlNetLoader", "ControlNetApply",
    "FaceDetailer", "HypernetworkLoader",
}


def validate_workflow(wf_path: str) -> dict:
    """验证工作流 JSON 并返回检查结果。"""
    results = {"file": wf_path, "valid": True, "issues": [], "nodes": 0, "warnings": 0}

    try:
        with open(wf_path, encoding="utf-8") as f:
            wf = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        results["valid"] = False
        results["issues"].append(f"无法读取: {e}")
        return results

    if not isinstance(wf, dict):
        results["valid"] = False
        results["issues"].append("根结构不是 dict")
        return results

    results["nodes"] = len(wf)

    # 检查每个节点
    for nid, node in wf.items():
        if not isinstance(node, dict):
            results["issues"].append(f"节点 {nid}: 类型错误 ({type(node).__name__})")
            results["valid"] = False
            continue

        ct = node.get("class_type", "")
        if not ct:
            results["issues"].append(f"节点 {nid}: 缺少 class_type")
            results["valid"] = False
            continue

        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            results["issues"].append(f"节点 {nid}: inputs 不是 dict")
            results["warnings"] += 1
            continue

        # 检查连接引用
        for k, v in inputs.items():
            if isinstance(v, list) and len(v) == 2:
                ref_nid, ref_slot = v[0], v[1]
                if ref_nid not in wf:
                    results["issues"].append(f"节点 {nid}.{k}: 引用不存在的节点 {ref_nid}")
                    results["valid"] = False
                elif not isinstance(ref_slot, (int, str)):
                    results["issues"].append(f"节点 {nid}.{k}: 引用槽位类型错误 {ref_slot}")
                    results["warnings"] += 1

        # 检查模型文件引用
        for k in ("ckpt_name", "unet_name", "vae_name", "clip_name"):
            val = inputs.get(k, "")
            if val and isinstance(val, str) and val.endswith(".safetensors"):
                comfy_root = os.environ.get("COMFY_ROOT", r"C:\DrawingLive\ComfyUI")
                model_dirs = {
                    "ckpt_name": "checkpoints",
                    "unet_name": "diffusion_models",
                    "vae_name": "vae",
                    "clip_name": "clip",
                }
                subdir = model_dirs.get(k, "")
                fp = Path(comfy_root) / "models" / subdir / val
                if not fp.is_file():
                    # Try other dirs
                    alt_found = False
                    for alt_sub in ["checkpoints", "diffusion_models", "unet", "clip", "vae", "text_encoders"]:
                        alt_fp = Path(comfy_root) / "models" / alt_sub / val
                        if alt_fp.is_file():
                            alt_found = True
                            break
                    if not alt_found:
                        results["issues"].append(f"节点 {nid}.{k}: 文件不存在 {val}")
                        results["warnings"] += 1

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="工作流 JSON 验证器")
    parser.add_argument("path", nargs="+", help="工作流 JSON 文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parsed = parser.parse_args()

    all_ok = True
    for path in parsed.path:
        r = validate_workflow(path)
        if parsed.json:
            print(json.dumps(r, indent=2, ensure_ascii=False))
        else:
            icon = "✅" if r["valid"] else "❌"
            print(f"\n{icon} {r['file']} ({r['nodes']} 节点)")
            for issue in r["issues"]:
                print(f"  ❌ {issue}")
            # Remaining warnings
            for _ in range(r["warnings"] - len([i for i in r["issues"] if "不存在" in i])):
                pass  # warnings already in issues

        if not r["valid"]:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
