#!/bin/bash
# 环境健康检查 - 一键诊断所有AI服务
echo "═══════════════════════════════════════"
echo "  Hermes AI 环境诊断"
echo "═══════════════════════════════════════"

# WSL
echo ""
echo "📦 WSL Ubuntu:"
wsl -d Ubuntu-22.04 -- bash -c 'echo "  ✅ Running ($(hostname -I | awk \"{print \\$1}\"))"' 2>/dev/null || echo "  ❌ Not running"

# Ollama
echo ""
echo "🦙 Ollama:"
OLLAMA_PID=$(wsl -d Ubuntu-22.04 -- bash -c 'pgrep ollama' 2>/dev/null)
if [ -n "$OLLAMA_PID" ]; then
  curl -s --max-time 3 http://localhost:11434/api/tags > /dev/null 2>&1
  if [ $? -eq 0 ]; then
    echo "  ✅ Running (PID $OLLAMA_PID) - API reachable"
  else
    echo "  ⚠️  Process exists (PID $OLLAMA_PID) but API not reachable"
  fi
else
  echo "  ❌ Not running"
fi

# ComfyUI
echo ""
echo "🎨 ComfyUI:"
curl -s --max-time 3 http://127.0.0.1:8188/ > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "  ✅ Running - API reachable"
else
  echo "  ❌ Not running"
fi

# GPU
echo ""
echo "🎮 GPU:"
nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null | head -1 || echo "  ❌ Not detected"

# Proxy
echo ""
echo "🌐 Proxy (7890):"
curl -s --max-time 2 http://127.0.0.1:7890 > /dev/null 2>&1 && echo "  ✅ Running" || echo "  ⚠️  Not detected (may be OK)"

echo ""
echo "═══════════════════════════════════════"
echo "  如需启动:  ollama_restart.bat"
echo "═══════════════════════════════════════"
