"""SDXL LoRA 训练 v3 — 手动构建 dataset TOML 配置。"""
import os, sys, gc, time, json
from pathlib import Path

os.environ.pop("PYTHONPATH", None)
COMFY = r"C:\DrawingLive\ComfyUI"
sys.path = [p for p in sys.path if 'hermes' not in p.lower()]
sys.path.insert(0, COMFY)
sys.path.insert(0, os.path.join(COMFY, "custom_nodes"))

import torch
import comfyui_fluxtrainer
import comfyui_fluxtrainer.networks
import comfyui_fluxtrainer.networks.lora
import comfyui_fluxtrainer.library
from comfyui_fluxtrainer.networks.lora import LoRANetwork
from comfyui_fluxtrainer.library import train_util, config_util
from comfyui_fluxtrainer.train_network import NetworkTrainer, setup_parser
from comfyui_fluxtrainer.nodes import InitFluxLoRATraining

MODEL = r"C:\DrawingLive\ComfyUI\models\checkpoints\waiIllustriousSDXL_v160.safetensors"
VAE = r"C:\DrawingLive\ComfyUI\models\vae\sdxl_vae.safetensors"
DATA = r"C:\DrawingLive\ComfyUI\input\flux_train_dataset"
OUT = r"C:\DrawingLive\ComfyUI\sdxl_trainer_output"
os.makedirs(OUT, exist_ok=True)

# 构建类似 ComfyUI 节点的 dataset_config
dataset_toml = json.dumps({
    "datasets": [{
        "subsets": [{
            "image_dir": os.path.join(DATA, "char"),
            "class_tokens": "",
            "num_repeats": 1,
        }]
    }]
})

print("="*60); print("SDXL LoRA 训练 v3"); print("="*60)

# 直接用 InitFluxLoRATraining 的逻辑，但传 SDXL 模型
# ... 这个太复杂了，换个思路

# 最简单的：直接用 Kohya CLI
os.chdir(r"C:\DrawingLive\ComfyUI\custom_nodes\comfyui_fluxtrainer")
sys.argv = [
    "train_network.py",
    f"--pretrained_model_name_or_path={MODEL}",
    f"--vae={VAE}",
    f"--train_data_dir={DATA}",
    "--caption_extension=.caption",
    "--resolution=896",
    "--enable_bucket=False",
    "--output_dir=" + OUT,
    "--output_name=sdxl_char_lora",
    "--network_module=networks.lora",
    "--network_dim=64",
    "--network_alpha=1",
    "--learning_rate=4e-4",
    "--max_train_steps=150",
    "--mixed_precision=fp16",
    "--gradient_checkpointing",
    "--mem_eff_attn=sdpa",
    "--sdpa",
    "--network_train_unet_only",
    "--save_precision=bf16",
    "--lr_scheduler=constant",
    "--seed=42",
    "--dataset_class=dream_booth",
    "--cache_latents",
]
print("Running Kohya train_network.py with SDXL args...")
print(f"  Model: {MODEL}")
print(f"  Output: {OUT}")
print()

# 直接调用 Kohya 的主入口
from train_network import main as kohya_main
gc.collect(); torch.cuda.empty_cache()
t0 = time.time()
kohya_main()
elapsed = time.time() - t0
print(f"\n✅ 耗时={elapsed:.0f}s")
for f in Path(OUT).glob("sdxl_char_lora*.safetensors"):
    print(f"LoRA: {f.name} ({f.stat().st_size/1024:.0f} KB)")
