# 分镜提示词规范

> 用于 ComfyUI 管线的分镜描述 — 配合 workflow 生成连续角色一致性的序列帧。

---

## 八列分镜表格式

每一镜（scene / shot）按以下八列组织：

| 镜号 | 人物 | 场景 | 景别 | 音频提示 | 画面描述 | 台词 | 备注 |
|------|------|------|------|----------|----------|------|------|
| S01 | Knives | 校园天台，日落 | 中景 | 风声 + 脚步 | Knives 白色校服，靠在栏杆上，风吹动银发，凝视远方 | "终于结束了。" | 定场镜头 |
| S02 | Caster | 同上 | 过肩 | 脚步声靠近 | Caster 从 Knives 身后走近，粉发在逆光中发光 | "你在想什么？" | 对话正反打开始 |
| S03 | Knives | 同上 | 特写 | — | Knives 侧脸，眼神闪烁，嘴微张欲言又止 | "没什么。" | 话不对心 |

---

## 乒乓镜头规则（对话正反打）

用于两人对话场景，保持视觉节奏：

```
S01 → A 说话（过肩拍 B）
S02 → B 说话（过肩拍 A）
S03 → A 说话（过肩拍 B）
S04 → B 特写（情绪节点）
S05 → A 特写（反应）
```

**规则：**
- 两人对话至少交替 3 轮（6 镜）才能切走
- 每 2-3 轮插入一张特写强化情绪
- 避免单镜台词超过 15 字
- 角色在画面中的位置保持轴向一致（180 度规则）

---

## 形态五大要素

每个角色在每镜中必须明确以下五个维度：

| 维度 | 说明 | 示例 |
|------|------|------|
| **神态** | 面部表情、眼神方向、情绪状态 | `serious expression, furrowed brows, narrowed eyes` |
| **动作** | 肢体姿势、身体朝向、正在做什么 | `standing with arms crossed, leaning on wall` |
| **服饰** | 服装款式、颜色、材质 | `white school uniform, tie loosely worn, skirt` |
| **道具** | 手持物、场景交互物 | `holding a smartphone, book in left hand` |
| **肌理** | 皮肤质感、伤痕、纹身、特殊细节 | `cybernetic arm, circuit patterns glowing, smooth skin` |

缺少任何一个维度，LLM 补全时需明确标记 `[待补]`。

---

## 打斗物理化规则

用于战斗 / 动作分镜：

**禁止：**
- ✗ 文学比喻（"如闪电般"、"像子弹一样"）
- ✗ 模糊描述（"激烈打斗"、"你来我往"）
- ✗ 心理描写（"他感到愤怒"）

**强制：**
- ✓ 具体招式名 + 部位（"右直拳击向面部"、"扫堂腿攻下盘"）
- ✓ 粒子特效标注（`sparks, dust cloud, debris flying, impact burst`）
- ✓ 受力反馈（`recoil from impact, stagger backward, clothing torn`）
- ✓ 速度线/动态模糊（`motion lines, speed lines, action blur, dynamic pose`）

**示例对比：**

```
❌ 差："两人激烈交手，身影交错"
✅ 好："Knives 低身扫腿，dust cloud 从地面升起，
     Caster 后跳避开，空中转体，校服下摆飘起，
     motion lines 从 Caster 鞋尖延伸"
```

---

## 景别差异化规则

相邻镜头的景别必须有差异：

```
❌ S01 中景 → S02 中景 → S03 中景（重复、单调）
✅ S01 全景 → S02 中景 → S03 特写 → S04 过肩（递进）
```

**推荐切换模式：**

| 模式 | 序列 | 用途 |
|------|------|------|
| 递进式 | 全景 → 中景 → 特写 | 引入场景 → 聚焦角色 → 情绪 |
| 跳跃式 | 特写 → 全景 → 中景 | 冲击感 / 快速切换 |
| 环绕式 | 平视 → 俯视 → 仰视 | 展示空间关系 / 力量对比 |

同一景别不可连续使用超过 2 镜。

---

## prompt 注释规范（workflow JSON）

workflow JSON 中的 prompt 节点需要附带结构化注释，方便后续修改和复用：

```json
{
  "6": {
    "inputs": {
      "text": "masterpiece, best quality, ..."
    },
    "_prompt_meta": {
      "style": "anime, cyberpunk",
      "subject": "1girl, knives, closers, silver hair",
      "scene": "city street night, neon",
      "lighting": "neon rim light, volumetric",
      "camera": "cowboy shot, shallow dof",
      "quality": "8k, masterpiece, ultra detailed",
      "generated_by": "ollama qwen3:14b",
      "original_input": "赛博朋克少女，雨中夜景"
    }
  }
}
```

### 图片引用四要素描述

当需要引用参考图（IPAdapter / ControlNet）时，图片的描述必须包含：

```
[主体] + [场景] + [镜头] + [质量词]
```

**示例：**

```
ref_image_description = (
    "knives, upper body portrait, school uniform, "
    "classroom background with window light, "
    "medium shot, eye level, "
    "masterpiece, detailed face"
)
```

这四要素必须同时出现在 prompt 和 IPAdapter 参考图描述中，以保证一致性。
