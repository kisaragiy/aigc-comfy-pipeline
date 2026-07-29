@echo off
REM SDXL LoRA 训练启动脚本 — 用 ComfyUI venv 运行
SET PYTHONPATH=
SET HTTP_PROXY=
SET HTTPS_PROXY=
SET http_proxy=
SET https_proxy=
"C:\DrawingLive\ComfyUI\venv\Scripts\python.exe" "C:\Users\zwq\aigc-comfy-pipeline\workshop\train_sdxl_lora.py"
pause
