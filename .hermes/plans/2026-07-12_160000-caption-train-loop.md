# V0.13.0 — 标图 + LoRA 训练闭环 实现方案

> **Goal:** `python -m agents caption` 自动标图 + `python -m agents train` 训练编排，形成**出图→选图→标图→训练→部署**闭环。
>
> **Architecture:**
> - `go_caption.py`: 调用 WSL Ollama VL（qwen3.5:9b）自动生成 .txt 标注
> - `go_train.py`: 验证训练数据 → 生成 AutoDL 训练命令 → 本地推理验证
>
> **Reference:** `flux-lora-autodl-training` skill 的 captioning 流程 + 训练参数。

---

## 用户交互

```
# 自动标图
python -m agents caption --dir ./training_images --trigger "Ha Eun"
python -m agents caption --dir ./training_images --trigger "Knives" --dry-run  # 预览
python -m agents caption --dir ./training_images --model qwen3.5:9b

# 训练编排
python -m agents train --dir ./training_images --trigger "Ha Eun" --output ./lora_output
python -m agents train --dir ./training_images --rank 64 --steps 2000 --dry-run
python -m agents train --dir ./training_images --no-caption  # 跳过标图，用已有 .txt
```

---

## 闭环节点

```
拍照/采集 → python -m agents caption → 自动 .txt 标注
                            ↓
              python -m agents train → 验证数据 → 生成命令
                            ↓
                  (手动SSH到AutoDL) → 训练
                            ↓
                  scp 下载 checkpoint
                            ↓
              python -m agents lora --lora new_model.safetensors "prompt"
```

---

## 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| Create | `agents/go_caption.py` | 自动标图 |
| Create | `agents/go_train.py` | 训练编排 |
| Modify | `agents/__main__.py` | +`caption` +`train` 子命令 |
| Modify | `AGENTS.md` | 版本 V0.13.0 |

---

## Task 1: 创建 go_caption.py

**Objective:** WSL Ollama VL 自动生成 .txt 标注

**核心逻辑:**

```python
import base64
import json
import time
from pathlib import Path
from urllib import request as urllib_request

CAPTION_PROMPT = (
    'Describe this character image in danbooru tags: '
    '"{trigger}", 1girl, {{pose}}, {{expression}}, {{gaze}}, {{framing}}. '
    'No hair/eye/clothing colors.'
)

def caption_image(model: str, image_path: Path, trigger: str, ollama_url: str) -> str:
    """调用 Ollama VL 生成单张图片的标注。"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    
    prompt = CAPTION_PROMPT.format(trigger=trigger)
    payload = json.dumps({
        "model": model, "prompt": prompt, "images": [b64],
        "stream": False, "options": {"num_predict": 30}
    }).encode()
    
    req = urllib_request.Request(ollama_url, data=payload,
        headers={"Content-Type": "application/json"})
    
    with urllib_request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
        text = resp.get("response", "").strip()
    
    # 清理：取第一部分，去掉多余换行
    text = text.replace("\n", ", ").replace("\r", "")
    return text


def run_captioning(
    image_dir: Path,
    trigger: str,
    *,
    model: str = "qwen3.5:9b",
    ollama_url: str = "http://127.0.0.1:11434/api/generate",
    extensions: tuple = (".png", ".jpg", ".jpeg", ".webp"),
    dry_run: bool = False,
) -> dict:
    """对目录中所有图片执行标图。返回统计信息。"""
    IMG_EXTS = {e.lower() for e in extensions}
    
    files = sorted([
        p for p in Path(image_dir).iterdir()
        if p.suffix.lower() in IMG_EXTS and p.is_file()
    ])
    
    if not files:
        print(f"未找到图片文件在: {image_dir}")
        return {"total": 0, "success": 0, "failed": 0}
    
    print(f"找到 {len(files)} 张图片")
    print(f"触发词: {trigger}")
    print(f"模型: {model}")
    if dry_run:
        print("[dry-run] 预览模式，不实际调用 API")
        for f in files[:3]:
            existing = f.with_suffix(".txt")
            status = "✅ 已有" if existing.exists() else "📄 待生成"
            print(f"  {status} {f.name}")
        if len(files) > 3:
            print(f"  ... 还有 {len(files)-3} 张")
        return {"total": len(files), "dry_run": True}
    
    # 检查 Ollama 连通性
    try:
        req = urllib_request.Request(ollama_url.rstrip("/api/generate") + "/api/tags",
            method="GET")
        with urllib_request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            if not any(model in m for m in models):
                print(f"[warn] Ollama 中未找到模型 {model}")
                print(f"  可用: {', '.join(models[:5])}")
    except Exception as exc:
        print(f"[warn] Ollama 连接失败: {exc}")
        print("处理: 确保 WSL 中已启动 Ollama (wsl sh -c 'ollama serve &')")
        # 继续尝试
```

