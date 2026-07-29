"""提示词反推 CLI 入口。"""
import sys, json


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="图片 -> SDXL/Flux/Anima 提示词")
    parser.add_argument("image", help="图片路径")
    parser.add_argument("--target", default="", help="针对性描述")
    parser.add_argument("--model", choices=["sdxl","flux","anima","all"], default="all")
    parsed = parser.parse_args(sys.argv[1:])

    from agents.prompt_reversal import reverse_prompt
    print(f"📷 分析: {parsed.image}")
    result = reverse_prompt(parsed.image, targeted=parsed.target)
    if not result.get("available"):
        print(f"❌ 失败: {result.get('error')}")
        return

    ms = ["sdxl", "flux", "anima"] if parsed.model == "all" else [parsed.model]
    lb = {"sdxl": "SDXL 格式（逗号标签+质量词）",
          "flux": "Flux 格式（自然语言段落）",
          "anima": "Anima 格式（自然语言+质量词）"}
    for m in ms:
        print(f"\n【{lb[m]}】\n" + "-" * 60)
        print(result[m])
        print(f"\n  长度: {len(result[m])} chars")
