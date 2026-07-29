"""Build and submit Wan2.1 I2V 360° rotation workflow"""
import json, urllib.request, sys, os

API = 'http://127.0.0.1:8188/prompt'

# Use FunModels pipeline for simpler API
wf = {
    # Load image
    "90": {"class_type": "LoadImage", "inputs": {"image": "shimu_ref.png"}},
    
    # Load Wan2.1 I2V model
    "100": {"class_type": "LoadWanModel", "inputs": {
        "model": "Wan2.1-I2V-14B-480P",
        "GPU_memory_mode": "model_cpu_offload",
        "config": "wan2.1/wan_civitai.yaml",
        "precision": "fp16"
    }},
    
    # Wan I2V sampler
    "101": {"class_type": "WanI2VSampler", "inputs": {
        "funmodels": ["100", 0],
        "prompt": "rotation 360 degrees, steady camera, orbiting around character, front view to back view, smooth motion, ultra realistic, high detail",
        "negative_prompt": "blurry, low quality, distorted, deformed, ugly",
        "video_length": 49,
        "base_resolution": 512,
        "seed": 42,
        "steps": 30,
        "cfg": 5.0,
        "scheduler": "Flow",
        "shift": 7,
        "teacache_threshold": 0.275,
        "enable_teacache": True,
        "num_skip_start_steps": 5,
        "teacache_offload": True,
        "cfg_skip_ratio": 0.3
    }},
    
    # Save images
    "102": {"class_type": "SaveImage", "inputs": {
        "images": ["101", 0],
        "filename_prefix": "shimu_360"
    }},
}

data = json.dumps({"prompt": wf, "client_id": "wan360_v2"}).encode()
req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    print(json.loads(resp.read()))
except Exception as e:
    print(f"ERROR: {e}")
