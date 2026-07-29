"""
提示词测试框架 — 不用跑 ComfyUI，验证提示词质量。

用法:
    python -m agents prompt_test "银发精灵在樱花树下" --model sdxl
"""
import sys, json
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), ".."))

from workshop.engine import nls_to_prompt


def test_prompt(desc: str, style: str = "anime", model_type: str = "sdxl") -> dict:
    """测试单个场景的提示词质量。"""
    prompt = nls_to_prompt(desc, style_hint=style, model_type=model_type, ollama_available=False)
    tags = prompt.split(",")
    return {
        "description": desc,
        "model": model_type,
        "prompt": prompt,
        "tag_count": len(tags),
        "char_count": len(prompt),
        "starts_correctly": prompt.lower().startswith("masterpiece, best quality") if model_type == "sdxl" else True,
        "no_redundancy": prompt.lower().count("masterpiece") <= 1,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="提示词测试框架")
    parser.add_argument("description", help="场景描述")
    parser.add_argument("--model", choices=["sdxl", "flux", "anima"], default="sdxl")
    parser.add_argument("--style", default="anime")
    parser.add_argument("--check", action="store_true", help="质量检查模式")
    parsed = parser.parse_args(sys.argv[1:])

    result = test_prompt(parsed.description, parsed.style, parsed.model)

    print(f"=== {result['model'].upper()} prompt test ===")
    print(f"描述: {result['description']}")
    print(f"提示词 ({result['tag_count']} tags, {result['char_count']} chars):")
    print(result['prompt'])

    if parsed.check:
        print(f"\n--- 质量检查 ---")
        print(f"以 MASTERPIECE, best quality 开头: {'✅' if result['starts_correctly'] else '❌'}")
        print(f"无冗余质量标签: {'✅' if result['no_redundancy'] else '❌'}")
        print(f"标签数 ({result['tag_count']}): {'✅' if result['tag_count'] <= 30 else '⚠️ 超过推荐值'}")
        print(f"Token 估算 ({result['char_count']//4}): {'✅' if result['char_count']//4 <= 75 else '⚠️ 可能超过75 token'}")


if __name__ == "__main__":
    main()
