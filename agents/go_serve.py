"""
AIGC Pipeline REST API — FastAPI 服务。

用法:
  python go_serve.py
  python go_serve.py --port 8765
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from comfy_utils import bootstrap_agents_path

bootstrap_agents_path()

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUTS_DIR = ROOT / "outputs"

jobs: dict[str, dict[str, Any]] = {}


def _run_flux(job_id: str, params: dict) -> None:
    """后台执行 Flux 作业（质量预设 + 自动门禁）。"""
    from comfy_utils import generate_with_quality, resolve_comfy_root
    from go_flux import build_flux_workflow

    try:
        prompt = params.get("prompt", "")
        if not prompt:
            raise ValueError("prompt is required")

        qr = generate_with_quality(
            build_flux_workflow, prompt,
            preset=params.get("preset"),
            min_score=params.get("min_score", 0.0),
            max_retries=params.get("retry", 0),
            no_validate=params.get("no_validate", False),
            seed=params.get("seed", -1),
            steps=params.get("steps"),
            cfg=params.get("cfg"),
            width=params.get("width", 1024),
            height=params.get("height", 1024),
            model_variant=params.get("model", "9b"),
            lora_name=params.get("lora"),
            lora_strength=params.get("lora_strength", 1.0),
            sampler=params.get("sampler"),
            scheduler=params.get("scheduler"),
            filename_prefix=params.get("prefix", "api_flux"),
        )

        seed = qr["seed"]
        comfy_root = resolve_comfy_root()
        image_urls = []
        for sub, name in qr.get("images", []):
            path = (comfy_root / "output" / sub / name).resolve()
            if path.is_file():
                image_urls.append(f"/outputs/{name}")

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = {
            "seed": seed,
            "images": image_urls,
            "score": qr.get("score", -1),
            "retries": qr.get("retries", 0),
            "params": {
                "prompt": prompt,
                "preset": params.get("preset"),
                "model": params.get("model", "9b"),
                "lora": params.get("lora"),
            },
        }
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


def _run_lora(job_id: str, params: dict) -> None:
    """后台执行 LoRA 作业。"""
    from comfy_utils import comfy_base_url, comfy_post_prompt, resolve_comfy_root, wait_images
    from go_knives_lora import CHARACTERS, build_positive, call_llm_outfit, default_negative
    import random, json

    try:
        prompt = params.get("prompt", "")
        character = params.get("character", "knives")
        if character not in CHARACTERS:
            character = "knives"
        char = CHARACTERS[character]

        positive = build_positive(call_llm_outfit(prompt, char), char, sdxl=True)
        negative = params.get("negative") or default_negative(char, sdxl=True)

        workflow_file = char["workflow_sdxl"]
        with open(workflow_file, encoding="utf-8") as f:
            template = json.load(f)

        wf = json.loads(json.dumps(template))
        wf["6"]["inputs"]["text"] = positive
        wf["7"]["inputs"]["text"] = negative
        seed = random.randint(1, 2**48 - 1)
        wf["3"]["inputs"]["seed"] = seed
        wf["9"]["inputs"]["filename_prefix"] = f"api_lora_{character}"

        result = comfy_post_prompt(wf)
        pid = result.get("prompt_id", "")
        if not pid:
            raise RuntimeError("ComfyUI did not return prompt_id")

        jobs[job_id]["prompt_id"] = pid
        base = comfy_base_url()
        images = wait_images(pid, base)

        comfy_root = resolve_comfy_root()
        image_urls = []
        for sub, name in images:
            path = (comfy_root / "output" / sub / name).resolve()
            if path.is_file():
                image_urls.append(f"/outputs/{name}")

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = {
            "seed": seed,
            "images": image_urls,
            "character": character,
        }
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


# FastAPI 导入（可选依赖）
try:
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.responses import JSONResponse, FileResponse
    import uvicorn

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False
    FastAPI = None  # type: ignore

if _HAS_FASTAPI:

    app = FastAPI(title="AIGC Pipeline API", version="0.30.0")

    @app.post("/api/flux")
    async def api_flux(params: dict, background: BackgroundTasks):
        job_id = uuid.uuid4().hex[:12]
        jobs[job_id] = {"status": "queued", "command": "flux", "params": params}
        background.add_task(_run_flux, job_id, params)
        return JSONResponse({"job_id": job_id, "status": "queued"}, status_code=202)

    @app.post("/api/lora")
    async def api_lora(params: dict, background: BackgroundTasks):
        job_id = uuid.uuid4().hex[:12]
        jobs[job_id] = {"status": "queued", "command": "lora", "params": params}
        background.add_task(_run_lora, job_id, params)
        return JSONResponse({"job_id": job_id, "status": "queued"}, status_code=202)

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str):
        job = jobs.get(job_id)
        if not job:
            return JSONResponse({"error": "not found"}, status_code=404)
        return job

    @app.get("/api/jobs")
    async def list_jobs():
        return {
            "total": len(jobs),
            "jobs": [
                {"job_id": jid, "status": j["status"], "command": j.get("command")}
                for jid, j in jobs.items()
            ][-20:],
        }

    @app.get("/api/health")
    async def health():
        from comfy_utils import check_comfy_health, check_ollama_health

        return {
            "status": "ok",
            "comfyui": check_comfy_health(),
            "ollama": check_ollama_health(),
        }

    @app.get("/api/models")
    async def list_models():
        try:
            from model_manager import list_models as lm
            models = lm()
            by_cat: dict[str, int] = {}
            for m in models:
                by_cat[m["category"]] = by_cat.get(m["category"], 0) + 1
            return {"total": len(models), "by_category": by_cat}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/workflows")
    async def list_workflows():
        try:
            from workflow_manager import list_workflows as lw
            wfs = lw()
            return {"total": len(wfs), "api_format": sum(1 for w in wfs if w["is_api_format"])}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/outputs/{filename}")
    async def get_output(filename: str):
        path = OUTPUTS_DIR / filename
        if not path.is_file():
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(str(path))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="REST API 服务（FastAPI）")
    parser.add_argument("--port", type=int, default=8765, help="端口")
    args = parser.parse_args()

    if not _HAS_FASTAPI:
        print("需要安装: pip install fastapi uvicorn", file=sys.stderr)
        print("或使用 CLI 模式: python -m agents --help")
        sys.exit(1)

    port = args.port or int(os.environ.get("PORT", 8765))
    print(f"🚀 AIGC Pipeline API v0.30.0")
    print(f"   地址: http://127.0.0.1:{port}")
    print(f"   文档: http://127.0.0.1:{port}/docs")
    print(f"   健康: http://127.0.0.1:{port}/api/health")
    print()
    print(f"   可用端点:")
    print(f"     POST /api/flux   — Flux.2 Klein 文生图（支持 preset/min_score/retry）")
    print(f"     POST /api/lora   — SDXL LoRA 文生图")
    print(f"     GET  /api/jobs   — 作业列表")
    print(f"     GET  /api/health — 健康检查")
    print(f"     GET  /api/models — 模型清单")
    print()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
