import argparse
import json
import os
import random
import sys
from pathlib import Path

from comfy_utils import AGENTS_DIR, bootstrap_agents_path, comfy_post_prompt, ollama_generate_or_fallback

bootstrap_agents_path()

HERE = AGENTS_DIR
WORKFLOW_FILE = HERE / "workflow.json"
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188/prompt")


def call_llm(prompt: str) -> str:
    return ollama_generate_or_fallback(f"把用户输入转换成SDXL提示词：{prompt}", fallback=prompt)


def load_workflow():
    with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="一句话提交 ComfyUI 文生图（默认经 Ollama 转写为适用于 SDXL 的英文提示词）。"
        "可用环境变量 COMFY_URL、OLLAMA_URL、OLLAMA_MODEL 覆盖默认地址与模型。",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="跳过 Ollama，将输入整段作为正向提示词（建议写英文；中文效果因底模而异）",
    )
    parser.add_argument("prompt", nargs="?", help="一句话画面描述；省略时从标准输入读取")
    args = parser.parse_args()

    user = args.prompt
    if not user:
        user = input("请输入需求: ").strip()
    if not user:
        print("未输入内容，退出。", file=sys.stderr)
        sys.exit(1)

    try:
        positive_prompt = user if args.raw else call_llm(user)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    negative_prompt = "worst quality, blurry, low quality"
    workflow = load_workflow()
    workflow["6"]["inputs"]["text"] = positive_prompt
    workflow["7"]["inputs"]["text"] = negative_prompt
    workflow["3"]["inputs"]["seed"] = random.randint(1, 999999999)

    try:
        comfy_post_prompt(workflow, prompt_url=COMFY_URL)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print("\n====================")
    print("已向 ComfyUI 提交任务")
    print("====================")
    print("正向提示词：", positive_prompt)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
