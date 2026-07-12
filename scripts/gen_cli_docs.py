"""自动生成 CLI 参考文档。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


# 主命令列表
COMMANDS = [
    ("run", "一句话提交 ComfyUI 文生图（自然语言 → Ollama → 出图）"),
    ("lora", "角色 LoRA 文生图（Knives / Caster，支持批量）"),
    ("ipa", "IPAdapter 锁脸文生图（参考图驱动面部一致性）"),
    ("multi", "多角色 LoRA 同图（Knives + Caster + FaceDetailer）"),
    ("sweep", "参数网格扫描（Flux.2 Klein，自动对比拼图）"),
    ("flux", "Flux.2 Klein 文生图（9B/4B，支持 LoRA 注入）"),
    ("control", "ControlNet 引导生图（depth/openpose/softedge/tile/inpaint/lineart）"),
    ("video", "Wan2.2 视频生成（Text-to-Video / I2V，帧数/帧率/分辨率控制）"),
    ("validate", "出图质量评估（CLIP score / 崩脸检测 / 图像质量）"),
    ("abtest", "Prompt A/B 对比测试（同 seed 控制变量）"),
    ("bestof", "多 seed 自动挑优（CLIP 评分排名）"),
    ("caption", "Ollama VL 自动标图（训练数据准备）"),
    ("train", "LoRA 训练编排（数据验证 + AutoDL 命令生成）"),
    ("report", "管线验收报告（ComfyUI/模型/workflow/产出全貌）"),
    ("queue", "ComfyUI 队列管理（list/clear/interrupt/free）"),
    ("gallery", "输出画廊（HTML 产出展示，支持视频）"),
    ("serve", "REST API 服务（FastAPI，异步作业队列，支持图像/视频）"),
    ("doctor", "一键诊断修复（环境/依赖/模型检查）"),
    ("check", "环境检查（ComfyUI / Ollama 连通性）"),
    ("workflow", "工作流模板管理（list / show / schema / check / convert）"),
    ("models", "模型管理（list / info / check / download）"),
    ("outputs", "产出管理（list / show / clean）"),
]

# 子命令
SUB_COMMANDS: dict[str, list[str]] = {
    "workflow": ["list", "show", "schema", "check", "convert"],
    "models": ["list", "info", "check", "download"],
    "outputs": ["list", "show", "clean"],
    "queue": ["list", "clear", "interrupt", "free"],
}


def run_help(cmd_parts: list[str]) -> str:
    """运行 python -m agents <parts> --help 并捕获输出。"""
    cmd = [sys.executable, "-m", "agents", *cmd_parts, "--help"]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=ROOT,
        )
        return r.stdout.strip() or r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "(超时)"
    except Exception as e:
        return f"(错误: {e})"


def generate() -> str:
    lines: list[str] = []
    lines.append("# CLI 参考文档")
    lines.append("")
    lines.append(
        f"> 自动生成于 "
        f"{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")

    try:
        from agents import __version__
        ver = __version__
    except Exception:
        ver = "?"
    lines.append(f"AIGC ComfyUI Pipeline v{ver}")
    lines.append("")

    for cmd_name, cmd_desc in COMMANDS:
        lines.append("---")
        lines.append("")
        lines.append(f"## `{cmd_name}`")
        lines.append("")
        lines.append(f"{cmd_desc}")
        lines.append("")
        lines.append("```")
        help_text = run_help([cmd_name])
        lines.append(help_text[:3000] if help_text else "(无帮助信息)")
        lines.append("```")
        lines.append("")

        if cmd_name in SUB_COMMANDS:
            for sub in SUB_COMMANDS[cmd_name]:
                lines.append(f"### `{cmd_name} {sub}`")
                lines.append("")
                lines.append("```")
                sub_text = run_help([cmd_name, sub])
                lines.append(sub_text[:2000] if sub_text else "(无帮助信息)")
                lines.append("```")
                lines.append("")

    return "\n".join(lines)


def main() -> None:
    content = generate()
    output_path = DOCS / "cli-reference.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"✅ CLI 参考文档已生成: {output_path}")
    print(f"   共 {len(COMMANDS)} 个主命令")


if __name__ == "__main__":
    main()
