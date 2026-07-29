#!/usr/bin/env python3
"""ComfyUI launcher — strips PYTHONPATH to avoid Hermes venv pollution."""
import os, sys, subprocess

# Strip PYTHONPATH so ComfyUI uses its own venv's torch
os.environ.pop("PYTHONPATH", None)

comfy_root = r"C:\DrawingLive\ComfyUI"
os.chdir(comfy_root)

python = os.path.join(comfy_root, "venv", "Scripts", "python.exe")
main = os.path.join(comfy_root, "main.py")

args = [python, main, "--disable-mmap", "--lowvram"]
sys.exit(subprocess.call(args))
