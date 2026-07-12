"""
LoRA 训练编排 — 数据验证 + AutoDL 训练命令生成。

用法示例:
  python go_train.py --dir ./training_images --trigger "Ha Eun"
  python go_train.py --dir ./images --trigger "Knives" --dry-run
  python go_train.py --dir ./images --trigger "Caster" --rank 64 --steps 2000
"""
from __future__ import annotations

import sys
from pathlib import Path

IMG_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def validate_dataset(data_dir: Path) -> dict:
    """验证训练数据集完整性。"""
    if not data_dir.is_dir():
        return {"error": f"目录不存在: {data_dir}"}

    images = sorted([
        p for p in data_dir.iterdir()
        if p.suffix.lower() in IMG_EXTENSIONS and p.is_file()
    ])
    txt_files = list(data_dir.glob("*.txt"))

    captioned = sum(1 for f in images if f.with_suffix(".txt").exists())
    missing = len(images) - captioned

    # 图片尺寸检查（前 20 张）
    sizes = set()
    size_consistent = True
    if images:
        try:
            from PIL import Image
            for f in images[:20]:
                try:
                    im = Image.open(f)
                    sizes.add(im.size)
                except Exception:
                    pass
            size_consistent = len(sizes) <= 2
        except ImportError:
            pass  # 无 Pillow 跳过尺寸检查

    result = {
        "directory": str(data_dir),
        "total_images": len(images),
        "total_captions": len(txt_files),
        "captioned": captioned,
        "missing_captions": missing,
        "unique_sizes": len(sizes),
        "size_consistent": size_consistent,
        "ready": captioned == len(images) and len(images) >= 10,
        "too_few_images": len(images) < 10,
    }
    if images:
        total_size_mb = sum(f.stat().st_size for f in images) / (1024 * 1024)
        result["total_size_mb"] = round(total_size_mb, 1)
    return result


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
    center_crop: bool = True,
    mixed_precision: str = "fp16",
) -> str:
    """生成 AutoDL/Linux 训练命令。"""
    prompt = trigger
    data_dir_name = data_dir.name
    out_name = output_dir.name

    lines = [
        f"# ===== LoRA 训练命令 — {trigger} =====",
        f"# 数据集: {data_dir}",
        f"# 触发词: {trigger}",
        f"# 生成于: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "",
        "# ── 1. 上传数据到 AutoDL ──",
        "# scp -P <PORT> -r ./<data_dir> root@<HOST>:~/training_data/",
        "",
        "",
        "# ── 2. SSH 到 AutoDL ──",
        "# ssh -p <PORT> root@<HOST>",
        "",
        "",
        "# ── 3. 安装依赖 ──",
        "pip3 install torch==2.5.1 torchvision==0.20.1 \\",
        "  --index-url https://download.pytorch.org/whl/cu124",
        "",
        "pip3 install diffusers transformers peft bitsandbytes accelerate \\",
        "  sentencepiece protobuf datasets tensorboard",
        "",
        "",
        "# ── 4. 下载训练脚本 ──",
        "curl -sL --max-time 60 \\",
        '  "https://api.github.com/repos/huggingface/diffusers/contents/examples/dreambooth/train_dreambooth_lora_flux2_klein.py" \\',
        "  | python3 -c \"import sys,json,base64; d=json.load(sys.stdin); open('train_script.py','w').write(base64.b64decode(d['content']).decode())\"",
        "",
        "# 如果 GitHub API 被墙，从本地 scp",
        "# scp ./train_dreambooth_lora_flux2_klein.py root@<HOST>:~/",
        "",
        "",
        "# ── 5. 设置环境 ──",
        "export HF_ENDPOINT=https://hf-mirror.com",
        "export HF_TOKEN=<your_hf_token>",
        "",
        "",
        "# ── 6. 训练 ──",
        "nohup python3 -u train_script.py \\",
        f"  --pretrained_model_name_or_path=black-forest-labs/FLUX.2-klein-base-4B \\",
        f"  --instance_data_dir=./{data_dir_name} \\",
        f'  --instance_prompt="{prompt}" \\',
        f"  --output_dir=./{out_name} \\",
        f"  --resolution={resolution} \\",
        f"  --train_batch_size={batch_size} \\",
        f"  --gradient_accumulation_steps=4 \\",
        f"  --learning_rate={lr} \\",
        f"  --max_train_steps={steps} \\",
        f"  --lr_scheduler=cosine --lr_warmup_steps=200 \\",
        f"  --rank={rank} --lora_alpha={max(rank // 2, 1)} \\",
        f"  --text_encoder_lr={text_encoder_lr} \\",
        f"  --seed=42 --mixed_precision={mixed_precision} \\",
    ]
    if center_crop:
        lines.append(f"  --center_crop \\")
        lines.append(f"  --random_flip \\")
    lines += [
        f"  --checkpointing_steps=500 \\",
        f"  --gradient_checkpointing --cache_latents --use_8bit_adam \\",
        f"  > training.log 2>&1 &",
        "",
        "",
        "# ── 7. 监控进度 ──",
        "# tail -f training.log",
        "# 或查看 loss: grep 'loss:' training.log | tail -5",
        "",
        "",
        "# ── 8. 下载 checkpoint ──",
        "# for CKPT in 500 1000 1500 2000; do",
        "#   scp -P <PORT> root@<HOST>:~/{out_name}/checkpoint-$CKPT/pytorch_lora_weights.safetensors ./checkpoint_$CKPT.safetensors",
        "# done",
        "# scp -P <PORT> root@<HOST>:~/{out_name}/pytorch_lora_weights.safetensors ./final.safetensors",
        "",
        "",
        "# ── 9. 本地推理验证 ──",
        "# python -m agents flux --lora final.safetensors \"test prompt\"",
    ]

    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="LoRA 训练编排 — 数据验证 + AutoDL 命令生成",
    )
    parser.add_argument(
        "--dir", required=True,
        help="训练数据目录（含图片和 .txt 标注）",
    )
    parser.add_argument(
        "--trigger", required=True,
        help="角色触发词",
    )
    parser.add_argument(
        "--output", default="./lora_output",
        help="输出目录（默认 ./lora_output）",
    )
    parser.add_argument("--rank", type=int, default=64, help="LoRA rank")
    parser.add_argument("--steps", type=int, default=2000, help="训练步数")
    parser.add_argument("--lr", type=float, default=5e-5, help="学习率")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅验证数据，不生成命令",
    )
    args = parser.parse_args()

    # 数据验证
    result = validate_dataset(Path(args.dir))

    if "error" in result:
        print(f"错误: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"数据集验证: {result['directory']}")
    print(f"{'='*50}")
    print(f"  图片:     {result['total_images']}")
    print(f"  标注:     {result['captioned']}/{result['total_images']}")
    if result.get("missing_captions", 0) > 0:
        print(f"  缺标注:   {result['missing_captions']} ⚠️")
    if result.get("total_size_mb"):
        print(f"  大小:     {result['total_size_mb']} MB")
    if result.get("unique_sizes", 0) > 0:
        print(f"  尺寸:     {result['unique_sizes']} 种 "
              f"{'✅' if result['size_consistent'] else '❌ 不一致'}")

    if result.get("too_few_images"):
        print(f"\n❌ 图片不足10张（当前{result['total_images']}），建议增加训练数据。")
        sys.exit(1)

    if result.get("missing_captions", 0) > 0:
        print(f"\n⚠️  缺少 {result['missing_captions']} 个标注文件。")
        print(f"   运行: python -m agents caption --dir {Path(args.dir)} --trigger \"{args.trigger}\"")
        if args.dry_run:
            return
        sys.exit(1)

    print(f"  ✅ 数据集就绪")

    if args.dry_run:
        print(f"\n[dry-run] 停止，不生成训练命令。")
        return

    # 生成命令
    cmd = generate_training_command(
        Path(args.dir),
        args.trigger,
        Path(args.output),
        rank=args.rank,
        steps=args.steps,
        lr=args.lr,
    )

    print(f"\n{'='*50}")
    print(f"训练命令（复制到 AutoDL SSH 终端执行）")
    print(f"{'='*50}\n")
    print(cmd)


if __name__ == "__main__":
    main()
