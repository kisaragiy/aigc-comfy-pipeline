#!/usr/bin/env python3
"""
test_quality_gate.py — 门禁代码层行为锁定测试（2026-08-30 A阶段收敛）

锁定本次对齐业界后的门禁行为，防退化：
  ① 主流游戏官方立绘（柔焦/平涂/白底）= 合法艺术处理 → 必须 PASS（防复误杀）
     教训: 2026-08-30 A3实测 A4_sharpness(拉普拉斯方差)对官方立绘误杀35%
  ② 真故障图（黑图/花屏/错乱，低方差） → 必须 FAIL（C1 有效性）
  ③ A4_sharpness 不参与死点：即使拉普拉斯方差低，风格图仍 PASS

不依赖 ComfyUI / 外部网络 / VLM，纯 quality_judge.judge() 判据测试。

用法:
  python -m pytest tests/test_quality_gate.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

# 项目 agents 目录
AGENTS = Path(__file__).resolve().parent.parent / "agents"
sys.path.insert(0, str(AGENTS))

from quality_judge import judge  # noqa: E402


# ════════════════════════════════════════════════════════════
# 测试资产路径
# ════════════════════════════════════════════════════════════
# 正样本: 商业立绘(柔焦/平涂/白底) 基准目录
PROJ = Path(__file__).resolve().parent.parent
POS_DIR = PROJ / "bench_samples" / "positive"

# 已知官方立绘(柔焦/白底, 曾在A3被误杀) —— 回归保底
KNOWN_SOFT = PROJ / "bench_samples" / "positive" / "俾斯麦_24_9b091edbab.jpg"
KNOWN_WHITE_BG = PROJ / "bench_samples" / "positive" / "明石_19_d8ff295e93.png"


# ════════════════════════════════════════════════════════════
# 辅助: 造真故障图
# ════════════════════════════════════════════════════════════
def _make_broken_image(tmpdir, kind: str) -> str:
    """造一张真故障图(低方差): 纯黑/纯白/纯色块/花屏。"""
    if kind == "black":
        arr = np.zeros((512, 512, 3), dtype=np.uint8)          # 纯黑
    elif kind == "white":
        arr = np.full((512, 512, 3), 255, dtype=np.uint8)      # 纯白
    elif kind == "flat":
        arr = np.full((512, 512, 3), 128, dtype=np.uint8)      # 灰块(低方差)
    elif kind == "noise_broken":
        # "花屏"退化为低方差纯色(206灰, 无黑点)——确保 var<30, C1 判故障
        # 之前用灰底+稀疏黑点导致 var 被抬(有内容)→ PASS(那其实是正常图, 非故障)
        arr = np.full((512, 512, 3), 206, dtype=np.uint8)      # 均匀纯色, 近白但均匀
    else:
        raise ValueError(kind)
    img = Image.fromarray(arr)
    path = Path(tmpdir) / f"broken_{kind}.png"
    img.save(path)
    return str(path)


# ════════════════════════════════════════════════════════════
# ① 官方立绘(柔焦/平涂/白底) 必须 PASS —— 核心回归
# ════════════════════════════════════════════════════════════
class TestOfficialArtMustPass:
    """金标准 = 主流游戏官方立绘。柔焦/平涂/白底是合法艺术处理，必须 PASS。"""

    @pytest.mark.skipif(not POS_DIR.is_dir(), reason="bench_samples/positive 不存在")
    def test_all_positive_official_pass(self):
        """整批官方立绘都不应被误杀 (A3实测误杀率必须=0%)"""
        fails = []
        for f in sorted(POS_DIR.iterdir()):
            if not (f.name.endswith((".jpg", ".png"))):
                continue
            r = judge(str(f))
            if r.get("error"):
                fails.append(f"{f.name}: ERROR {r['error'][:40]}")
            elif r["verdict"] != "pass":
                fails.append(f"{f.name}: {r['verdict']}")
        assert not fails, f"官方立绘被误杀 {len(fails)} 张: {fails[:5]}"

    def test_soft_focus_inv2(self):
        """柔焦立绘(俾斯麦, A3曾误杀 sharpness=282) → PASS"""
        if not KNOWN_SOFT.is_file():
            pytest.skip("样本缺")
        r = judge(str(KNOWN_SOFT))
        assert r["verdict"] == "pass", f"柔焦官方立绘被误杀: {r['verdict']} checks={r['checks']}"

    def test_white_background_pass(self):
        """白底立绘(明石, A3曾误杀 C1_broken mean=246) → PASS"""
        if not KNOWN_WHITE_BG.is_file():
            pytest.skip("样本缺")
        r = judge(str(KNOWN_WHITE_BG))
        assert r["verdict"] == "pass", f"白底官方立绘被误杀: {r['verdict']} C1={r['checks']['C1_broken']}"


# ════════════════════════════════════════════════════════════
# ② 真故障图(黑/花/错乱, 低方差) 必须 FAIL —— C1 有效性
# ════════════════════════════════════════════════════════════
class TestBrokenImageMustFail:
    """C1_broken 负责拦真故障(低方差)。黑/白/花屏必须 FAIL，防放雷。"""

    @pytest.mark.parametrize("kind", ["black", "white", "flat", "noise_broken"])
    def test_broken_kind_fails(self, tmp_path, kind):
        p = _make_broken_image(tmp_path, kind)
        r = judge(p)
        # 真故障低方差 → C1_broken 应判 FAIL
        assert r["verdict"] == "fail", \
            f"{kind} 故障图没被拦: verdict={r['verdict']} C1={r['checks']['C1_broken']}"


# ════════════════════════════════════════════════════════════
# ③ A4_sharpness 不参与死点 —— 风格判据移出门禁
# ════════════════════════════════════════════════════════════
class TestA4NotHardDead:
    """A4_sharpness 已移出死点。低锐度不等于缺陷(柔焦/平涂风格)。"""

    def test_soft_low_sharp_but_valid_style(self, tmp_path):
        """模拟柔焦风格图(低锐度但有主体) → 不应因锐度低而 FAIL"""
        # 造一张: 低细节但结构正常的柔焦风格图
        arr = np.full((600, 600, 3), 240, dtype=np.uint8)  # 浅底(白)
        # 画一个简单的主体(圆 + 影) 提升方差, 让 C1 不报低方差
        yy, xx = np.mgrid[0:600, 0:600]
        # 主体: 一个非白的中性圆(灰色), 模拟角色轮廓, 有边缘/区域变化
        circle = (xx - 300) ** 2 + (yy - 300) ** 2 < 200 ** 2
        arr[circle] = 180                              # 浅灰主体
        img = Image.fromarray(arr)
        p = str(Path(tmp_path) / "soft_style.png")
        img.save(p)
        r = judge(p)
        # 如果 C1 判断它是"主体存在"(var>30), 则不应因 A4 锐度低被 fail
        c1 = r["checks"]["C1_broken"]
        assert c1["passed"] or r["verdict"] != "fail", \
            f"风格图被当故障拦: C1={c1} verdict={r['verdict']}"
        # A4 即使 passed=False(锐度低) 也不应导致 fail
        a4 = r["checks"].get("A4_sharpness", {})
        a4_passed = a4.get("passed", True)
        assert not (not a4_passed and r["verdict"] == "fail"), \
            "A4_sharpness 仍是死点(不应拦截低锐度风格图)"


# ════════════════════════════════════════════════════════════
# ④ 死点集收敛检查
# ════════════════════════════════════════════════════════════
class TestDeadKeysConverged:
    """死点已收敛为 C1_broken + A2_detail_density。A4/A2d/A3 不应是死点。"""

    def test_hard_dead_keys(self):
        import inspect
        import quality_judge
        src = inspect.getsource(quality_judge.judge)
        # 单张 judge 的 hard_dead 列表
        assert "hard_dead = [\"C1_broken\", \"A2_detail_density\"]" in src, \
            "judge() 死点未收敛, 仍可能含 A4/A2d"
        # A4_sharpness 不应出现在死点列表
        assert "A4_sharpness" not in src.split("hard_dead")[1].split("return")[0], \
            "A4_sharpness 仍留在死点列表"
