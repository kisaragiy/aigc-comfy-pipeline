FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝管线代码
COPY agents/ agents/
COPY workflows/ workflows/
COPY scripts/ scripts/

# 环境变量
ENV COMFY_URL=http://comfyui:8188/prompt
ENV OLLAMA_URL=http://ollama:11434/api/generate
ENV PYTHONPATH=/app/agents

# 默认入口
ENTRYPOINT ["python", "-m", "agents"]
CMD ["--help"]