**CLI main():**

```python
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ollama VL 自动标图")
    parser.add_argument("--dir", required=True, help="训练图片目录")
    parser.add_argument("--trigger", required=True, help="角色触发词")
    parser.add_argument("--model", default="qwen3.5:9b", help="Ollama VL 模型")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()
    
    result = run_captioning(
        Path(args.dir), args.trigger,
        model=args.model, dry_run=args.dry_run,
    )
    print(f"\n标图完成: {result.get('success',0)}/{result.get('total',0)}")
```

**验证:**
```bash
mkdir -p /tmp/test_caption
# 放一张测试图片
python -m agents caption --dir /tmp/test_caption --trigger "Test" --dry-run
```

---

## Task 2: 创建 go_train.py

**Objective:** 训练数据验证 + 生成 AutoDL 训练命令

**核心设计:**

```python
VALIDATION_CHECKLIST = [
    ("图片文件", lambda d: len(list(d.glob("*.png")) + list(d.glob("*.jpg"))) >= 10),
    ("标注文件", lambda d: len(list(d.glob("*.txt"))) >= 10),
    ("标注完整性", lambda d: _check_caption_coverage(d)),
    ("图片尺寸一致性", lambda d: _check_image_sizes(d)),
]

def validate_dataset(data_dir: Path) -> dict:
    """验证训练数据集完整性。"""
    checks = {}
    images = sorted(data_dir.glob("*.*"))
    img_exts = {".png", ".jpg", ".jpeg", ".webp"}
    img_files = [f for f in images if f.suffix.lower() in img_exts]
    txt_files = list(data_dir.glob("*.txt"))
    
    checks["total_images"] = len(img_files)
    checks["total_captions"] = len(txt_files)
    checks["captioned"] = sum(1 for f in img_files if f.with_suffix(".txt").exists())
    checks["missing_captions"] = checks["total_images"] - checks["captioned"]
    checks["ready"] = checks["captioned"] == checks["total_images"] and checks["total_images"] >= 10
    
    if img_files:
        sizes = set()
        for f in img_files[:20]:
            try:
                from PIL import Image
                im = Image.open(f)
                sizes.add(im.size)
            except Exception:
                pass
        checks["unique_sizes"] = len(sizes)
        checks["size_consistent"] = len(sizes) <= 2
    else:
        checks["unique_sizes"] = 0
        checks["size_consistent"] = True
    
    return checks


def generate_training_command(
    data_dir: Path,
    trigger: str,
    output_dir: Path = Path("./lora_output"),
    *,
    rank: int = 64,
    steps: int = 2000,
    lr: float = 5e-5,
    text_encoder_lr: float = 1e-5,
    batch_size: int = 2,
    resolution: int = 1024,
    instance_prompt: str = "",
    center_crop: bool = True,
    mixed_precision: str = "fp16",
) -> str:
    """生成 AutoDL 训练命令。"""
    prompt = instance_prompt or trigger
    
    cmd = f"""# ===== 训练命令 (AutoDL / Linux) =====
# 1. 上传数据
#    scp -P <PORT> -r {data_dir}/ root@<HOST>:/root/training_data/

# 2. SSH 到 AutoDL
#    ssh -p <PORT> root@<HOST>

# 3. 安装依赖
pip3 install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
pip3 install diffusers transformers peft bitsandbytes accelerate sentencepiece protobuf datasets tensorboard

# 4. 下载训练脚本
curl -sL --max-time 60 \\
  "https://api.github.com/repos/huggingface/diffusers/contents/examples/dreambooth/train_dreambooth_lora_flux2_klein.py" \\
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open('train_script.py','w').write(base64.b64decode(d['content']).decode())"

# 5. 设置环境
export HF_ENDPOINT=https://hf-mirror.com
export HF_TOKEN=<your_hf_token>

# 6. 训练
python3 -u train_script.py \\
  --pretrained_model_name_or_path=black-forest-labs/FLUX.2-klein-base-4B \\
  --instance_data_dir=./training_data \\
  --instance_prompt="{prompt}" \\
  --output_dir=./{output_dir.name} \\
  --resolution={resolution} \\
  --train_batch_size={batch_size} \\
  --gradient_accumulation_steps=4 \\
  --learning_rate={lr} \\
  --max_train_steps={steps} \\
  --lr_scheduler=cosine --lr_warmup_steps=200 \\
  --rank={rank} --lora_alpha={rank//2} \\
  --text_encoder_lr={text_encoder_lr} \\
  --seed=42 --mixed_precision={mixed_precision} \\
  {"--center_crop" if center_crop else ""} \\
  --checkpointing_steps=500 \\
  --gradient_checkpointing --cache_latents --use_8bit_adam
"""
    return cmd
```

