"""视频质检探路 — 先用 HunyuanVideo I2V 出一段视频（素材），再抽帧测 VLM 判质可行性

目的：视频领域专家会议第一仗 P0"视频门禁可行性"探路。
  第1步：用已有图 → I2V 出 480P 33帧 视频（lightx2v rank32, 4步, 快~33s）当素材
  第2步：ffmpeg 抽帧（首/中/尾）
  第3步：VLM(qwen3-vl) 逐帧判——能不能查"崩坏/鬼影/闪烁/运动
依据：hunyuanvideo-15-comfyui skill（注意：CLIP 路径已实测修正为 text_encoders/qwen-image/）
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
CKPT = "hunyuanvideo1.5_720p_i2v_cfg_distilled_fp8_scaled.safetensors"
CLIP = r"qwen-image\qwen_2.5_vl_7b_fp8_scaled.safetensors"
VAE = "hunyuanvideo15_vae_fp16.safetensors"
SIGCLIP = "sigclip_vision_patch14_384.safetensors"
LORA = "lightx2v_I2V_14B_480p_cfg_step_distill_rank32_bf16.safetensors"
FIRST_IMG = "hy_vid_first.png"
W, H, LEN = 848, 480, 33
PROMPT = "a girl in maid outfit, gentle swaying hair, subtle movement, natural motion, warm light"
NEG = ""


def http_():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def submit(wf, timeout=300):
    body = json.dumps({"prompt": wf}).encode()
    req = urllib.request.Request(COMFY + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    r = json.loads(http_().open(req, timeout=30).read())
    if "error" in r:
        raise RuntimeError(str(r["error"])[:400])
    pid = r["prompt_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            d = json.loads(http_().open(COMFY + f"/history/{pid}", timeout=5).read())
            if pid in d:
                files = []
                for node in d[pid].get("outputs", {}).values():
                    for img in node.get("images", []):
                        files.append((img.get("subfolder", ""), img["filename"]))
                return files, pid
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("生成超时")


def build_i2v():
    wf = {}
    n = [0]

    def nxt():
        n[0] += 1
        return str(n[0])

    n1 = nxt()
    wf[n1] = {"class_type": "UNETLoader", "inputs": {"unet_name": CKPT, "weight_dtype": "fp8_e4m3fn"}}
    # lightx2v LoRA 加速（skill: LoraLoaderModelOnly strength=1.0, 4步33s；必须接否则走默认8步慢）
    n1b = nxt()
    wf[n1b] = {"class_type": "LoraLoaderModelOnly", "inputs": {
        "model": [n1, 0], "lora_name": LORA, "strength_model": 1.0}}
    n2 = nxt()
    wf[n2] = {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "qwen_image"}}
    n3 = nxt()
    wf[n3] = {"class_type": "VAELoader", "inputs": {"vae_name": VAE}}
    n4 = nxt()
    wf[n4] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": SIGCLIP}}
    n5 = nxt()
    wf[n5] = {"class_type": "LoadImage", "inputs": {"image": FIRST_IMG}}
    n6 = nxt()
    wf[n6] = {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": [n4, 0], "image": [n5, 0], "crop": "center"}}
    n7 = nxt()
    wf[n7] = {"class_type": "TextEncodeHunyuanVideo_ImageToVideo",
              "inputs": {"clip": [n2, 0], "clip_vision_output": [n6, 0], "prompt": PROMPT, "image_interleave": 2}}
    n8 = nxt()
    wf[n8] = {"class_type": "TextEncodeHunyuanVideo_ImageToVideo",
              "inputs": {"clip": [n2, 0], "clip_vision_output": [n6, 0], "prompt": NEG, "image_interleave": 2}}
    n9 = nxt()
    wf[n9] = {"class_type": "HunyuanVideo15ImageToVideo",
              "inputs": {"positive": [n7, 0], "negative": [n8, 0], "vae": [n3, 0],
                         "width": W, "height": H, "length": LEN, "batch_size": 1,
                         "start_image": [n5, 0], "clip_vision_output": [n6, 0]}}
    n10 = nxt()
    wf[n10] = {"class_type": "KSampler", "inputs": {
        "model": [n1b, 0], "positive": [n9, 0], "negative": [n9, 1], "latent_image": [n9, 2],
        "seed": 111111, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}}
    n11 = nxt()
    wf[n11] = {"class_type": "VAEDecode", "inputs": {"samples": [n10, 0], "vae": [n3, 0]}}
    # 先 SaveImage 帧序列（观察），再 VHS 合成
    n12 = nxt()
    wf[n12] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "hyv_qa", "images": [n11, 0]}}
    n13 = nxt()
    wf[n13] = {"class_type": "VHS_VideoCombine", "inputs": {
        "images": [n11, 0], "frame_rate": 16, "loop_count": 0,
        "filename_prefix": "hyv_qa", "format": "video/h264-mp4", "pingpong": False, "save_output": True}}
    return wf


if __name__ == "__main__":
    print("[hyv-qa] I2V 480P 33帧 4步 生成中（素材）…")
    t0 = time.time()
    wf = build_i2v()
    files, pid = submit(wf, timeout=400)
    print(f"[hyv-qa] 完成 {time.time()-t0:.0f}s, pid={pid[:8]}")
    out = Path("C:/Users/zwq/aigc-comfy-pipeline/workspace/hy_qa")
    out.mkdir(parents=True, exist_ok=True)
    root = Path("C:/DrawingLive/ComfyUI/output")
    for sub, fn in files:
        src = root / (sub or "") / fn
        if src.suffix == ".mp4":
            dst = out / "hyv_sample.mp4"
        else:
            dst = out / fn
        dst.write_bytes(src.read_bytes())
        print(f"  -> {dst}")
