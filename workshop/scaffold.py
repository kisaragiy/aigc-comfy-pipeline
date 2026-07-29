#!/usr/bin/env python3
"""项目骨架生成器 — workshop scaffold

用法:
  workshop scaffold cli <name>          # Python CLI 工具
  workshop scaffold fastapi <name>      # FastAPI 后端
  workshop scaffold vue3 <name>         # Vue3 + Vite 前端
  workshop scaffold fullstack <name>    # FastAPI + Vue3 全栈
  workshop scaffold python-pkg <name>   # Python 库
  workshop scaffold list                # 列出可用的骨架类型
"""
import os, sys, shutil
from pathlib import Path

TEMPLATES = {}  # type: ignore

def render(template: str, name: str, out: Path):
    """将模板字符串中的 {name} 替换并写入文件"""
    content = template.replace("{name}", name).replace("{Name}", name.title())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"  ✦ {out.relative_to(out.parent.parent if (out.parent.parent / 'pyproject.toml').exists() else out.parent)}")

def scaffold_cli(name: str, out_dir: Path = Path.cwd()):
    base = out_dir / name
    print(f"🚀 创建 Python CLI 项目: {name}")
    render("""[project]
name = "{name}"
version = "0.1.0"
description = "{name} CLI tool"
requires-python = ">=3.11"
dependencies = []
""", name, base / "pyproject.toml")
    render("""def main():
    import argparse
    parser = argparse.ArgumentParser(prog="{name}")
    parser.add_argument("--version", action="version", version="0.1.0")
    args = parser.parse_args()
    print(f"{name} v0.1.0 ready")

if __name__ == "__main__":
    main()
""", name, base / f"{name.replace('-','_')}" / "__init__.py")
    render("""from {name} import main
main()
""", name, base / "__main__.py")
    render("""# {name}

Python CLI tool.

## Install
pip install -e .

## Usage
python -m {name} --help
""", name, base / "README.md")

def scaffold_fastapi(name: str, out_dir: Path = Path.cwd()):
    base = out_dir / name
    print(f"🚀 创建 FastAPI 项目: {name}")
    render("""[project]
name = "{name}"
version = "0.1.0"
description = "{name} API server"
requires-python = ">=3.11"
dependencies = ["fastapi", "uvicorn[standard]", "pydantic", "sqlalchemy", "alembic"]
""", name, base / "pyproject.toml")
    render("""from fastapi import FastAPI
from .routers import items

app = FastAPI(title="{name}")
app.include_router(items.router)

@app.get("/health")
async def health():
    return {{"status": "ok"}}
""", name, base / "app" / "__init__.py")
    render("""from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/items", tags=["items"])

class Item(BaseModel):
    id: int | None = None
    name: str
    description: str = ""

items_db: List[dict] = []

@router.get("/")
async def list_items():
    return items_db

@router.post("/")
async def create_item(item: Item):
    items_db.append(item.model_dump())
    return item
""", name, base / "app" / "routers" / "items.py")
    render("""from fastapi import FastAPI
import uvicorn
from . import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
""", name, base / "run.py")
    render("""FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install .
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
""", name, base / "Dockerfile")
    render("""# {name}

FastAPI backend server.

## Quick start
pip install -e .
python run.py

## API docs
http://localhost:8000/docs
""", name, base / "README.md")

def scaffold_vue3(name: str, out_dir: Path = Path.cwd()):
    base = out_dir / name
    print(f"🚀 创建 Vue3 项目: {name}")
    # package.json
    render("""{{
  "name": "{name}",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "vue": "^3.4",
    "vue-router": "^4.3",
    "pinia": "^2.1"
  }},
  "devDependencies": {{
    "@vitejs/plugin-vue": "^5.0",
    "typescript": "^5.4",
    "vite": "^5.2",
    "vue-tsc": "^2.0"
  }}
}}""", name, base / "package.json")
    render("""import {{ defineConfig }} from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({{
  plugins: [vue()],
  server: {{ port: 3000 }}
}})
""", name, base / "vite.config.ts")
    render("""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{name}</title></head>
<body><div id="app"></div><script type="module" src="/src/main.ts"></script></body>
</html>""", name, base / "index.html")
    render("""import {{ createApp }} from 'vue'
import {{ createPinia }} from 'pinia'
import App from './App.vue'
import router from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
""", name, base / "src" / "main.ts")
    render("""<script setup lang="ts">
import {{ RouterView }} from 'vue-router'
</script>

<template>
  <RouterView />
</template>
""", name, base / "src" / "App.vue")

def scaffold_fullstack(name: str, out_dir: Path = Path.cwd()):
    base = out_dir / name
    print(f"🚀 创建全栈项目: {name}")
    scaffold_fastapi(name, base / "backend")
    scaffold_vue3(name, base / "frontend")
    render("""services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
""", name, base / "docker-compose.yml")

def scaffold_python_pkg(name: str, out_dir: Path = Path.cwd()):
    base = out_dir / name
    print(f"🚀 创建 Python 库: {name}")
    render("""[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
description = "{name} library"
requires-python = ">=3.11"
""", name, base / "pyproject.toml")
    src = name.replace("-", "_")
    render("""def hello():
    return "{name} v0.1.0 ready"
""", name, base / "src" / src / "__init__.py")
    render("""import pytest
from {src} import hello

def test_hello():
    assert hello() == "{name} v0.1.0 ready"
""".replace("{src}", src), name, base / "tests" / "test_basic.py")

TEMPLATES = {
    "cli": scaffold_cli,
    "fastapi": scaffold_fastapi,
    "vue3": scaffold_vue3,
    "fullstack": scaffold_fullstack,
    "python-pkg": scaffold_python_pkg,
}

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        print("可用骨架类型:")
        for k in sorted(TEMPLATES):
            desc = {"cli": "Python CLI", "fastapi": "FastAPI 后端", "vue3": "Vue3 前端",
                    "fullstack": "FastAPI+Vue3 全栈", "python-pkg": "Python 库"}
            print(f"  workshop scaffold {k:<12s} {desc[k]}")
        return
    if cmd not in TEMPLATES:
        print(f"未知骨架: {cmd}")
        sys.exit(1)
    name = sys.argv[2] if len(sys.argv) > 2 else input("项目名: ")
    TEMPLATES[cmd](name)

if __name__ == "__main__":
    main()