**CLI main():**

```python
def main():
    import argparse
    parser = argparse.ArgumentParser(description="LoRA 训练编排")
    parser.add_argument("--dir", required=True, help="训练数据目录")
    parser.add_argument("--trigger", required=True, help="角色触发词")
    parser.add_argument("--output", default="./lora_output")
    parser.add_argument("--rank", type=int, default=64)
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true", help="仅验证数据")
    args = parser.parse_args()
    
    result = validate_dataset(Path(args.dir))
    print(f"\n数据集验证:")
    print(f"  图片:     {result['total_images']}")
    print(f"  标注:     {result['captioned']}/{result['total_images']}")
    print(f"  尺寸一致: {'✅' if result['size_consistent'] else '❌'}")
    print(f"  就绪:     {'✅' if result['ready'] else '❌'}")
    
    if not result['ready']:
        print("\n处理: 先运行 python -m agents caption --dir ... --trigger ...")
        return
    
    if args.dry_run:
        return
    
    cmd = generate_training_command(
        Path(args.dir), args.trigger, Path(args.output),
        rank=args.rank, steps=args.steps,
    )
    print("\n" + cmd)
```

**验证:**
```bash
python -m agents train --dir /tmp/test_caption --trigger "Test" --dry-run
# → 验证报告 + 停止（dry-run）
```

---

## Task 3: __main__.py — +caption +train 子命令

**改动:** 两命令都走 script_map 路由。

```python
# script_map 加:
"caption": "go_caption.py",
"train": "go_train.py",

# elif 加:
elif command == "caption":
    from agents.go_caption import main as target_main
elif command == "train":
    from agents.go_train import main as target_main

# _show_help() 加:
("caption", "Ollama VL 自动标图（WSL，训练数据准备）"),
("train", "LoRA 训练编排（数据验证 + AutoDL 命令生成）"),
```

---

## Task 4: AGENTS.md + commit

- 版本 V0.12.0 → V0.13.0
- 核心能力表加 caption + train
- Checklist

---

## 验证清单

- [ ] `python -m agents caption --help` 显示完整参数
- [ ] `python -m agents caption --dir /path --trigger "Test" --dry-run` 预览不调用 API
- [ ] `python -m agents train --help` 显示完整参数
- [ ] `python -m agents train --dir /path --trigger "Test" --dry-run` 验证报告
- [ ] `python -m agents --help` 显示 12 个子命令
