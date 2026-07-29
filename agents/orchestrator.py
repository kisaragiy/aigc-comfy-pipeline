#!/usr/bin/env python3
"""工作流编排器 — 多熔炉并行模式

核心思想:
  一个复杂工作流 = N 个独立子工作流 + 1 个合并工作流
  每个子工作流在自己的资源预算内运行, 结果异步合并。

类比你的描述:
  ┌─ 高炉烧石头 (稳定性高, 耗时短) ─→ 石头 ✓
  矿脉 ─┤
      └─ 烟熏炉烤猪排 (温度精准, 耗时长) ─→ 熟猪排 ✓

  生图同理:
  ┌─ TXT2IMG 线稿 (低分辨率, 快速) ─→ 线稿 ✓
  提示词 ─┤
        ├─ 角色生成 (高分辨率, 精修) ─→ 角色图 ✓
        ├─ 背景生成 (全景, 无角色) ─→ 背景图 ✓
        └─ 后期合并 (Image Composition) ─→ 最终图 ✓

ComfyUI 工作流拆分策略:
  1. 空间拆分: 角色↔背景↔道具分别生 → 合成
  2. 阶段拆分: 草稿→线稿→上色→细化→后期
  3. 局部修复: 生完整图 → 检测崩坏部位 → 局部重绘
  4. 批量替换: 同模板换服装/表情/姿势

硬件约束引擎:
  - 检测可用 VRAM
  - 检测 GPU 型号
  - 按预算分配子工作流分辨率/步数/模型大小
============================================================ """

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# ════════════════════════════════════════════════════════════
# 硬件检测
# ════════════════════════════════════════════════════════════

class GPULevel(Enum):
    UNKNOWN = 0
    INTEGRATED = 1   # 核显 <4GB
    ENTRY = 2         # 入门 4-6GB
    MID = 3           # 中端 6-10GB
    HIGH = 4          # 高端 10-16GB
    ULTRA = 5         # 旗舰 16-24GB+
    DATACENTER = 6    # 数据中心 40GB+

@dataclass
class HardwareSpec:
    gpu_name: str = "unknown"
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    ram_total_gb: float = 0
    gpu_level: GPULevel = GPULevel.UNKNOWN
    
    def max_resolution(self) -> tuple[int, int]:
        """根据 VRAM 推荐最大分辨率"""
        if self.vram_free_mb >= 24000:  return (1920, 1080)
        if self.vram_free_mb >= 16000:  return (1536, 1024)
        if self.vram_free_mb >= 12000:  return (1280, 960)
        if self.vram_free_mb >= 8000:   return (1024, 768)
        if self.vram_free_mb >= 6000:   return (768, 768)
        if self.vram_free_mb >= 4000:   return (640, 640)
        return (512, 512)
    
    def max_batch_size(self) -> int:
        if self.vram_free_mb >= 24000: return 8
        if self.vram_free_mb >= 12000: return 4
        if self.vram_free_mb >= 6000:  return 2
        return 1
    
    def can_run_flux(self) -> bool:
        return self.vram_free_mb >= 12000
    
    def can_run_video(self) -> bool:
        return self.vram_free_mb >= 16000

def detect_hardware() -> HardwareSpec:
    """检测可用硬件 (nvidia-smi / Windows 兼容)"""
    spec = HardwareSpec()
    
    # 尝试 nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 3:
                spec.gpu_name = parts[0]
                spec.vram_total_mb = int(parts[1])
                spec.vram_free_mb = int(parts[2])
    except Exception:
        pass
    
    # 尝试 Windows WMIC
    if spec.vram_total_mb == 0:
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name,adapterram"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if "GB" in line or "MB" in line or line.strip():
                        spec.gpu_name = line.strip()
                        break
        except Exception:
            pass
    
    # 尝试通过 ComfyUI API 查询
    if spec.vram_free_mb == 0:
        try:
            import requests
            r = requests.get("http://127.0.0.1:8188/queue", timeout=2)
            if r.ok:
                spec.gpu_name = "ComfyUI (detected via API)"
                spec.vram_free_mb = 4096  # 保守估计
                spec.vram_total_mb = 8192
        except Exception:
            pass
    
    # 兜底
    if spec.vram_free_mb == 0:
        spec.vram_free_mb = 4096
        spec.vram_total_mb = 8192
        spec.gpu_name = "unknown"
    
    # 等级归类
    free = spec.vram_free_mb
    if free >= 40000:    spec.gpu_level = GPULevel.DATACENTER
    elif free >= 16000:  spec.gpu_level = GPULevel.ULTRA
    elif free >= 10000:  spec.gpu_level = GPULevel.HIGH
    elif free >= 6000:   spec.gpu_level = GPULevel.MID
    elif free >= 4000:   spec.gpu_level = GPULevel.ENTRY
    elif free > 0:       spec.gpu_level = GPULevel.INTEGRATED
    else:                spec.gpu_level = GPULevel.UNKNOWN
    
    return spec


# ════════════════════════════════════════════════════════════
# 子工作流定义
# ════════════════════════════════════════════════════════════

class WorkflowStage(Enum):
    ROUGH = "草稿阶段"      # 512x512, 10步, 快速构图
    LINEART = "线稿阶段"    # 控制网生成线稿
    COLOR = "上色阶段"     # 线稿→彩色
    DETAIL = "细化阶段"    # 原分辨率细化
    UPSCALE = "放大阶段"   # 2x/4x 放大
    INPAINT = "修复阶段"   # 局部重绘 (眼/手/背景)
    COMPOSITE = "合成阶段" # 多图合成
    FINAL = "最终输出"     # 输出/加水印/切图

@dataclass
class SubWorkflow:
    name: str
    stage: WorkflowStage
    workflow_file: str       # ComfyUI API JSON 路径
    resolution: tuple[int, int]
    steps: int
    vram_required_mb: int
    depends_on: list[str]   # 依赖的其他子工作流
    result_key: str         # 在合成阶段的键名
    
    def estimate_oom_risk(self, available_vram: int) -> float:
        """估算 OOM 风险 (0.0=安全, 1.0=必崩)"""
        if available_vram == 0:
            return 1.0
        ratio = self.vram_required_mb / available_vram
        if ratio <= 0.6:   return 0.0
        if ratio <= 0.8:   return 0.3
        if ratio <= 0.95:  return 0.6
        if ratio <= 1.1:   return 0.85
        return 1.0


# ════════════════════════════════════════════════════════════
# 编排策略 — 根据硬件自动决定拆分方案
# ════════════════════════════════════════════════════════════

@dataclass
class OrchestrationPlan:
    """一次生成的完整编排计划"""
    hardware: HardwareSpec
    sub_workflows: list[SubWorkflow] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)
    merge_workflow: Optional[str] = None
    
    def summary(self) -> str:
        lines = [
            f"╔══ 编排计划 ══╗",
            f"  硬件: {self.hardware.gpu_name} ({self.hardware.vram_free_mb}MB VRAM)",
            f"  子工作流: {len(self.sub_workflows)} 个",
        ]
        for sw in self.sub_workflows:
            oom = sw.estimate_oom_risk(self.hardware.vram_free_mb)
            risk = "⚠️" if oom > 0.5 else "✅"
            lines.append(f"  {risk} {sw.stage.value}: {sw.name} ({sw.resolution[0]}x{sw.resolution[1]}, {sw.steps}步)")
        
        lines.append(f"  并行分组: {len(self.parallel_groups)} 组")
        for i, group in enumerate(self.parallel_groups):
            lines.append(f"    第{i+1}轮并行: {', '.join(group)}")
        
        lines.append(f"╚══ 合计: {sum(sw.steps for sw in self.sub_workflows)} 步 ══╝")
        return "\n".join(lines)


def build_orchestration_plan(
    prompt: str,
    hardware: Optional[HardwareSpec] = None,
    # 可覆盖: 想要什么阶段
    has_character: bool = True,
    has_background: bool = True,
    need_video: bool = False,
    detail_level: str = "standard",  # draft/standard/detailed
) -> OrchestrationPlan:
    """根据提示词 + 硬件构建编排计划"""
    
    if hardware is None:
        hardware = detect_hardware()
    
    plan = OrchestrationPlan(hardware=hardware)
    max_res = hardware.max_resolution()
    batch = hardware.max_batch_size()
    
    # ── 草稿阶段 (总是先跑) ──
    draft_res = (max_res[0] // 2, max_res[1] // 2)
    plan.sub_workflows.append(SubWorkflow(
        name=f"构图草稿_{prompt[:20]}",
        stage=WorkflowStage.ROUGH,
        workflow_file="workflows/draft.json",
        resolution=draft_res,
        steps=10,
        vram_required_mb=2048,
        depends_on=[],
        result_key="draft"
    ))
    
    # ── 角色生成 (如果需要角色) ──
    if has_character:
        char_res = (max_res[0], max_res[1])
        char_vram = int(max_res[0] * max_res[1] / (1024*1024) * 2.5)
        plan.sub_workflows.append(SubWorkflow(
            name="角色生成",
            stage=WorkflowStage.LINEART,
            workflow_file="workflows/character.json",
            resolution=char_res,
            steps=20 if detail_level == "draft" else 30,
            vram_required_mb=max(2048, char_vram),
            depends_on=["draft"],
            result_key="character"
        ))
    
    # ── 背景生成 (并行, 不依赖角色) ──
    if has_background:
        bg_res = (max_res[0], max_res[1])
        bg_vram = int(max_res[0] * max_res[1] / (1024*1024) * 2.0)
        plan.sub_workflows.append(SubWorkflow(
            name="背景生成",
            stage=WorkflowStage.COLOR,
            workflow_file="workflows/background.json",
            resolution=bg_res,
            steps=20 if detail_level == "draft" else 28,
            vram_required_mb=max(1536, bg_vram),
            depends_on=["draft"],
            result_key="background"
        ))
    
    # ── 局部修复阶段 (独立子工作流, 处理眼睛/手/脚等细节) ──
    if detail_level != "draft":
        for part, res_scale, vram_factor in [
            ("眼睛修复", 0.3, 1.0),
            ("手部修复", 0.4, 1.2),
            ("服装细化", 0.5, 1.5),
        ]:
            part_res = (int(max_res[0] * res_scale), int(max_res[1] * res_scale))
            part_vram = int(part_res[0] * part_res[1] / (1024*1024) * vram_factor * 2)
            plan.sub_workflows.append(SubWorkflow(
                name=part,
                stage=WorkflowStage.INPAINT,
                workflow_file=f"workflows/{part}.json",
                resolution=part_res,
                steps=25,
                vram_required_mb=max(1024, part_vram),
                depends_on=["character"],
                result_key=part
            ))
    
    # ── 最终合成 (merge all) ──
    all_keys = [sw.result_key for sw in plan.sub_workflows]
    plan.sub_workflows.append(SubWorkflow(
        name="最终合成",
        stage=WorkflowStage.COMPOSITE,
        workflow_file="workflows/composite.json",
        resolution=max_res,
        steps=5,
        vram_required_mb=max(1024, int(max_res[0] * max_res[1] / (1024*1024) * 1.5)),
        depends_on=all_keys,
        result_key="final"
    ))
    
    # ── 计算并行分组 ──
    # DAG: draft → (character || background) → eyes/hand/clothing → composite
    plan.parallel_groups = [
        ["draft"],
        ["character", "background"],
        [k for k in all_keys if k not in ["draft", "character", "background", "final"]],
        ["final"],
    ]
    plan.parallel_groups = [g for g in plan.parallel_groups if g]
    
    return plan


# ════════════════════════════════════════════════════════════
# ComfyUI API 调用
# ════════════════════════════════════════════════════════════

def call_comfyui_workflow(workflow_json: dict, timeout: int = 300) -> dict:
    """调用 ComfyUI API 执行工作流"""
    import requests
    try:
        r = requests.post(
            "http://127.0.0.1:8188/prompt",
            json={"prompt": workflow_json},
            timeout=10
        )
        if r.ok:
            return {"status": "queued", "data": r.json()}
        return {"status": "error", "error": r.text}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "error": "ComfyUI 未运行 (127.0.0.1:8188)"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def prompt_comfyui_queue() -> dict:
    """查询 ComfyUI 队列状态"""
    import requests
    try:
        r = requests.get("http://127.0.0.1:8188/queue", timeout=3)
        if r.ok:
            return r.json()
        return {"running": 0, "queued": 0}
    except:
        return {"running": 0, "queued": 0, "error": "unreachable"}


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔════════════════════════════════════════════════╗")
    print("║     ComfyUI 工作流编排器                      ║")
    print("╚════════════════════════════════════════════════╝")
    
    # 检测硬件
    hw = detect_hardware()
    print(f"\n🔧 硬件检测:")
    print(f"  GPU: {hw.gpu_name}")
    print(f"  VRAM: {hw.vram_free_mb}MB / {hw.vram_total_mb}MB")
    print(f"  等级: {hw.gpu_level.name} ({hw.gpu_level.value})")
    print(f"  推荐最大分辨率: {hw.max_resolution()[0]}x{hw.max_resolution()[1]}")
    print(f"  Flux可行: {'✅' if hw.can_run_flux() else '❌'} 视频可行: {'✅' if hw.can_run_video() else '❌'}")
    
    # 构建编排计划
    plan = build_orchestration_plan("少女站在樱花树下", hardware=hw)
    print(f"\n{plan.summary()}")
    
    # ComfyUI 状态
    queue = prompt_comfyui_queue()
    print(f"\n🔌 ComfyUI API: {'✅' if 'running' in queue else '❌ 未运行'}")
    print(f"  队列状态: {queue}")
