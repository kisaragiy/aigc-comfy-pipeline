# ComfyUI 管线 — Agent 初始任务书

## 定位

**自然语言驱动的 AIGC 创作工坊** — ComfyUI 编排 · 批量生图 · 质量检测 · 漫画 · 视频

不是作品展示仓库，是工程化工具链。生成的图片是产出，编排脚本是产品。

## 版本规约

V0.X.0 = 大功能，V0.0.XXX = 小修。

- **V1.75.0** — cover 负向词+wx 导出实测 COMM-11~12（2026-08-15）<br>
　　　　　　默认负向词加人物硬伤词（bad hands/extra fingers/mutated hands 等）<br>
　　　　　　wx 表情上架全套规格实测（10 文件：主图/缩略图/横幅/封面/头像/标题图）<br>
　　　　　　全量 708 全过<br>
　　　　　　版本 1.75.0<br>
- **V1.74.0** — wait_images 队列感知+插画场景+手部词库 ENV-4/COMM-10（2026-08-15）<br>
　　　　　　comfy_utils.wait_images 队列深度检查+超时扩展（oc/emotes/create 全受益）<br>
　　　　　　illustration 类型加场景氛围词（VLM 建议：场景元素弱）<br>
　　　　　　wardrobe 加 hand 词库 5 类（手崩坏 SDXL 硬伤）<br>
　　　　　　全量 706 全过<br>
　　　　　　版本 1.74.0<br>
- **V1.73.0** — 封面 kb 门禁+KV 自动聚焦 COMM-8~9（2026-08-15）<br>
　　　　　　`cover --check` kb 29 规则质量门禁<br>
　　　　　　game_kv 复杂描述自动聚焦主角色（SDXL 多主体局限规避，翻译后追加）<br>
　　　　　　全量 705 全过<br>
　　　　　　版本 1.73.0<br>
- **V1.72.0** — 封面服装联动+oc 一键表情 COMM-6~7（2026-08-15）<br>
　　　　　　`cover --outfit gothic` 封面角色穿风格服装（wardrobe 贯通商业图）<br>
　　　　　　`oc emotes <名> --set ecchi` 角色卡身份一键表情包<br>
　　　　　　全量 703 全过<br>
　　　　　　版本 1.72.0<br>
- **V1.71.0** — 自动重试+系列一致性 COMM-5（2026-08-15）<br>
　　　　　　生成失败自动重试 3 次（重试前等队列清空防双份僵尸任务）<br>
　　　　　　`cover --verify` 系列一致性 VLM 检查（verify_consistency_paths：首张锚+双图对比）<br>
　　　　　　全量 701 全过<br>
　　　　　　版本 1.71.0<br>
- **V1.70.0** — 商业图 VLM 验证 COMM-4（2026-08-15）<br>
　　　　　　轻小说插画 ✅（角色特写+氛围合格）· 游戏 KV ✅（史诗感强，复杂多主体 SDXL 只抓最强元素）<br>
　　　　　　KV 超时根因链：队列僵尸 → 连续生成显存累积 → 手动清+重启后单张成功（7min lowvram）<br>
　　　　　　版本 1.70.0<br>
- **V1.69.0** — 商业图大尺寸超时 COMM-2（2026-08-14）<br>
　　　　　　实测抓 bug：game_kv 1536x864 生成超时（VRAM 压力）→ 降 1344x768 稳妥档<br>
　　　　　　版本 1.69.0<br>
- **V1.68.0** — 商业图类型扩展 COMM-1（2026-08-14）<br>
　　　　　　cover 加 illustration（轻小说插画 2:3 竖版）+ game_kv（游戏宣传 16:9 主视觉）<br>
　　　　　　全量 700 全过（+3 商业图测试：类型规格/中文标题渲染/类型边界）<br>
　　　　　　版本 1.68.0<br>
- **V1.67.0** — 全链路实测 E2E-1（2026-08-14）<br>
　　　　　　原创角色 silver_wolf（狼耳概念锚+银红记忆点+方舟装）端到端验证<br>
　　　　　　oc gen → kb 29 规则：服装 5/5 全 1.00 + 吸引力 4/4 全 1.00（0.87 总分）<br>
　　　　　　VLM 确认：绑带/装甲/披风三层设计，记忆点极高——衣品问题解决<br>
　　　　　　版本 1.67.0<br>
- **V1.66.0** — 吸引力闭环 + 环境修复 APPEAL-5~6 / ENV-3（2026-08-14）<br>
　　　　　　kb 加 APPEAL-01~04（记忆点/设计统一/裸露平衡/风格契合——29 规则）<br>
　　　　　　`emotes --outfit gothic` 表情穿风格服装（wardrobe 联动）<br>
　　　　　　go_manga.py WSL IP 探测修复（127.0.0.1 转发失效老坑）<br>
　　　　　　IP 参考边界：只取设计语言（服装/形象/鞋/画风），不做角色二创<br>
　　　　　　全量 697 全过<br>
　　　　　　版本 1.66.0<br>
- **V1.65.0** — oc 吸引力字段 APPEAL-4（2026-08-14）<br>
　　　　　　CHAR-APPEAL 五原则落地角色卡：identity 加 concept_anchor/memory_point/worldview<br>
　　　　　　`oc create --concept 白狐 --memory color_anchor,symbol --worldview fantasy`<br>
　　　　　　oc_to_prompt 词库展开（异质特征/记忆点/世界观）+ 旧卡归一化兼容<br>
　　　　　　tests/test_wardrobe.py 25 测试<br>
　　　　　　版本 1.65.0<br>
- **V1.64.0** — IP 参考库 + 吸引力分析 APPEAL-1~3（2026-08-14）<br>
　　　　　　IP_STYLES 36 个作品服装特征（`build --ip 原神` 风格锚注入）<br>
　　　　　　docs/CHAR-APPEAL.md 角色吸引力分析（萌百实抓 8 IP + 5 原则）<br>
　　　　　　APPEAL_ACCENTS 点睛裸露 10 类 + MEMORY_POINTS 记忆点 7 类 + WORLDVIEW_ANCHORS 8 类<br>
　　　　　　tests/test_wardrobe.py 24 测试<br>
　　　　　　版本 1.64.0<br>
- **V1.63.0** — 双版本生成实测 ART-8（2026-08-14）<br>
　　　　　　实测抓 bug：variant 追加被主服装淹没（泳装版出战术服）→ 改替换+风格锚<br>
　　　　　　VLM 确认泳装版生效 + 角色一致（发色/脸一致）<br>
　　　　　　版本 1.63.0<br>
- **V1.62.0** — 配饰/异质特征/光影词库 ART-5~7（2026-08-14）<br>
　　　　　　ACCESSORIES 配饰 7 类（首饰/武器挂载/头饰/科技/魔法）<br>
　　　　　　RACIAL_FEATURES 异质特征 8 类（兽耳/角/翼/尾/鳞/光环/獠牙/精灵耳）<br>
　　　　　　LIGHTING_STYLES 光影 8 类（轮廓光/逆光/体积光/冷暖/霓虹/棚拍）<br>
　　　　　　`wardrobe body --accessory/--racial/--lighting`<br>
　　　　　　tests/test_wardrobe.py 20 测试<br>
　　　　　　版本 1.62.0<br>
- **V1.61.0** — 人物绘制全景 ART-1~4（2026-08-14）<br>
　　　　　　docs/ART-KB.md 人物绘制要素全景（8 层 + 基本功/进阶/大师分层）<br>
　　　　　　wardrobe 加 arknight 方舟风（绑带/多层/不对称复杂设计）<br>
　　　　　　`--variant full/swim/lingerie/artistic` 穿/不穿双版本<br>
　　　　　　figure 人体层 + pose 姿势层词库<br>
　　　　　　tests/test_wardrobe.py 19 测试<br>
　　　　　　版本 1.61.0<br>
- **V1.60.0** — kb 衣品规则 + oc 子部件集成 AESTH-5 / WARD-6（2026-08-14）<br>
　　　　　　kb 加 OUTFIT-01~05 衣品量化规则（25 条 7 大类——设计感/协调/材质/配色/鞋袜配套）<br>
　　　　　　OUTFIT-05 部件不可见降级（半身图不误判，实测 0.84→1.00）<br>
　　　　　　oc identity 子部件词库展开（body/face_shape 词库值→英文描述）<br>
　　　　　　tests/test_wardrobe.py 15 测试<br>
　　　　　　版本 1.60.0<br>
- **V1.59.0** — 衣品混搭 WARD-4~5（2026-08-14）<br>
　　　　　　实测对比：完整词库 vs 笼统描述（同 seed 精致度明显提升）<br>
　　　　　　`wardrobe build --mix cyber,military` 多风格混搭（ARPG/异世界组合）<br>
　　　　　　审美方向补充：传统吸引力审美，禁止 PC 审美元素<br>
　　　　　　tests/test_wardrobe.py 13 测试<br>
　　　　　　版本 1.59.0<br>
- **V1.58.0** — 衣品知识库 WARD-1~3（2026-08-14）<br>
　　　　　　`wardrobe list/show/build` 12 风格完整服装设计词库（款式+剪裁+材质+装饰+鞋袜+配色）<br>
　　　　　　`wardrobe body` 子部件词库（身材/脸/眼/发/鞋/袜 6 类 + 细节）<br>
　　　　　　oc 角色卡 outfit=风格名自动展开（gothic/lolita 等）<br>
　　　　　　tests/test_wardrobe.py 9 测试<br>
　　　　　　版本 1.58.0<br>
- **V1.57.0** — 人物模块边缘第七轮 CHAR-14~15（2026-08-14）<br>
　　　　　　oc outfit_idx 越界/verify 半匹配区分度实测（1.0/1.0/0.0）<br>
　　　　　　idphoto 全组合降级链 · YOLO hand 损坏图降级确认<br>
　　　　　　tests/test_edge_cases.py 54 测试（累计）<br>
　　　　　　版本 1.57.0<br>
- **V1.56.0** — 猎奇向表情集 + LoRA 透传 EMOTE-3~4（2026-08-14）<br>
　　　　　　`--set horror` 猎奇向 12 表情（12魔器风格：狂气/病娇/崩坏/空洞/怨念/极黑）<br>
　　　　　　`emotes --lora` 角色 LoRA 透传（实测发现无 LoRA 角色会漂——触发词不够）<br>
　　　　　　实测：猎奇情绪传达精准（病娇甜美+危险/空洞死气/狂气疯狂）<br>
　　　　　　tests/test_emote_sets.py 8 测试<br>
　　　　　　版本 1.56.0<br>
- **V1.55.0** — 表情库来源域扩展 EMOTE-1~2（2026-08-14）<br>
　　　　　　表情库 12→31（galgame 差分/漫画夸张/成人向软色情）<br>
　　　　　　`emotes --set casual|galgame|manga|ecchi` 来源域预设<br>
　　　　　　集合完整性校验+emoji 全覆盖+adult 锚点<br>
　　　　　　tests/test_emote_sets.py 7 测试<br>
　　　　　　版本 1.55.0<br>
- **内容策略（2026-08-14 定）**：制作层软硬色情全支持；公开分层——硬色情完全 private（仅本地/不公开），软色情小范围公开。公开输出按隐私纪律三问走。
- **审美方向（2026-08-14 补充）**：传统吸引力审美（大众男性审美：番剧/好莱坞/游戏参照）。禁止政治正确审美元素——女权组织指导的无性吸引力设计、男同/跨性别/奇怪性别元素不做。服装参考来源含真人（明星/时尚设计），但保持传统吸引力。
- **V1.54.0** — 人物模块边缘第六轮 CHAR-12~13（2026-08-14）<br>
　　　　　　emotes 重复表情去重（防浪费生成）<br>
　　　　　　wx 导出深层目录自动创建<br>
　　　　　　tests/test_edge_cases.py 53 测试（累计）<br>
　　　　　　版本 1.54.0<br>
- **V1.53.0** — 人物模块边缘第五轮 CHAR-10~11（2026-08-14）<br>
　　　　　　换装一致性验证（服装变化不影响身份 1.0）<br>
　　　　　　旧版角色卡字段归一化（缺字段不崩）<br>
　　　　　　tests/test_edge_cases.py 51 测试（累计）<br>
　　　　　　版本 1.53.0<br>
- **V1.52.0** — 人物模块边缘第四轮 CHAR-9（2026-08-14）<br>
　　　　　　oc gen count 上限校验（count=1000 之前直接开跑——防资源浪费）<br>
　　　　　　tests/test_edge_cases.py 50 测试（累计）<br>
　　　　　　版本 1.52.0<br>
- **V1.51.0** — 人物模块边缘第三轮 CHAR-7~8（2026-08-14）<br>
　　　　　　oc verify 非角色图实测 0.00 分（无假阳性，VLM 一致性可靠）<br>
　　　　　　idphoto 换装失败降级链确认 · multi 模式补全确认<br>
　　　　　　interrogate 人物图反推实测正常<br>
　　　　　　tests/test_edge_cases.py 49 测试（累计）<br>
　　　　　　版本 1.51.0<br>
- **V1.50.0** — 人物模块边缘第二轮 CHAR-5~6（2026-08-14）<br>
　　　　　　multi ref_a/ref_b 参考图前置校验（缺/损坏立即报错）<br>
　　　　　　multi 未知模式/idphoto 坏参数友好处理<br>
　　　　　　tests/test_edge_cases.py 48 测试（累计）<br>
　　　　　　版本 1.50.0<br>
- **V1.49.0** — 人物模块边缘 CHAR-1~4（2026-08-14）<br>
　　　　　　outfit 服装图前置校验（缺图/损坏立即报错）<br>
　　　　　　emotes 空描述/非法表情/名字清洗<br>
　　　　　　人物模块全扫描（character/colorize/fix/idphoto）<br>
　　　　　　tests/test_edge_cases.py 44 测试（累计）<br>
　　　　　　版本 1.49.0<br>
- **V1.48.0** — 边缘情况第六轮 EDGE-16~17（2026-08-14）<br>
　　　　　　create seed 类型校验（API 层字符串友好报错）<br>
　　　　　　极端混合目录实测（空+损坏+好图+子目录全组合兼容）<br>
　　　　　　tests/test_edge_cases.py 38 测试（累计）<br>
　　　　　　版本 1.48.0<br>
- **V1.47.0** — 边缘情况第五轮 EDGE-13~15（2026-08-14）<br>
　　　　　　create 空描述/空白/count<1 校验（之前默默生成默认模板图=静默错误）<br>
　　　　　　中文/空格文件名全模块实测兼容<br>
　　　　　　panorama 20 张 0.0s 性能；oc 库损坏 JSON 跳过不崩<br>
　　　　　　tests/test_edge_cases.py 37 测试（累计）<br>
　　　　　　版本 1.47.0<br>
- **V1.46.0** — OC 全链路实测 + 边缘第四轮 OC-3~5 / EDGE-12（2026-08-14）<br>
　　　　　　celeste 原创角色实测：创建→中文翻译→SDXL+自有LoRA 生成 2 张→verify 1.00→kb 0.93<br>
　　　　　　`oc gen --lora` 串联自有风格 LoRA（②③ 打通）<br>
　　　　　　LoRA 名自动补 .safetensors；kb 阈值 0-1 校验<br>
　　　　　　tests/test_edge_cases.py 35 测试（累计）<br>
　　　　　　版本 1.46.0<br>
- **V1.45.0** — 风格蒸馏全链路实测完成 SD-4（2026-08-14）<br>
　　　　　　实测：数据集 4 图门禁 85 分 → 训练 800 步 23:37 loss 0.092 → LoRA style_cine_manga.safetensors（340MB）<br>
　　　　　　VLM 验证："右图更贴合目标（暖调光影+日漫线条+游戏立绘质感）"<br>
　　　　　　kb 审美检查 0.94 分（无文字/无签名/风格统一满分）<br>
　　　　　　版本 1.45.0<br>
- **V1.44.0** — 边缘情况第三轮 EDGE-9~11（2026-08-14）<br>
　　　　　　outpaint 负数方向/负目标尺寸中文友好报错<br>
　　　　　　blend 目录当图友好报错（open_image_safe 判定）<br>
　　　　　　compare 异尺寸/ interrogate 非法格式兼容<br>
　　　　　　tests/test_edge_cases.py 29 测试（累计）<br>
　　　　　　版本 1.44.0<br>
- **V1.43.0** — 边缘情况第二轮 EDGE-5~8（2026-08-14）<br>
　　　　　　biztext 批量 time bug 修复（NameError）<br>
　　　　　　标题参数边界（空标题/负字号友好报错）<br>
　　　　　　批量混合目录（坏图跳过不中断）<br>
　　　　　　超长标题 200 字/空角色卡兼容<br>
　　　　　　tests/test_edge_cases.py 25 测试（累计）<br>
　　　　　　版本 1.43.0<br>
- **V1.42.0** — 边缘防护层 EDGE-1~4（2026-08-14）<br>
　　　　　　`workshop/image_utils.py` open_image_safe 统一图片防护（替换 8 模块）<br>
　　　　　　enhance 静默失败链修复（损坏图立即报错，不假完成）<br>
　　　　　　interrogate 图片校验前置（不浪费 VLM 调用）<br>
　　　　　　tests/test_edge_cases.py 19 测试<br>
　　　　　　版本 1.42.0<br>
- **V1.41.0** — 风格蒸馏闭环 + 原创 OC 库 SD-1~3 / OC-1~2（2026-08-14）<br>
　　　　　　`style-distill` 风格蒸馏闭环（生成数据集→门禁→caption→训练→验证）<br>
　　　　　　`oc list/create/show/gen/verify` 原创角色库（角色卡+生成+一致性验证）<br>
　　　　　　tests/test_style_distill.py 5 + test_oc.py 6<br>
　　　　　　版本 1.41.0<br>
- **V1.40.0** — 审美知识库 AESTH-1~4（2026-08-14）<br>
　　　　　　`kb list` 列出 20 条规则 6 大类<br>
　　　　　　`kb check <图>` VLM+像素双引擎检查（实测素描图 0.95+抓 2 短板）<br>
　　　　　　`kb report <图>` 详细报告含建议<br>
　　　　　　kb_rules.json：构图/色彩/光影/造型/技术/风格 6 类规则，权重+来源<br>
　　　　　　tests/test_kb.py 6 测试<br>
　　　　　　版本 1.40.0<br>
- **V1.39.0** — 商业图细节第四轮 BZ-15~19（2026-08-14）<br>
　　　　　　`biztext --dir` 批量文字合成<br>
　　　　　　多行自动换行（_wrap_text 逐字换行，像素验证 2 行+副标题）<br>
　　　　　　`biz --poster-template` 海报 5 模板（新品/招聘/节日/活动/感恩）<br>
　　　　　　`biz --banner-template` Banner 4 模板（大促/上新/品牌/节日）<br>
　　　　　　`biz --vi` 扩 6 件套（+banner+social）<br>
　　　　　　tests/test_biz_flow4.py 6 测试<br>
　　　　　　版本 1.39.0<br>
- **V1.38.0** — 商业图细节第三轮 BZ-10~14（2026-08-14）<br>
　　　　　　`biz og` OG 分享预览图（1200x630）<br>
　　　　　　`biz card` 商务名片（3:2）<br>
　　　　　　`biz --vi` 品牌 VI 全套（logo/名片/封面/头像）<br>
　　　　　　`biz --resume` 简历头像（求职场景）<br>
　　　　　　`biztext --template sale/event --price --date` 促销模板（修标题重叠 bug，实测无重叠）<br>
　　　　　　tests/test_biz_flow3.py 7 测试<br>
　　　　　　版本 1.38.0<br>
- **V1.37.0** — 商业图细节第二轮 BZ-5~9（2026-08-14）<br>
　　　　　　`biztext <图> "标题"` 文字合成（PIL 后期排版——白字黑描边/半透明底/金线，实测无乱码）<br>
　　　　　　`biz --product-set` 产品主图 5 件套（白底/场景/细节/角度/手持）<br>
　　　　　　`biz --variants <主图>` 多尺寸适配 5 规格<br>
　　　　　　`biz --social` 社交封面 3:4（小红书/朋友圈）<br>
　　　　　　`biz --check-text` VLM 文字检查门禁<br>
　　　　　　tests/test_biz_flow2.py 7 测试<br>
　　　　　　版本 1.37.0<br>
- **V1.36.0** — 商业图模块 B-biz（2026-08-14）<br>
　　　　　　`biz <主题> "描述"` 商业图 8 主题（qwen-image 中文直喂，实测产品图达电商标准）<br>
　　　　　　`--style` 6 品牌风格预设（tech/minimal/luxury/fresh/warm）<br>
　　　　　　`--batch` 统一风格批量系列化<br>
　　　　　　无文字铁律（默认禁文字，实测 0 乱码）<br>
　　　　　　tests/test_biz_flow.py 6 测试<br>
　　　　　　版本 1.36.0<br>
- **V1.35.0** — 生图细节第八轮 DF-25~28（2026-08-14）<br>
　　　　　　`restore` 全组合（划痕+上色+超分流水线，修互斥缺陷）<br>
　　　　　　`bg-replace --dir` 批量背景替换<br>
　　　　　　`info --dir` 批量规格检查（汇总表）<br>
　　　　　　`compare --dir-before/--dir-after` 批量配对对比<br>
　　　　　　tests/test_core_ops_details8.py 6 测试<br>
　　　　　　版本 1.35.0<br>
- **V1.34.0** — 生图细节第七轮 DF-23~24 + 新命令（2026-08-14）<br>
　　　　　　`enhance --dir` 批量高清修复<br>
　　　　　　`panorama <图1> <图2>...` 全景拼接（横向/纵向，实测 3 张拼 240x60）<br>
　　　　　　`restore --scratch` 划痕修复（亮度极值检测+中值迭代，实测 255→128）<br>
　　　　　　`info <图>` 图片信息查看（EXIF/ComfyUI metadata）<br>
　　　　　　tests/test_core_ops_details7.py 6 测试<br>
　　　　　　版本 1.34.0<br>
- **V1.33.0** — 生图细节第六轮 DF-20~22 + 新命令（2026-08-14）<br>
　　　　　　`enhance <图>` 高清修复管线（去噪→超分→修脸→对比，实测 64→128）<br>
　　　　　　`bg-replace <图> "新背景"` 背景替换（SAM 抠主体+InvertMask 重绘）<br>
　　　　　　`img2img --auto-best` 变体 VLM 评分自动选最佳<br>
　　　　　　`inpaint --watermark` 去水印（右下角自动定位）<br>
　　　　　　`blend --dir-a/--dir-b` 批量两两融合<br>
　　　　　　tests/test_core_ops_details6.py 7 测试<br>
　　　　　　版本 1.33.0<br>
- **V1.32.0** — 生图细节第五轮 DF-16~19（2026-08-14）<br>
　　　　　　`stylize --dir` 批量风格化（统一画风）<br>
　　　　　　`outpaint --target-w/--target-h` 目标尺寸扩图<br>
　　　　　　`inpaint --invert` 反向重绘（InvertMask）<br>
　　　　　　`img2img --pipeline` 组合管线（反推→修改→生成→对比）<br>
　　　　　　tests/test_core_ops_details5.py 5 测试<br>
　　　　　　版本 1.32.0<br>
- **V1.31.0** — 生图细节第四轮 DF-11~15（2026-08-14）<br>
　　　　　　`inpaint --dir` 批量重绘 + `--compare` 每张对比<br>
　　　　　　`img2img --faceid` InstantID 保脸（失败回退）<br>
　　　　　　`outpaint --iterations N` 循环扩图（放大倍数）<br>
　　　　　　`interrogate --lora-hint` LoRA 触发词检测<br>
　　　　　　img2img 自动 params.json 参数记录（可复现）<br>
　　　　　　tests/test_core_ops_details4.py 6 测试<br>
　　　　　　版本 1.31.0<br>
- **V1.30.0** — 生图细节第三轮 DF-6~10（2026-08-14）<br>
　　　　　　`stylize <内容图> <风格图>` 风格迁移（IPAdapter 双参考）<br>
　　　　　　`img2img --dir` 批量处理 + `--compare` 每张对比<br>
　　　　　　`inpaint --feather N` mask 羽化（边缘过渡）<br>
　　　　　　`blend --gradient` 渐变融合（实测红→紫→蓝无拼接缝）<br>
　　　　　　`interrogate --edit` 反推+修改组合（--recreate 分支恢复）<br>
　　　　　　tests/test_core_ops_details3.py 6 测试<br>
　　　　　　版本 1.30.0<br>
- **V1.29.0** — 生图细节第二轮 DF-1~5（2026-08-14）<br>
　　　　　　`interrogate --recreate` 反推→生成闭环 / `--dir` 批量反推<br>
　　　　　　`compare <原图> <结果>` 前后对比图（左右/上下+标注，实测清晰）<br>
　　　　　　`inpaint --areas` 多区域叠加重绘 + `--compare` 自动对比<br>
　　　　　　`outpaint --tile` 无缝平铺壁纸<br>
　　　　　　`blend --char-face --char-outfit` 角色融合（A脸B装）<br>
　　　　　　tests/test_core_ops_details.py 7 测试<br>
　　　　　　版本 1.29.0<br>
- **V1.28.0** — 核心生图操作五件套（2026-08-14）<br>
　　　　　　`interrogate <图> [--format]` 图片反推（natural/sdxl/tag，实测海报→prompt 准确）<br>
　　　　　　`img2img <图> "描述" [--denoise]` 通用图生图（三档强度+多变体）<br>
　　　　　　`inpaint <图> "改" --area/--box` 局部重绘（SAM 文本定位/矩形 mask）<br>
　　　　　　`outpaint <图> [--right/--bottom/--left/--top]` 扩图（扩展区 mask 重绘）<br>
　　　　　　`blend <A> <B> [--weight] [--refine]` 图片融合（PIL 混合+img2img 精修）<br>
　　　　　　tests/test_core_ops.py 7 测试<br>
　　　　　　版本 1.28.0<br>
- **V1.27.0** — 支线细节第二轮 DFS-7~10（2026-08-14）<br>
　　　　　　`merch --print` 印刷规格（+出血线 CMYK TIFF）<br>
　　　　　　`idphoto --outfit` 证件照换装（西装/衬衫）<br>
　　　　　　`multi --ref-a --ref-b` 双角色参考图（防漂移）<br>
　　　　　　`assemble_page border_style` 分格边框（直角/圆角/斜切，像素级验证）<br>
　　　　　　tests/test_scene_branches2.py 5 测试<br>
　　　　　　版本 1.27.0<br>
- **V1.26.0** — 支线细节 DFS-4/5/6（2026-08-14）<br>
　　　　　　`wallpaper --dark --notch` 深色模式+刘海安全区<br>
　　　　　　`verify-page <图A> <图B>` 跨页角色一致检查（VLM 评分）<br>
　　　　　　`assemble_page` 音效字（ドン/砰/轰 16 词 → 白字黑描边斜向大字）<br>
　　　　　　tests/test_scene_branches.py 5 测试<br>
　　　　　　版本 1.26.0<br>
- **V1.25.0** — 场景 DFS 细节（2026-08-14）<br>
　　　　　　`emotes --wx` 微信表情上架全套规格（主图/缩略图/横幅/封面/头像/标题图）<br>
　　　　　　`idphoto --beauty --all-colors` 美颜+三色一键全出<br>
　　　　　　`cover --series N` 封面批量系列化（一集一封面/AB测试）<br>
　　　　　　tests/test_scene_details.py 5 测试<br>
　　　　　　版本 1.25.0<br>
- **V1.24.0** — AI证件照+服装上身+线稿上色（2026-08-14）<br>
　　　　　　`idphoto <照片> [--bg] [--size]` 证件照（SAM 抠人像+换底色+规格裁切，648K 热度）<br>
　　　　　　`outfit <服装图> [--model]` 服装上身（IPAdapter 参考+模特）<br>
　　　　　　`colorize <线稿> [--desc] [--color]` 线稿上色（Canny+ControlNet）<br>
　　　　　　tests/test_scene_round5.py 6 测试<br>
　　　　　　版本 1.24.0<br>
- **V1.23.0** — AI 海报 + 老照片修复（2026-08-14）<br>
　　　　　　`cover --type poster [--subtitle]` 海报（A4 竖版+大标题+副标题，196K 热度实测"标题可读+视觉中心"）<br>
　　　　　　`restore <图片> [--color] [--upscale 2]` 老照片修复（去噪/锐化/上色/超分）<br>
　　　　　　VLM 实测发现 poster 左上标题重复 → 已修（poster 只画底部）<br>
　　　　　　tests/test_restore_poster.py 6 测试<br>
　　　　　　版本 1.23.0<br>
- **V1.22.0** — 场景第三轮：多人同框+直播背景+动态表情+动态壁纸（2026-08-14）<br>
　　　　　　`multi "A" "B" [--mode]` 多人同框（couple/group/battle）<br>
　　　　　　`wallpaper --type live_bg` 直播背景（无角色场景）<br>
　　　　　　`emotes --gif` 动态表情（4帧GIF，1.38M热度场景）<br>
　　　　　　`wallpaper --dynamic` 动态壁纸（I2V 微动）<br>
　　　　　　tests/test_scene_round3.py 6 测试<br>
　　　　　　版本 1.22.0<br>
- **V1.21.0** — 封面多类型 + 周边设计（2026-08-14）<br>
　　　　　　`cover --type video|live|novel` 视频/直播/小说封面（实测小说封面"2:3竖版+书名可读+神秘氛围"）<br>
　　　　　　`merch "描述" [--type sticker|badge|standee|postcard]` 周边设计（透明底+原图保留）<br>
　　　　　　tests/test_merch_cover_types.py 6 测试<br>
　　　　　　版本 1.21.0<br>
- **V1.20.0** — B站主流生图场景（2026-08-14）<br>
　　　　　　`cover "描述" [--title]` 视频封面（16:9 高冲击力+标题留白，实测"流量密码型"）<br>
　　　　　　`character --generate --sheet` 三视图立绘（VTB 皮套）<br>
　　　　　　`emotes "角色描述" [--emotes]` 表情包批量（12 表情库）<br>
　　　　　　`wallpaper "描述" [--type phone|avatar|desktop]` 壁纸/头像<br>
　　　　　　tests/test_bstation_scenes.py 6 测试<br>
　　　　　　版本 1.20.0<br>
- **V1.19.0** — 条漫模式 webtoon（2026-08-14）<br>
　　　　　　`assemble_page layout=webtoon` 竖排条漫（1 列大格 1:1.45，手机阅读，角色神态放大）<br>
　　　　　　`manga --layout webtoon` + `manga-book --webtoon` 整本条漫<br>
　　　　　　气泡密度补偿条漫"信息量低"缺点；VLM 实测"优秀水准：剧情推进自然"<br>
　　　　　　canvas 尺寸 bug 修复（列/行 acc 变量共用 → 分离 acc_w/acc_h，影响所有非对称布局）<br>
　　　　　　tests/test_manga_webtoon.py 4 测试<br>
　　　　　　版本 1.19.0<br>
- **V1.18.0** — 台词气泡 B1 + 多页漫画 B3（2026-08-14）<br>
　　　　　　`assemble_page` 真正漫画气泡：椭圆对话/tail 尖角/rect 旁白（按备注自动分型，自适应换行）<br>
　　　　　　中文字体修复：msyh.ttc 优先（arial 无中文字形→中文静默空白，实测修复）<br>
　　　　　　`manga-book "剧本" [--pages N] [--shots-per-page 4]` 整本漫画（E1 续写→分页→E4 拼版→封面→metadata）<br>
　　　　　　tests/test_manga_balloon_book.py 7 测试<br>
　　　　　　版本 1.18.0<br>
- **V1.17.0** — 漫画布局自动匹配 E4（2026-08-14）<br>
　　　　　　`assemble_page auto` 按面板比例自动选布局（7 模板：L4/L4_v/grid2x2/strip4/grid3/strip3/grid6，业界 parseLayoutFromStoryboards）<br>
　　　　　　大格缩放（漫画节奏感）+ 绝对路径健壮性（os.path.isabs 支持）<br>
　　　　　　tests/test_manga_layout.py 10 测试（匹配规则/模板有效性）<br>
　　　　　　版本 1.17.0<br>
- **V1.16.0** — 漫画逐批续写 E1（2026-08-14）<br>
　　　　　　`manga --batch-size 2` 逐批续写分镜（业界对齐 AI Comic Factory：每次生成 2 格，已有分镜 JSON 喂回 LLM 续写）<br>
　　　　　　实测 4 格：故事连贯递进 + 角色形态五要素一致 + 景别差异化 + 乒乓镜头<br>
　　　　　　`ollama_generate` 加 WSL IP 漂移兜底（127.0.0.1 不通自动探测 WSL 地址，根治复发性坑）<br>
　　　　　　tests/test_manga_batch_continuation.py 7 测试（解析/重编号/喂回/停止/降级）<br>
　　　　　　版本 1.16.0<br>
- **V1.15.0** — 画师工作流 M2/M3/M4（2026-08-14）<br>
　　　　　　`finalcheck --flip` 倒置/镜像检查（PIL 变体 + VLM 评估构图/对称）<br>
　　　　　　`finalcheck --focus` 焦点引导检查（VLM 评估视觉层级）<br>
　　　　　　`colorgrade <图片> [--warm] [--saturation] [--strength]` 色彩氛围统一（自动白平衡/色温，VLM 实测"高质量交付图"）<br>
　　　　　　tests/test_artist_m2m3m4.py 5 测试（flip 2 + colorgrade 3）<br>
　　　　　　版本 1.15.0<br>
- **V1.14.0** — 画师工作流 M1 黑白光影稿（2026-08-14）<br>
　　　　　　`compose --value <序号>` 上色前确认明暗结构（value study：PIL 灰度+对比度，零显存）<br>
　　　　　　`compose --value <序号> --contrast 1.3` 调对比度；VLM 实测"专业级：明暗清晰+焦点引导三层动线"<br>
　　　　　　tests/test_compose_value.py 3 测试（灰度/对比度/亮度）<br>
　　　　　　版本 1.14.0<br>
- **V1.13.0** — 当前：质检依赖修复 + 业界最佳差距分析（2026-08-14）<br>　　　　　　`docs/GAP-ANALYSIS.md` 差距矩阵（16 项：质检半残/后处理缺失/断点续跑缺等 + 原因分类 + ADR）<br>　　　　　　质检恢复：OpenCV 模糊/脚检测实测生效（综合分 0.92→1.00）——用系统 Python311（`/c/Users/zwq/AppData/Local/Programs/Python/Python311/python.exe`，有 cv2 4.10）<br>　　　　　　requirements.txt 补全依赖（numpy/cv2-headless/Pillow，此前只有 requests 导致质检 cv2 静默跳过）<br>　　　　　　根因：依赖未声明 + 运行环境未固定（python 解析到 Hermes venv 无 cv2）<br>　　　　　　⚠️ 质检/测试跑系统 Python311，不用 `python`（Hermes venv 缺 cv2）<br>　　　　　　`create_batch --resume` 断点续跑：读 batch_metadata.json 跳过已成功条目，元数据合并防覆盖（tests/test_batch_resume.py 5 测试）<br>　　　　　　质检人脸检测修复：YOLO subprocess 调 ComfyUI venv（Haar 对动漫脸误报"未检测到人脸"→ YOLO 实测"1 张人脸"，综合分 0.83→1.00；修 MediaPipe 假成功 + subprocess % 格式 bug）<br>　　　　　　超分修复：build_upscale_workflow ImageScaleBy 参数 upscale_by/method → scale_by/upscale_method（实测 7168×9216=2.0x）<br>　　　　　　ComfyUI 队列巡检 cron（comfyui_queue_watchdog.py 每 10 分钟，僵尸任务>120min 自动 interrupt）<br>　　　　　　版本 1.13.0<br>
- **V1.12.0** — 上一版：VLM 审美门禁修复（2026-08-14）<br>　　　　　　`workshop create --aesthetic-min-score N` 真正生效（此前参数空转）<br>　　　　　　`generate_with_quality` 新增 `vlm_min_score`（Flux 出图后 qwen3-vl 评分，不达标换 seed 重试）<br>　　　　　　`aesthetic_scorer` 修复：自动探测 WSL ollama IP / 512px 压缩提速 / PIL 延迟导入<br>　　　　　　`build_flux_workflow` 补齐 create.py 传参（aesthetic_min_score/faceid/controlnet 占位）<br>　　　　　　`workshop create` 中文自动翻译（检测 CJK + SDXL 自动启用 Ollama，防中文直塞英文 tag 模型主体跑偏）<br>　　　　　　VLM 评分新增 `has_subject` 主体符合度检测（画面无主体按不达标重试，防"魔杖图拿高分"）<br>　　　　　　`generate_with_quality` 修复 image_paths 未定义 bug（wait_images 失败时最后 return 崩溃）<br>　　　　　　Ollama IP 漂移修复：engine.py 两处硬编码 172.18.9.126 改动态探测（wsl hostname -I）<br>　　　　　　翻译模型 qwen3:14b→qwen3.5:9b（加载快3倍）+ 超时 30s→60s<br>　　　　　　VLM 评分前自动 `POST /free` 卸载 ComfyUI 模型（12G 单卡显存错峰）<br>　　　　　　坑：VLM 卡死根因 = ComfyUI 驻留大模型抢显存；中文 prompt 进 SDXL 会画魔杖<br>　　　　　　版本 1.12.0<br>
- **V1.11.0** — 上一版：画师工作流四件套（P0-P3 全落地）<br>　　　　　　`workshop fix` 局部修复 inpaint（box/YOLO auto + mask 羽化）<br>　　　　　　`workshop compose` 构图先行（缩略图风暴→Canny→ControlNet 精修）<br>　　　　　　`workshop layer` 分层绘制（双分层→语义分割抠图→PIL 合成）<br>　　　　　　`workshop finalcheck` 终检清单（透视/比例/光影/边缘/色彩/崩坏六项）<br>　　　　　　`workshop converge` 意图收敛（锚点→变体→微调）+ refcheck 双图对比<br>　　　　　　版本 1.11.0<br>
- **V1.10.0** — 上一版：模型兼容知识库 + 质量自动重试 + 多角度 prompt + 角色 LoRA 训练<br>　　　　　　`workshop/models/knowledge.md` 模型兼容性文档<br>　　　　　　`workshop/models/registry.json` 程序可读模型/recipe 库<br>　　　　　　`agents/model_compat.py` 提交前自动检查兼容性<br>　　　　　　`agents/comfy_utils.py` 出图后自动记录 recipe<br>　　　　　　`workshop/inspect/auto_retry.py` 质检不合格自动换 seed 重试<br>　　　　　　`workshop/engine/variant.py` 多角度 prompt 策略（特写/半身/全身）<br>　　　　　　`workshop/engine/ref.py` 参考图 CLIP 分析 → 结构化特征<br>　　　　　　`workshop/prototype.py` 原创角色流水线（20 张原型→挑选→变体）<br>　　　　　　Flux.1 dev LoRA 训练管线（comfyui-fluxtrainer）<br>　　　　　　版本 1.10.0<br>
- **V0.92.0** — 上一版：角色特征保持方案调研（IP-Adapter/ReferenceLatent/IFTv3）<br>　　　　　　IP-Adapter 全线 7 变种测试：均无法锁住动漫角色特征<br>　　　　　　Flux ReferenceLatent + IdentityFeatureTransferV3 HARD\_LOCK 测试<br>　　　　　　Flux.2 Klein 与 FluxTrainer 架构不兼容（3072dim vs 4096dim）<br>　　　　　　下载 flux1-dev-fp8 标准 Flux.1 模型 + ae VAE + clip\_L 完成<br>　　　　　　Flux.1 dev LoRA 训练流程打通<br>　　　　　　版本 0.92.0<br>
- **V0.91.0** — 上一版：质量分级工作流 + 审美门禁<br>　　　　　　`workshop/workflows/` 三级工作流（bare/standard/premium）<br>　　　　　　`agents/planner.py` 自然语言→工作流自动选择<br>　　　　　　VLM 审美评分门禁（Qwen3.5-9B）<br>　　　　　　版本 0.91.0<br>
- **V0.90.0** — 上一版：视频管线完善 + 漫画管线<br>　　　　　　Wan2.2 视频生成接入 workshop CLI<br>　　　　　　漫画分镜→逐格生图→拼页→Gallery<br>　　　　　　版本 0.90.0<br>
- **V0.80.0** — 上一版：面试展示里程碑（release v1.0.0）<br>　　　　　　CLI 统一入口（16+ 命令）<br>　　　　　　`workshop demo` 面试样张生成<br>　　　　　　serve API（12 个端点）<br>　　　　　　Docker 部署<br>　　　　　　295 项测试<br>　　　　　　版本 0.80.0<br>
- **V0.71.0** — IP-Adapter 调研 + 文本分析增强 + 质量门禁 bug 修复<br>　　　　　　**IP-Adapter 验证结论**: XLabs Flux IP-Adapter 模型 (`double_blocks.*` keys) 与<br>　　　　　　　comfyui_ipadapter_plus 节点 (`image_proj.*` / `ip_adapter.*` keys) 不兼容<br>　　　　　　　已移除 IP-Adapter workflow 节点，XLabs 模型已清理（节省 936MB）<br>　　　　　　--ref 当前走 Ollama 文本分析 + Qwen3 文本编码（无视觉条件控制）<br>　　　　　　**文本分析增强（保留）**: _ollama_vl_analyze prompt 改为英文 + 结构化 JSON<br>　　　　　　ref_analyze_to_prompt 返回新增 composition/lighting/colors/background 字段<br>　　　　　　**质量门禁 bug 修复**: create.py 图片路径解析支持 generate_with_quality 返回的绝对路径格式<br>　　　　　　agents/go_flux.py 工作流构建移除不兼容的 IP-Adapter 节点<br>　　　　　　workshop/engine/engine.py 参考图分析增强<br>　　　　　　tests/test_go_flux_workflow.py +9 项工作流测试<br>　　　　　　tests/test_workshop_engine.py +3 项增强字段测试<br>　　　　　　测试总数 283 → 295 项<br>　　　　　　版本 0.71.0<br>
- **V0.70.0** — 上一版：workshop create --batch-file 批量管线<br>　　　　　　从文本文件读取多条 prompt，逐条执行完整创作管线<br>　　　　　　每行一条 prompt，空行和 # 注释行自动跳过<br>　　　　　　每条 prompt 在输出目录下创建独立子目录（<编号>_<slug>/）<br>　　　　　　自动保存 best.png + metadata.json + Gallery 到子目录<br>　　　　　　控制台显示实时分步进度 [3/5] prompt [2/4] ✅✅❌✅<br>　　　　　　末尾汇总：成功数/失败数/每条 best seed + score<br>　　　　　　生成 batch_metadata.json 保存批量元数据<br>　　　　　　`workshop/create.py` 新增 `create_batch()` + `_make_slug()`<br>　　　　　　`tests/test_workshop_create.py` +7 项批量测试<br>　　　　　　测试总数 276 → 283 项<br>　　　　　　版本 0.70.0<br>
- **V0.69.0** — 上一版：Gallery 下载按钮 + workshop create --clean<br>　　　　　　Gallery Lightbox 右上角 ⬇ 下载当前图片（download 属性，浏览器原生保存）<br>　　　　　　Lightbox 新增 closeModal（点击背景关闭，非图片区域）<br>　　　　　　`workshop create --clean` 生成前清理输出目录旧文件<br>　　　　　　　　删除 *.png/*.jpg/*.jpeg/*.webp/*.json/*.html + gallery/ 子目录<br>　　　　　　`tests/test_workshop_create.py` +5 项测试（下载按钮2 + --clean3）<br>　　　　　　测试总数 271 → 276 项<br>　　　　　　版本 0.69.0<br>
- **V0.68.0** — 上一版：Gallery 键盘导航 + inspect --json<br>　　　　　　Gallery Lightbox 支持 ← → 箭头键切换候选图<br>　　　　　　Lightbox 底部显示"<当前>/<总数> ← →"计数器<br>　　　　　　Lightbox 支持 ESC 关闭<br>　　　　　　`workshop inspect --json` 输出结构化的 JSON 质检结果（适合程序处理）<br>　　　　　　JSON 模式自动隐藏进度提示，兼容管道/重定向用法<br>　　　　　　`tests/test_workshop_create.py` +3 项键盘导航测试<br>　　　　　　`tests/test_workshop_inspect.py` +3 项 JSON 输出测试<br>　　　　　　测试总数 265 → 271 项<br>　　　　　　版本 0.68.0<br>
- **V0.67.0** — 上一版：Gallery 质检详情 + --open gallery<br>　　　　　　Gallery 卡片新增逐部位分（Face/L-Eye/R-Eye/Hand/Foot/Blur）<br>　　　　　　逐部位分绿色(≥0.8) / 黄色(≥0.3) / 红色(<0.3) 彩色标签<br>　　　　　　`workshop create --open` 优先打开 Gallery HTML（完整上下文）<br>　　　　　　无 Gallery 时降级打开最优图<br>　　　　　　`tests/test_workshop_create.py` +1 项 `test_parts_displayed`<br>　　　　　　测试总数 264 → 265 项<br>　　　　　　版本 0.67.0<br>
- **V0.66.0** — 上一版：workshop video CLI + manga gallery 画廊<br>　　　　　　`workshop video <prompt>` 使用 workshop.video 模块生成（替代裸 go_video 委派）<br>　　　　　　支持完整参数：--frames/--fps/--seed/--preset/--preview/--neg/--ref/--output<br>　　　　　　`workshop video --preview` 预览视频参数（帧数/帧率/尺寸/种子/预设）<br>　　　　　　`workshop manga --output` 自动生成 HTML 画廊页（面板+拼页+角色+剧本）<br>　　　　　　`workshop/manga/manga.py` 新增 `generate_manga_gallery()` 函数<br>　　　　　　`agents/__main__.py` 新增 `_workshop_video()` 函数<br>　　　　　　`tests/test_workshop_video_manga_gallery.py` 7 项测试（gallery 5 + video preview 2）<br>　　　　　　测试总数 257 → 264 项<br>　　　　　　版本 0.66.0<br>
- **V0.65.0** — 上一版：workshop inspect --annotate + 批量摘要增强<br>　　　　　　`workshop inspect --annotate` 视觉标注质检结果到图片上<br>　　　　　　`workshop inspect --annotate --open` 标注后自动打开<br>　　　　　　标注内容：左上角综合分/各部位状态 + 底边渐变色状态条<br>　　　　　　`workshop inspect` 批量模式新增失败原因聚合（⚠️ 模糊: 3张 · 崩脸: 2张）<br>　　　　　　`workshop/inspect/inspector.py` 新增 `annotate_image()` 函数<br>　　　　　　`tests/test_workshop_inspect.py` 9 项测试（annotate + format_report + 批量摘要）<br>　　　　　　测试总数 248 → 257 项<br>　　　　　　版本 0.65.0<br>
- **V0.64.0** — 上一版：metadata.json 逐候选信息 + Gallery 增强<br>　　　　　　`workshop create --output` metadata.json 新增 `candidates[]` 数组：每候选 seed/score/retries/error/inspect<br>　　　　　　metadata.json 新增 `version` 和 `engine_detection` 字段（引擎推测）<br>　　　　　　Gallery 按综合分降序（最优排首位）+ 排名标签 (#1, #2...)<br>　　　　　　Gallery 新增负向提示词显示 + 引擎推测显示（有数据时）<br>　　　　　　`_maybe_save_output` 新增 `extra_meta` 参数供调用方补充元数据<br>　　　　　　`workshop create` 生成后自动补充引擎推测到已保存的 metadata.json<br>　　　　　　`tests/test_workshop_create.py` 16 项纯函数测试<br>　　　　　　测试总数 232 → 248 项<br>　　　　　　版本 0.64.0<br>
- **V0.63.0** — 上一版：增强 manga preview + 漫画纯函数测试 + char_prompt 死代码修复<br>　　　　　　`workshop manga --preview` 显示完整分镜表（6 列）+ 面板表（种子/尺寸/Prompt）<br>　　　　　　`workshop create --preview` 新增引擎推测 + 自动负向显示<br>　　　　　　增强 `storyboard_to_prompts`：修复 `char_prompt` 死代码，角色特征注入 prompt<br>　　　　　　`_template_storyboard` 修复空字符 IndexError 边界<br>　　　　　　`workshop/manga/manga.py` 关键 bug 修复<br>　　　　　　`tests/test_workshop_manga.py` 28 项纯函数测试（seed/尺寸/分镜/面板/Prompt）<br>　　　　　　测试总数 204 → 232 项<br>　　　　　　版本 0.63.0<br>
- **V0.62.0** — 上一版：自动负向检测 + workshop engine --ref<br>　　　　　　`_detect_negative()` 从 NL 文本自动提取负向提示词<br>　　　　　　“不要模糊背景” → `blurry, out of focus` / “别崩手” → `bad hands, deformed hands`<br>　　　　　　支持句式（不要/别/没有/不能有/排除）+ 直接关键词（模糊/崩手/太暗等）<br>　　　　　　`workshop create` 自动检测并追加到 style 预设负向后<br>　　　　　　`workshop engine --ref <image>` 测试参考图分析结果<br>　　　　　　引擎推测输出新增自动负向提示词显示<br>　　　　　　`tests/test_workshop_engine.py` +20 项 `_detect_negative` 测试<br>　　　　　　测试总数 184 → 204 项<br>　　　　　　版本 0.62.0<br>
- **V0.61.0** — 上一版：workshop create --negative + 引擎单元测试<br>　　　　　　`workshop create \"描述\" --negative \"blurry, bad hands\"` 自定义负向提示词<br>　　　　　　未指定 `--negative` 时自动使用风格预设的默认负向词（如 anime=bad hands, photoreal=anime...）<br>　　　　　　引擎推测输出新增负向提示词显示<br>　　　　　　`tests/test_workshop_engine.py` 65 项测试覆盖 `_detect_style`/`_detect_composition`/`_detect_lighting`/`_extract_keywords`/`_clean_subject`/`_template_fallback`/`list_presets`<br>　　　　　　测试总数 119 → 184 项<br>　　　　　　版本 0.61.0<br>
- **V0.60.0** — 上一版：manga --sdxl + auto-gallery<br>　　　　　　`workshop manga --sdxl` 使用 SDXL 代替 Flux（更快/支持 LoRA）<br>　　　　　　`workshop create --output` 自动生成候选画廊（无需单独 --gallery）<br>　　　　　　auto-gallery 保存在 `<output>/gallery/`，仍可手动指定 --gallery<br>　　　　　　版本 0.60.0<br>
- **V0.59.0** — 上一版：create 引擎推测 + --open<br>　　　　　　`workshop create` 始终显示引擎推测（风格/构图/光照）<br>　　　　　　`workshop create --open` 生成后自动打开最优图<br>　　　　　　`os.startfile` 在默认图片查看器中打开<br>　　　　　　版本 0.59.0<br>
- **V0.58.0** — 上一版：manga 重试 + create 排行榜<br>　　　　　　`workshop manga --retry N` 每格失败后重试（含递增延迟）<br>　　　　　　`generate_panels` 新增 `max_retries` 参数，空结果也触发重试<br>　　　　　　`workshop create` 输出候选排行榜 🥇🥈🥉（综合分/质检/CLIP）<br>　　　　　　版本 0.58.0<br>
- **V0.57.0** — 上一版：create --seed + manga --output<br>　　　　　　`workshop create --seed N` 固定种子，可复现结果<br>　　　　　　`workshop manga --output DIR` 保存拼页+逐格图+metadata.json<br>　　　　　　manga 输出目录包含逐格 panel_*.png 和 metadata.json（剧本/角色/路径）<br>　　　　　　版本 0.57.0<br>
- **V0.56.0** — 上一版：质检批量扫描 + 漫画剧本文件<br>　　　　　　`workshop inspect` 支持通配符/目录批量质检，输出汇总表<br>　　　　　　批量模式显示每张脸/眼/手/脚/模糊/综合分 + 通过率<br>　　　　　　`workshop manga --script-file` 从文件读取剧本<br>　　　　　　单张模式保留原详细报告格式<br>　　　　　　版本 0.56.0<br>
- **V0.55.0** — 上一版：引擎 Ollama 增强修复 + 自动地址探测<br>　　　　　　Ollama prompt 模板从中文改为英文，输出更干净<br>　　　　　　`_ollama_enhance` 自动探测 Ollama URL（环境变量→默认→WSL）<br>　　　　　　`_clean_ollama_output` 去中文行/引号/尾随分隔符<br>　　　　　　`workshop engine --ollama` 新增 CLI 参数<br>　　　　　　`_ollama_vl_analyze` 支持 OLLAMA_URL 环境变量<br>　　　　　　版本 0.55.0<br>　　　　　　
- **V0.48.0** — 上一版：serve API 升级（新增 control/sweep/abtest/bestof 端点）<br>　　　　　　`POST /api/control` — ControlNet 条件生图，ref/type/model，走 generate_with_quality <br>　　　　　　`POST /api/sweep` — 参数网格扫描，grid/type，走 generate_with_quality <br>　　　　　　`POST /api/abtest` — A/B 双 Prompt 对比，prompts[2]，走 generate_with_quality <br>　　　　　　`POST /api/bestof` — Best of N 多轮择优，count/prompt，走 generate_with_quality<br>　　　　　　API 版本升至 0.48.0，新增 4 个后台异步端点 + quality 门禁全覆盖
- **V0.47.0** — 上一版：AB Test / Best of N 升级 generate_with_quality + 质量门禁<br>　　　　　　`python -m agents abtest --prompts "A" "B" --preset anime --min-score 0.2` <br>　　　　　　`python -m agents bestof "prompt" --count 4 --retry 2 --min-score 0.25` <br>　　　　　　替换直调 `build_flux_workflow` 为 `generate_with_quality`，新增 `--preset`/`--min-score`/`--retry`/`--no-validate`
- **V0.46.0** — 上一版：gallery 新增全屏/幻灯片/键盘导航<br>　　　　　　点击图片全屏 Lightbox，← → 翻页，缩略图条，Esc 关闭
- **V0.45.0** — 上一版：video-process 新增帧提取 (--extract-frames --every / --count)
- **V0.43.0** — 上一版：sweep 升级 quality（generate_with_quality + --preset + 门禁）<br>　　　　　　`python -m agents sweep --grid '{\"steps\":[20,30]}' --preset anime --min-score 0.2` <br>　　　　　　`python -m agents sweep --type video --grid '{\"frames\":[49,81]}'` <br>　　　　　　图片/视频均走质量门禁，新增 `--preset`/`--seed`/`--min-score`/`--retry`/`--no-validate`
- **V0.42.0** — 上一版：测试覆盖 run.py（30 项）+ outputs 内联预览（--images/--open）<br>　　　　　　`python -m agents outputs list --images` 显示首文件名预览 <br>　　　　　　`python -m agents outputs show <id> --open` 打开产出目录 <br>　　　　　　测试总数 89 → 119 项
- **V0.41.0** — 上一版：lora/ipa/multi 升级 Flux + 模型管理增强<br>　　　　　　`python -m agents lora/ipa/multi` 增加 `--preset`/`--seed`/`--min-score`/`--retry` <br>　　　　　　`python -m agents models list --disk` 显示磁盘占用 <br>　　　　　　`python -m agents models prune [--force]` 清理孤立模型
- **V0.40.0** — 上一版：Run 升级 Flux（generate_with_quality + --lora + --preset）<br>　　　　　　`python -m agents run` 等价 `python -m agents flux` 超集 <br>　　　　　　支持 `--preset`/`--lora`/`--model`/`--steps`/`--min-score`/`--retry`
- **V0.39.0** — Run 视频路由 + 产出管理视频信息 <br>　　　　　　`python -m agents run "prompt" --video` 自动路由视频生成 <br>　　　　　　`python -m agents outputs show <id> --info` 显示视频时长/大小
- **V0.38.0** — Gallery 视频缩略图 + 测试覆盖增强（32→89 项）<br>　　　　　　`--refresh-posters` 强制刷新
- **V0.37.0** — 视频后处理工具 + 视频预览模式
- **V0.36.0** — 视频批量生成 + 参数扫描视频支持 + Gallery 增强筛选对比
- **V0.35.0** — 模型下载增强（含视频模型预设）+ 模型缓存刷新
- V0.34.0 — 上一版：模型完整性检查（含视频模型）+ CLI 文档同步
- V0.27.0 — A/B 测试
- V0.26.0 — Prompt 兜底 + 质量验证
- V0.25.0 — Docker 部署
- V0.24.0 — 视频生成管线（Wan2.2）
- V0.23.0 — ControlNet 能力补齐
- V0.22.0 — 工作流重建工程
- V0.21.0 — CLI 文档自动生成
- V0.20.0 — 一键诊断修复 (doctor)
- V0.19.0 — workflow API 格式转换
- V0.18.0 — 工程化测试 + CI
- V0.17.0 — Output Gallery 增强
- V0.16.0 — 模型下载
- V0.15.0 — ComfyUI 队列管理
- V0.14.0 — 管线验收报告
- V0.13.0 — 自动标图 + LoRA 训练闭环
- V0.12.0 — 批量迭代 + 参数扫描
- V0.11.0 — 输出管理深度集成（自动归档 + metadata）
- V0.10.0 — Flux.2 Klein 原生 CLI
- V0.9.0 — 模型管理（列表/查询/依赖检查）
- V0.8.0 — 工作流模板管理 + 依赖检查
- V0.7.0 — 管线健壮性 + 验证
- V0.6.0 — 统一 CLI + 输出管理
- V0.5.0 — LoRA 训练/批处理/IPAdapter/多角色/Flux.2 Klein 均已可用
- V0.0.XXX — 小修

## 当前版本：V0.67.0

## 核心能力

| 能力 | 入口 | 统一 CLI | 说明 |
|------|------|----------|------|
| 一句话出图 | `run.py` | `python -m agents run` | 自然语言 → Ollama 转写，**--video 切换视频**，支持 --lora/--preset/--model 等全参数 |
| 角色 LoRA 文生图 | `go_knives_lora.py` | `python -m agents lora` | SDXL/SD1.5 多角色（Knives / Caster）、批量、换装、**质量门禁 + --preset** |
| IPAdapter 锁脸 | `go_knives_ipadapter.py` | `python -m agents ipa` | 参考图驱动面部一致性、权重可调、**质量门禁 + --preset** |
| 多角色同框 | `go_multi_char_lora.py` | `python -m agents multi` | 双 LoRA + FaceDetailer 修脸、**质量门禁 + --preset** |
| 批处理 | `go_knives_lora.py --count N` | `python -m agents lora --count N` | 多张自动复制到草稿库 |
| 产出管理 | `output_manager.py` | `python -m agents outputs` | 结构化元数据、list/show/clean，**所有命令自动归档**，`list --images` 预览首文件，`show --open` 打开目录 |
| 环境检查 | `comfy_utils.py` | `python -m agents check` | 运行前探活 ComfyUI/Ollama，自助诊断 |
| Dry-run 验证 | `comfy_utils.DRY_RUN` | `--dry-run` 全局参数 | 跳过真实提交，验证参数正确性 |
| Flux.2 Klein 身份一致性 | agents 脚本加载 workflows/JSON | — | 身份引导 + 单图工作流 |
| Prompt 优化 | `comfy_utils.optimize_prompt()` | — | 六维度构图法转为结构化英文 tag |
| 工作流管理 | `workflow_manager.py` | `python -m agents workflow` | 模板扫描、参数 schema 提取、节点依赖检查、格式转换 |
| 模型管理 | `model_manager.py` | `python -m agents models` | 列出/查询/检查/下载、**--disk 磁盘占用**、**prune 清理孤立** |
| Flux.2 Klein 生图 | `go_flux.py` | `python -m agents flux` | 程序化构建 Flux 工作流（9B/4B、LoRA 注入） |
| 参数扫描 | `go_sweep.py` | `python -m agents sweep` | 网格参数迭代、自动对比拼图，**走 generate_with_quality**，支持 `--preset`/`--seed`/`--min-score`/`--retry` |
| 自动标图 | `go_caption.py` | `python -m agents caption` | Ollama VL 自动生成训练数据 .txt 标注 |
| 训练编排 | `go_train.py` | `python -m agents train` | 数据验证 + AutoDL 训练命令生成 |
| 管线报告 | `go_report.py` | `python -m agents report` | 一键验收：ComfyUI/模型/workflow/产出全貌 |
| 队列管理 | `go_queue.py` | `python -m agents queue` | 查看/清空/中断队列、释放显存 |
| 产出画廊 | `go_gallery.py` | `python -m agents gallery` | HTML 产出展示、HTTP 服务模式 |
| 一键诊断 | `go_doctor.py` | `python -m agents doctor` | 9 项环境检查 + 自动修复 |
| 单元测试 | `tests/` | `pytest tests/` | 204 项测试覆盖核心模块 + 视频管线 + run.py 参数映射 + workshop 引擎 |
| CLI 文档 | `docs/cli-reference.md` | `python scripts/gen_cli_docs.py` | 16 命令 + 子命令自动生成参考文档 |
| 高质量工作流 | `workflows/*.json` | `python scripts/build_workflows.py` | 6 个 API 格式工作流，带 _meta 元数据 |
| ControlNet | `go_control.py` | `python -m agents control` | depth/openpose/softedge/tile/inpaint/lineart 引导生图，**Flux/SDXL 双架构**，支持 --model 9b/4b/sdxl |
| 视频生成 | `go_video.py` | `python -m agents video` | Wan2.2 T2V/I2V，帧数/帧率/分辨率控制 |
| 创作工坊·漫画 | `workshop/manga/` | `python -m agents workshop manga` | 剧本→分镜→逐格生图→拼页，`--char` 动态角色 1~4 个 |
| Docker 部署 | `Dockerfile` + `docker-compose.yml` | `docker-compose up` | 三服务容器化（GPU 直通） |
| Prompt 兜底 | `comfy_utils._fallback_prompt()` | 内置 | Ollama 不可用时模板拼接英文 tag |
| 质量验证 | `go_validate.py` | `python -m agents validate` | CLIP score + 崩脸检测 + 图像质量 |
|| A/B 测试 | `go_abtest.py` | `python -m agents abtest` | 同 seed prompt 对比，**走 generate_with_quality**，支持 `--preset`/`--min-score`/`--retry` |
|| Best of N | `go_abtest.py` | `python -m agents bestof` | 多 seed 自动挑优 + 排名，**质量门禁 + --preset** |
||| API 服务 | `go_serve.py` | `python -m agents serve` | FastAPI REST API，异步作业队列，flux/lora/video/control/sweep/abtest/bestof 全端点 + quality 门禁 |
|| 一句话创作 | `workshop/create.py` | `python -m agents workshop create` | 引擎→多张生成→质检→排序→选最优，端到端管线 |
|| 创作工坊 CLI | `agents/__main__.py` | `python -m agents workshop` | workshop 子命令入口：create/engine/inspect/manga/video |
|| Prompt 引擎 | `workshop/engine/engine.py` | `python -m agents workshop engine` | 自然语言→专业绘画提示词，9 种风格预设，构图/光照/关键词库，模板兜底 |
|| 逐部位质检 | `workshop/inspect/inspector.py` | `python -m agents workshop inspect` | [脸:ok] [左眼:ok] [右眼:ok] [手:ok] [脚:ok] [模糊:正常] 结构化报告 |
|| 漫画/分镜生成 | `workshop/manga/manga.py` | `python -m agents workshop manga` | 剧本→八列分镜表→逐格 prompt→ComfyUI 出图→拼页+台词 |
|| 视频自动化 | `workshop/video/video.py` | `python -m agents workshop video` | 封装 Wan2.2 + 分镜驱动视频生成 + ffmpeg 拼接 |
| 质量预设 | `comfy_utils.QUALITY_PRESETS` | `--preset quality|fast|portrait` | 优选参数组合，环境变量 AIGC_PRESET |
| 视频预设 | `comfy_utils.VIDEO_PRESETS` | `--preset quality|fast|cinematic` | 视频专用预设，环境变量 AIGC_VIDEO_PRESET |
| 自动门禁 | `comfy_utils.generate_with_quality()` | `--min-score 0.25 --retry 3` | 出图验证 + 不合格自动重试 |
| 自定义预设 | `presets.json` | 项目根目录 JSON | 用户自定义 image/video 预设，无硬编码限制 |
| I2V 视频 | `go_video.py --ref` | `python -m agents video "..." --ref img.png` | Wan2.2 I2V，自动构建 LoadImage+VAEEncode 工作流 |
| Gallery 视频 | `go_gallery.py` | `python -m agents gallery` | HTML 画廊自动检测 .mp4 渲染 `<video>` 标签 |
| 视频 API | `go_serve.py /api/video` | `POST /api/video` | 异步视频作业（T2V/I2V + preset + timeout） |
| 队列智能感知 | `go_queue.py list` | `python -m agents queue list` | 自动区分 image/video 任务类型 |
|| Output 视频感知 | `output_manager.py` | `python -m agents outputs list` | images/videos 分开统计，show 显示文件列表 |
||| Run 视频路由 | `run.py --video` | `python -m agents run "..." --video` | 一句话出视频，支持全参数（ref/frames/fps/preset） |
||| 产出视频信息 | `__main__.py` | `python -m agents outputs show <id> --info` | 视频文件大小 + ffprobe 时长 |
|| 视频参数对齐 | `go_video.py --sampler --scheduler` | `python -m agents video "..." --sampler dpmpp_2m` | KSampler 参数可自定义，预设含 sampler/scheduler |
|| 视频模型检查 | `model_manager.check_video_models()` | `python -m agents models check video` | Wan2.2 三件套完整性 + 文件大小健康检查 |
|| CLI 文档同步 | `scripts/gen_cli_docs.py` | `python scripts/gen_cli_docs.py` | 22 个命令自动生成参考文档 |
||| 视频模型下载 | `model_download.download_video_models()` | `python -m agents models download video` | Wan2.2 三件套一键下载（HF 镜像预设） |
||| 模型缓存刷新 | `model_manager.refresh_cache()` | `python -m agents models refresh` | 清除扫描缓存，新增模型后不用重启 |
||| 列表实时扫描 | `list_models(no_cache=True)` | `python -m agents models list --no-cache` | 跳过缓存直接扫描磁盘 |
||| 视频预览模式 | `go_video.py --preview` | `python -m agents video "..." --preview` | 快速预览(25帧/480p/15步/CFG5)，自动打印正式命令 |
||| 视频后处理 | `go_video_process.py` | `python -m agents video-process` | GIF/裁剪/变速/拼接/帧提取，支持运行ID和链式操作 |
||| 帧提取 | `extract_frames()` | `--extract-frames --every N / --count N` | 从视频批量抽帧为JPG，支持间隔/均匀数量 |
||| Gallery 类型筛选 | `go_gallery.py --type` | `python -m agents gallery --type video` | 按 image/video 过滤，JS 对比视图 + 排序 |
||| Gallery 全屏/幻灯片 | `go_gallery.py` | `python -m agents gallery` | 点击图片全屏浏览，← → 键盘翻页，缩略图导航 |

## 项目结构

```
agents/                    # Python 编排脚本（产品）
  __init__.py              #   包标识 + 版本
  __main__.py              #   统一 CLI 入口
  run.py                   #   一句话出图入口
  comfy_utils.py           #   共享工具库（ComfyUI API / Ollama / 图片等待）
  output_manager.py        #   产出管理（结构化元数据）
  workflow_manager.py      #   工作流模板管理（扫描/schema/检查）
  model_manager.py         #   模型管理（列表/查询/依赖检查）
  go_flux.py               #   Flux.2 Klein 文生图
  go_sweep.py              #   参数网格扫描
  go_caption.py             #   自动标图（Ollama VL）
  go_train.py               #   训练编排（数据验证 + 命令生成）
  go_report.py              #   管线验收报告
  go_queue.py               #   ComfyUI 队列管理
  model_download.py         #   模型下载
  go_gallery.py             #   输出画廊
  go_doctor.py              #   一键诊断修复
  go_control.py             #   ControlNet 引导生图
  go_video.py               #   Wan2.2 视频生成
  go_video_process.py        #   视频后处理（GIF/裁剪/变速/拼接）
  go_validate.py            #   出图质量验证
  go_abtest.py              #   A/B 测试 + Best of N
  go_serve.py               #   REST API 服务
  go_knives_lora.py        #   角色 LoRA 文生图（主力脚本）
  go_knives_ipadapter.py   #   IPAdapter 锁脸（复用 go_knives_lora 的构建函数）
  go_multi_char_lora.py    #   多角色同框
  go_caster_lora.py        #   [兼容] 转发到 go_knives_lora.py --character caster
  run_knives_lora_batch.py #   [兼容] 转发到 go_knives_lora.py --count
presets.json               #   用户自定义预设（image + video）
workshop/                  # 创作工坊模块（V0.49+）
  __init__.py               #   包标识
  engine/                   #   Prompt 引擎
  inspect/                  #   质检模块
  manga/                    #   漫画/分镜生成
  video/                    #   视频自动化
workflows/                 # ComfyUI 工作流 JSON（可以从 UI 打开查看节点图）
scripts/                   # 辅助脚本（开发用）
  bootstrap_portfolio.py   #   从本机 DrawingLive 同步 + 生成 SFW 样张
  finalize_portfolio.py    #   [弃用] 仅调用 bootstrap，待删除
  gen_cli_docs.py          #   自动生成 CLI 参考文档
  build_workflows.py       #   程序化构建 API 格式工作流 JSON
docs/                      # 作品展示 + 知识库
  GALLERY.html
  PORTFOLIO.md
  prompt-framework.md      # 六维度构图法 prompt 工程参考
  storyboard-spec.md        # 分镜提示词规范、乒乓镜头、打斗物理化
  cli-reference.md          # CLI 自动生成参考文档
  samples/
  assets/
outputs/                   # 出图产出（gitignored，本地自动生成）
  .gitkeep                 #   占位文件
```

## 技术栈

- **ComfyUI** REST API (`http://127.0.0.1:8188`)
- **Python** 编排（requests + json → POST /prompt → poll /history）
- **Ollama** 可选提示词转写（中文 → 英文 danbooru tag）
- **SDXL / SD1.5 / Flux.2 Klein** 底模支持
- **LoRA** 角色身份保持
- **IPAdapter PLUS FACE** 面部参考一致性

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `COMFY_URL` | `http://127.0.0.1:8188/prompt` | ComfyUI API |
| `COMFY_ROOT` | `C:\DrawingLive\ComfyUI` | ComfyUI 安装目录 |
| `OLLAMA_URL` | `http://127.0.0.1:11434/api/generate` | Ollama API |
| `OLLAMA_MODEL` | `qwen3:14b` | 提示词转写模型 |

## 不做什么

- ❌ 不开在线服务/API for others
- ❌ 不接灵枢
- ❌ 不做 LoRA 训练自动化（用 kohya，本仓库仅编排生图管线）
- ❌ 不碰 AnimateDiff / T2I-Adapter
- ❌ 不包含模型权重（所有 .safetensors / .ckpt 都在本地 `.gitignore` 排除）
- ❌ 不包含成图样张（仅公开展示工作流界面截图）

## 如何工作

所有 agent 脚本遵循同一模式：
1. 加载 workflow JSON（模板）
2. 填入正向/负向提示词、LoRA 名称、seed 等参数
3. POST 到 ComfyUI `/prompt`
4. 轮询 `/history` 等待出图
5. （批量模式）复制到草稿目录或 outputs/

## 统一 CLI

`python -m agents` 提供统一入口，避免记忆多个脚本名：

```bash
# 一句话出图
python -m agents run "夕阳下的赛博朋克少女，半身像"

# 角色 LoRA 文生图
python -m agents lora --character knives "白色连衣裙，海边日落" --count 2

# IPAdapter 锁脸
python -m agents ipa --ref path/to/ref.png "校服，教室窗边"

# 多角色同框
python -m agents multi "Knives校服在左，Caster连衣裙在右，街道背景"

# 产出管理
python -m agents outputs list
python -m agents outputs show 2026-07-12_153022-lora
python -m agents outputs clean --days 30
```

旧脚本入口依然可用，完全向后兼容。

## 产出管理

产出自动保存到 `outputs/YYYY-MM-DD_HHMMSS-<命令>/`：

```
outputs/
  2026-07-12_153022-lora/
    metadata.json     # prompt, seed, 参数, 时间
    images/           # 出图副本
```

metadata.json 包含完整的生成参数，面试时打开即可证明工程化能力。

## 依赖

- `requests>=2.28.0`（核心）
- `pillow`（可选，仅 scripts/bootstrap_portfolio.py 需要）

## 开发约定

- `comfy_utils.py` 是共享工具库，新增脚本要 import 它而非重复代码
- 新增能力时要更新 AGENTS.md 的「核心能力」表
- workflow JSON 放 `workflows/`，同时在 `agents/` 放一份副本让脚本能找到
- 兼容性 wrapper（转发到主力脚本）要加 deprecation warning
- 所有脚本必须支持 `--help`

## Verification Checklist

- [ ] `python agents/run.py` 能调用 ComfyUI 并提交任务
- [ ] `python agents/go_knives_lora.py --help` 显示完整参数
- [ ] `python agents/go_knives_ipadapter.py --help` 显示完整参数
- [ ] `python agents/go_multi_char_lora.py --help` 显示完整参数
- [ ] `python -m agents --help` 显示 6 个子命令（含 check）
- [ ] `python -m agents check` 显示 ComfyUI/Ollama 状态
- [ ] `python -m agents run --dry-run "test"` 使用降级提示词 + 跳过提交
- [ ] `python -m agents lora --dry-run --character knives "test"` 参数可见
- [ ] `python -m agents ipa --dry-run "test"` 参数可见
- [ ] `python -m agents multi --dry-run "test"` 参数可见
- [ ] `python -m agents outputs list` 正常列出（或提示"暂无"）
- [ ] 无 ComfyUI/Ollama 运行不崩溃（自动降级 + warn 提示）
- [ ] 各脚本从任意工作目录运行都能找到 comfy_utils
- [ ] `.gitignore` 正确排除生图输出
- [ ] `from agents.comfy_utils import optimize_prompt` 可导入
- [ ] `docs/prompt-framework.md` 包含六维度构图法完整说明
- [ ] `docs/storyboard-spec.md` 包含八列分镜表、乒乓镜头、打斗物理化规则
- [ ] `python -m agents workflow list` 列出所有 workflow（含 API 格式标识）
- [ ] `python -m agents workflow show <name>` 显示节点连接图
- [ ] `python -m agents workflow schema <name>` 提取可控参数
- [ ] `python -m agents workflow check <name>` ComfyUI 离线时友好提示
- [ ] `python -m agents models list` 按类型分组列出模型
- [ ] `python -m agents models info <name>` 显示模型详情
- [ ] `python -m agents models check <workflow>` 检查模型依赖
- [ ] `python -m agents flux --help` 显示 Flux 完整参数
- [ ] `python -m agents flux --dry-run "test"` 构建 13 节点工作流并跳过提交
- [ ] `python -m agents flux --lora <name> --dry-run "test"` LoRA 注入
- [ ] `python -m agents run --dry-run "test"` dry-run 不归档
- [ ] `python -m agents lora --dry-run "test"` dry-run 不归档
- [ ] `python -m agents flux --dry-run "test"` dry-run 不归档
- [ ] `python -m agents sweep --help` 显示完整参数
- [ ] `python -m agents sweep --grid '{"steps":[20,30]}' --dry-run "test"` 2 组合 + dry-run
- [ ] `python -m agents sweep --grid '{"steps":[20,30],"cfg":[1.0,2.0]}' --dry-run "test"` 4 组合
- [ ] `python -m agents caption --help` 显示完整参数
- [ ] `python -m agents caption --dir <path> --trigger "Test" --dry-run` 预览模式
- [ ] `python -m agents train --help` 显示完整参数
- [ ] `python -m agents train --dir <path> --trigger "Test" --dry-run` 验证报告
- [ ] `python -m agents report` 显示 6 个章节
- [ ] `python -m agents report --json` 输出 JSON 格式
- [ ] `python -m agents queue list` ComfyUI 离线时友好提示
- [ ] `python -m agents queue --help` 显示 4 个子命令
- [ ] `python -m agents models download --help` 显示下载参数
- [ ] `python -m agents models download <url> --type lora --preview` 预览
- [ ] `python -m agents gallery --help` 显示参数
- [ ] `python -m agents gallery --output /tmp/g.html` 生成 HTML
- [ ] `PYTHONPATH=agents python -m pytest tests/ -v` 89 项测试通过
- [ ] `python -m agents workflow convert <name>` ComfyUI 离线时友好提示
- [ ] `python -m agents doctor` 显示 9 项诊断
- [ ] `python -m agents doctor --json` JSON 格式输出
- [ ] `python scripts/gen_cli_docs.py` 生成 `docs/cli-reference.md`
- [ ] `python scripts/build_workflows.py` 生成 6 个 API 格式工作流
- [ ] `python -m agents workflow list` 显示新增工作流为 ✅ API 格式
- [ ] `python -m agents control --help` 显示 6 种 ControlNet 类型
- [ ] `python -m agents control "test" --ref test.png --type depth --dry-run` 跳过提交
- [ ] `python -m agents video --help` 显示视频参数
- [ ] `python -m agents video "test" --frames 25 --dry-run` 跳过提交
- [ ] 无 Ollama 时 `python -m agents flux --dry-run "画个女孩子"` 使用模板兜底
- [ ] `python -m agents validate --image fake.png --prompt "test"` 友好提示
- [ ] `python -m agents abtest --prompts "A" "B" --dry-run` 跳过提交
- [ ] `python -m agents bestof "test" --count 3 --dry-run` 跳过提交
- [ ] `docker build -t aigc-pipeline .` 构建成功
- [ ] `docker run --rm aigc-pipeline --help` 显示帮助
- [ ] `python -m agents flux --preset quality --dry-run "test"` 质量预设
- [ ] `python -m agents flux --raw --dry-run "test" --min-score 0.25 --retry 2` 自动门禁
- [ ] `python -m agents video --preset fast --help` 视频预设帮助
- [ ] `python -m agents video "test" --ref test.png --frames 25 --dry-run` I2V 跳过提交
- [ ] `python -m agents video "test" --denoise 0.85 --timeout 3600 --dry-run` 参数可见
- [ ] `python -m agents flux --preset anime --raw --dry-run "test"` 自定义预设（anime）
- [ ] `python -m agents flux --preset photoreal --raw --dry-run "test"` 自定义预设（photoreal）
- [ ] `python -m agents video --preset quick --raw --dry-run "test"` 自定义视频预设（quick）
- [ ] `presets.json` 可定义任意 QUALITY_PRESETS/VIDEO_PRESETS 覆盖
- [ ] `python -m agents serve --help` API 服务器帮助
- [ ] `python -m agents flux --preset nonexistent --dry-run "test"` 未知预设友好降级
- [ ] `python -m agents gallery` 无产出时友好提示
- [ ] `python -m agents models check video` 显示 Wan2.2 三件套状态
- [ ] `python -m agents models check video` 模型缺失时友好提示
- [ ] `python -m agents models check video` 文件过小时警告损坏风险
- [ ] `python scripts/gen_cli_docs.py` 生成 22 个命令的参考文档
- [ ] `python -m agents models download video --preview` 显示 Wan2.2 三件套路径
- [ ] `python -m agents models download video` 已存在时跳过下载
- [ ] `python -m agents models refresh` 清除缓存并重新扫描
- [ ] `python -m agents models list --no-cache` 跳过缓存扫描磁盘
- [ ] gallery 渲染 .mp4 视频为 `<video>` 标签而非 `<img>`
- [ ] gallery stats 显示 `N videos` 当有视频时
- [ ] `POST /api/video` 返回 job_id + status
- [ ] `POST /api/video` 支持 preset/timeout/denoise/ref 参数
- [ ] `python -m agents queue list` 显示 `🎬 video`/`🖼️ image` 类型标记
- [ ] `python -m agents queue list` 队列为空时友好提示

## 实战策略参考（新增，见 workshop/）

| 文件 | 用途 | 示例命令 |
|------|------|---------|
| `workshop/prompt-tactics.md` | Prompt 工程战术（动漫/写实/视频模板） | `workshop create "1girl, ..." --preset anime` |
| `workshop/character-consistency.md` | 角色一致性（LoRA/seed/ref 三战术） | `workshop train --character "name"` |
| `workshop/workflow-tips.md` | ComfyUI 工作流技巧（节点/放大/面部修复） | 直接用于 C:\DrawingLive\ComfyUI |
| `workshop/comfyui-workflows-reference.md` | 424个网上工作流提取的模型→Prompt→参数映射 | 直接配合 workshop create/video |
| `workshop/video-camera-guide.md` | AI 视频运镜实战 (8种运镜→Wan2.2 Prompt) | `workshop video "camera slowly pushes in..."` |
| `workshop/storyboard-to-video.md` | 分镜→视频全流程 (剧本→逐镜→生成→拼接) | 三步出片流程 |
| `workshop/scene-guide.md` | 9大生图场景实战 (真人/立绘/换装/多人/Cos等) | workshop create 直接套用 |
| `workshop/production_springboot.py` | **高级** Spring Boot 3 生产架构 (Java, 600+行C#风格代码) | 12模块: DI/JPA/JWT/缓存/测试/8条常见坑 |
| `workshop/production_dotnet.py` | **高级** ASP.NET Core 10 生产架构 (C#, 600+行) | 12模块: DI/EF/中间件/JWT/测试/8条常见坑 |
| `workshop/production_fastapi.py` | **高级** 生产级 FastAPI 架构 (1173行) | 分层/DI/Repo/UoW/CQRS/熔断/指标/认证/CRUD全示例 |
| `workshop/scaffold.py` | 项目骨架生成 (cli/fastapi/vue3/fullstack/python-pkg 5种) | `workshop scaffold fastapi myapi` |
| `tools/re/pe-analyzer.py` | PE 文件自动分析 (头/节区/导入表/加壳检测) | `python tools/re/pe-analyzer.py target.exe` |
| `tools/re/frida-script-gen.py` | Frida 脚本生成 (Hook/Trace/Dump/反调试) | `python tools/re/frida-script-gen.py hook CreateFile` |
| `tools/re/api-monitor.py` | API 调用分析 (参数解码/攻击模式检测) | `python tools/re/api-monitor.py decode VirtualAllocEx` |
| `tools/re/game-arch-extract.py` | 游戏资源包识别 (NK/Zip/PAK 等格式鉴定) | `python tools/re/game-arch-extract.py identify file.bin` |
| `tools/re/cheat-toolkit.py` | Cheat Engine 模式辅助 (扫描/监控/指针) | `python tools/re/cheat-toolkit.py modules <pid>` |
| `tools/re/mem_scanner.py` | **高级** 进程内存扫描器 (Pymem+Capstone) | 全维度扫描/RWX检测/特征码搜索/DLL清单 |
| `tools/re/frida_hooker.py` | **高级** Frida自动化工具 (frida Python绑定) | 反调试绕过/API Trace/模块枚举 |
| `tools/re/shellcode_factory.py` | **高级** Shellcode生成器 (MessageBox/WinExec/XOR编码) | 实际可用的x64 shellcode |
| `tools/re/anti_debug_detect.py` | **高级** 反调试检测 (PEB/NtGlobalFlag/INT3/父进程) | 9种反调试技术全检测 |
| `tools/scraping/captcha_solver.py` | 通用验证码破解 (VLM+Playwright+Pillow三引擎) | 文本/滑块/点选/旋转/数学/reCAPTCHA |
| `tools/scraping/scraper_pro.py` | 生产级爬虫框架 (反检测/Cookie持久/重试/截图) | `python scraper_pro.py fetch <url>` |
| `tools/scraping/taobao_auto.py` | 淘宝自动化 (搜索/详情/价格监控/收藏) | `python taobao_auto.py search <keyword>` |
| `tools/testing/production_testing.py` | **高级** 测试架构参考 (15模块) | 金字塔/TDD/Hypothesis/Fake/异步/CI/覆盖率 |
| `tools/testing/demo_test.py` | 测试实战演示 (17用例, 94%覆盖, Hypothesis+AsyncMock) | `pytest tools/testing/demo_test.py -v --cov` |
| `tools/frontend/frontend_expert.py` | **高级** Vue3/TS/CSS 前端参考 (15模块) | 组件模式/状态管理/Pinia/路由/权限/性能/动画/测试 |
| `workshop/creative/aigc_knowledge.py` | 创意知识库 (41服装/17发型/14表情/15姿势/14画风/13分镜/8运镜) | 性别×风格×季节推荐, 可组合原子知识 |
| `workshop/creative/composition_psychology.py` | **构图心理学** (视线动力学/重心/负空间/视角情绪/景别情绪) | 选构图前查——"要什么情绪→选什么构图" |
| `workshop/creative/lighting_system.py` | **光影体系** (光源类型/方向/光色/光比/材质光感) | 生成前定光源三要素→拼 prompt |
| `workshop/creative/color_system.py` | **色彩体系** (色调情绪/配色结构/互补/相似/低饱和/色彩叙事) | 主色60%辅色30%点缀10%——超3色=花 |
| `workshop/creative/face_aesthetics.py` | **面部美学** (瞳孔高光/眼型情绪/眉毛杠杆/表情微差/泪痣) | 眼睛是灵魂——高光是"有神"关键 |
| `workshop/creative/hair_system.py` | **发型体系** (发型×性格/刘海/鬓发/发饰/动态发/发色规范) | 发型=背影认人——黑长直=国民初恋 |
| `workshop/creative/clothing_system.py` | **服装结构** (制服体系/日常/幻想/面料质感/细节) | 服装词要"款式+细节+材质"三层 |
| `workshop/creative/background_system.py` | **背景透视** (透视类型/场景叙事/细节密度/三层纵深) | 背景=氛围担当——前景元素=高级感 |
| `workshop/creative/prompt_system.py` | **Prompt 工程** (结构/权重/质量词/负面库/角色卡/风格词) | SDXL 精确特征必加权——负面=精准控制 |
| `workshop/creative/postprocess_system.py` | **后处理技术** (超分/修脸/调色/锐化/特征后处理/顺序) | 生成→colorgrade→泪痣——顺序已固化 |
| `workshop/creative/delivery_system.py` | **商业交付** (需求解析/系列化/交付规范/审美守门/定价) | 必问五件事→角色卡→系列交付 |
| `workshop/creative/pose_system.py` | **姿势动态** (站/坐/动态/S曲线/姿势×情绪) | 姿势=状态第一信号——一条主曲线不僵硬 |
| `workshop/creative/hand_system.py` | **手部细节** (手势语言/姿势库/安全姿势/手部质检) | 手=最大崩坏点——非必要不露手/露手必具体 |
| `workshop/creative/multichar_system.py` | **多角色构图** (双人关系/空间/互动手势/三人站位) | 分别描述角色+空间关系句——主次分明 |
| `workshop/creative/age_system.py` | **年龄表现** (幼/少/成特征/脸型/服装联动) | 眼型+脸型+服装三一致——年龄立住 |
| `workshop/creative/aura_system.py` | **气质类型** (清纯/元气/文静/御姐/冷淡/病弱/可爱/神秘) | 眼型50%+表情25%+服装15%+姿势10%——四要素同向 |
| `workshop/creative/style_system.py` | **特殊画风** (赛璐璐/厚涂/水彩/吉卜力/新海诚/京阿尼/线稿) | 商业默认赛璐璐——水彩=小说插画友好 |
| `workshop/creative/weather_system.py` | **天气系统** (晴/雨/雪/雾/阴×情绪×光) | 天气=情绪放大器——雨=忧郁/雪=浪漫 |
| `workshop/creative/season_system.py` | **季节表现** (春夏秋冬符号/色板/校园季节化) | 季节色=天然色板——选一季画面自动统一 |
| `workshop/creative/time_system.py` | **时间表现** (晨/午/黄昏/夜/深夜×光色叙事) | 黄昏=商业图默认(最美光)——深夜=情绪重图 |
| `workshop/creative/lens_system.py` | **镜头语言** (景深/焦距/焦点/bokeh) | 人像长焦感(脸不畸变)——商业图80%浅景深 |
| `workshop/creative/relationship_system.py` | **关系叙事** (距离语言/视线语言/接触层级) | 距离=关系刻度·接触点=关系进度条 |
| `workshop/creative/architecture_system.py` | **建筑体系** (和风/欧式/现代/幻想建筑) | 建筑材质词比风格词更让模型"懂" |
| `workshop/creative/prop_system.py` | **道具系统** (手持道具/环境道具/道具叙事) | 道具=第三只手·顺带防手崩 |
| `workshop/creative/animal_system.py` | **动物配饰** (动物×性格/位置互动/兽耳兽尾) | 猫配傲娇/狗配阳光——动物=性格外化 |
| `workshop/creative/pattern_system.py` | **纹样装饰** (蕾丝/花柄/格纹/和风纹样) | 纹样密度=角色华丽度 |
| `workshop/creative/texture_system.py` | **质感细节** (皮肤/金属/布料/液体) | 布料词=真实感10倍 |
| `workshop/creative/motion_system.py` | **动态速度** (速度线/运动模糊/残影/动势线) | 主体清晰+背景模糊=速度 |
| `workshop/creative/composition_advanced.py` | **情绪构图进阶** (S/Z/C形/包围/张力/留白进阶) | 曲线=视觉旅程 |
| `workshop/creative/novel_illustration.py` | **轻小说插画规范** (插画vs封面/叙事选型/系列统一/文字区) | 封面=角色+情绪+留白——朋友场景直接套 |
| `workshop/creative/trend_system.py` | **审美趋势** (大厂设计特征/高级感五要素/避AI味/记忆点) | 现代感=精致+层次+统一 |
| `workshop/creative/visual_guidance.py` | **视觉引导线** (引导线种类/路径节奏/入口出口) | 所有线指向主体=单焦点 |
| `workshop/creative/viewpoint_system.py` | **特殊视角** (透过/镜子/窗户/窥视) | 透过=观众是偷看者 |
| `workshop/creative/anime_studio_styles.py` | **动画流派** (京阿尼/新海诚/吉卜力/新房/骨头社等) | 特征词比公司名更稳 |
| `workshop/creative/growth_arc.py` | **成长弧线** (幼/现在/未来/对比图) | 特征固定段+年龄变化段 |
| `workshop/creative/power_dynamics.py` | **权力构图** (地位差五维/主仆/对峙) | 高+大+前+亮+正=权力 |
| `workshop/creative/lighting_advanced.py` | **光影进阶** (投影/AO/反射/焦散/光效) | AO=角色不悬浮 |
| `workshop/creative/color_psychology.py` | **色彩心理学** (单色情绪表/双色冲突/60-30-10) | 点缀色用互补色=主体自动突出 |
| `workshop/creative/text_layout.py` | **文字排版** (文字位置/图字平衡/标题风格) | 文字区=主体的对立面 |
| `workshop/creative/dream_scene.py` | **梦境幻想** (漂浮/扭曲/光效/经典梦境) | 梦境=日常+超现实处理 |
| `workshop/creative/horror_system.py` | **恐怖暗黑** (恐怖光/构图/色彩/哥特暗黑) | 恐怖=光的异常+看不见 |
| `workshop/creative/intimacy_detail.py` | **互动微细节** (微接触/衣物互动/空间微距) | 指尖相触=最经典暧昧 |
| `workshop/creative/cropping_system.py` | **构图裁切** (裁切位置/延伸感/安全区) | 不裁关节·朝向侧留白60% |
| `workshop/creative/perspective_advanced.py` | **透视进阶** (鱼眼/极广角/微距/变形) | 夸张透视=情绪放大器 |
| `workshop/creative/glow_system.py` | **发光霓虹** (自发光/辉光/霓虹/光效场景) | 小面积辉光=精致/大面积=俗 |
| `workshop/creative/cloth_motion.py` | **服装动态** (布料类型/物理/风向/动态情绪) | 风方向统一=协调 |
| `workshop/creative/chibi_system.py` | **Q版表情** (Q版比例/颜艺/动作/用途) | Q版=放大情绪2倍 |
| `workshop/creative/mythology_system.py` | **神话宗教** (天使/恶魔/神/符号) | 天使=白翼+光环+圣光 |
| `workshop/creative/mecha_system.py` | **机甲机械** (义肢/装甲/细节/风格) | 机械=硬表面+发光线条 |
| `workshop/creative/food_daily.py` | **食物日常** (食物表现/场景/互动/日常细节) | 食物=热气+光泽=温度感 |
| `workshop/creative/worldview_system.py` | **世界观整合** (符号/场景关联/系列节奏/统一性) | 系列=角色卡+风格+光源+色板 |
| `workshop/creative/color_grade.py` | **调色叙事** (电影LUT/分色/对比度曲线) | 青橙=电影·低饱和灰=文艺 |
| `workshop/creative/film_texture.py` | **胶片质感** (颗粒/胶卷色偏/暗角/漏光) | 胶片=时间滤镜 |
| `workshop/creative/art_composition.py` | **纯艺术构图** (几何构成/极简/符号化) | 极简=少即是多 |
| `workshop/creative/job_system.py` | **职业体系** (职业装+道具+场景三件套) | 2件道具认出职业 |
| `workshop/creative/school_life.py` | **校园生活** (教室/走廊/天台/部活/学园祭) | 走廊=相遇离别独处 |
| `workshop/creative/battle_system.py` | **战斗场景** (冲击/姿态/技能特效) | 战斗构图=对角线+速度 |
| `workshop/creative/water_scene.py` | **水场景** (水面/水花/水下) | 水下=光柱+漂浮+气泡 |
| `workshop/creative/sky_scene.py` | **天空飞行** (云表现/飞行/天空时刻) | 云=天气+高度 |
| `workshop/creative/festival_system.py` | **节日庆典** (节日元素/灯饰/人群) | 节日=情感峰值 |
| `workshop/creative/premium_style.py` | **高级感风格** (留白极致/杂志感/性冷淡) | 高级感=克制不是华丽 |
| `workshop/creative/emotion_lighting.py` | **情绪光配方** (告白/告别/治愈/孤独/战斗等 20 配方) | 场景→情绪→直接抄配方 |
| `workshop/creative/info_density.py` | **信息密度** (三档/减法原则/焦点密度) | 删与主题无关的 |
| `workshop/creative/inner_text.py` | **画面内文字** (招牌/标语/印章/AI文字规避) | 可读文字少用(模型写不对) |
| `workshop/creative/traditional_clothes.py` | **传统服饰** (和服/汉服/韩服/洛丽塔) | 和服=袖长定正式度 |
| `workshop/creative/modern_fashion.py` | **现代穿搭** (学院/街头/简约/甜美/OL/休闲) | 换外套=换风格 |
| `workshop/creative/body_type.py` | **体型表现** (纤瘦/丰满/娇小/高挑×气质) | 体型与气质同向 |
| `workshop/creative/rhythm_system.py` | **画面节奏** (点线面/疏密对比/重复变化) | 疏密对比=视觉休息+聚焦 |
| `workshop/creative/outfit_lineup.py` | **换装谱系** (换装逻辑/四类谱系/辨识度保持) | 换装=服装变+特征不变 |
| `workshop/creative/scene_lighting_recipes.py` | **场景光色配方** (校园/城市/自然/室内 16 配方) | 场景+光+色+氛围缺一不可 |
| `workshop/creative/decision_tree.py` | **AI生图决策树** (10 步全流程+实战示例——整合入口) | 需求→成图一次到位 |
| `agents/orchestrator.py` | **核心** ComfyUI 工作流编排器 | 硬件检测 → 多熔炉拆分 → DAG编排 → 并行/串行策略 |
| `agents/go_director.py` | **核心** AIGC 创意导演层 | 需求理解→故事板→创意推荐→编排→评审, 3镜15s视频 |
| `workshop/creative/fashion_depth.py` | **专业级** 深度服装分类 (148条目, 8大类) | 丝袜D数/材质/类型/鞋子跟型/领型/袖型/面料/颜色, 可组合审美推荐 |
| `workshop/creative/character_design.py` | **二次元/动漫/Galgame** 角色设计 (9属性/14动漫服/24发型/11眼型/8定番) | 性格→视觉映射, 动漫服装/发色/瞳色体系, Galgame定番场景 |
| `workshop/creative/background_depth.py` | **深度背景** 知识 (18场景×13景别×12光线) | 校园/都市/自然/幻想/特殊五类, 镜头语言, 跨镜连续性, 情绪变化策略 |
| `agents/go_aesthetic.py` | **核心** VLM 审美评估 Agent | 多维度(构图/色彩/角色/服装/背景/技法)评分, A/B对比, 多轮评审, 时尚细节识别 |
| `agents/go_manga.py` | **核心** 漫画连续性系统 + LLM 语义理解 | 角色卡/场景卡/故事板, qwen3:14b 自然语言→分镜(角色/场景/镜头/情感弧), 批量一致性生成, 4格排版 |
| `agents/workflow_builder.py` | **核心** ComfyUI 工作流自动生成器 | 声明式DAG→API JSON, 4预设模板, 50+节点支持, 连接验证 |
| `workshop/local-workflows-map.md` | 本地 ComfyUI 工作流地图 (18+目录/579文件) | 在 ComfyUI 中 Load 对应 JSON |
| `workshop/commercial_flow.py` | **商业画师标准出图流程** v1 (生成→质检→colorgrade→泪痣→终检 一键) | `workshop commercial_flow "short bob, side braid..." --hair black --tear-mole` |
| `workshop/add_tear_mole.py` | 泪痣后处理 (内眼角小点——精确可控) | `python workshop/add_tear_mole.py <图> --x 0.445 --y 0.40` |

---

## 商业画师标准流程（2026-08-15 实战固化——重要）

**业界商业画师 AI 流程（七步）**：
```
① 生成: SDXL/Flux + --commercial（anime_commercial 风格词）+ --face-detailer 修脸
   + 画风质量词（clean lineart, soft cel shading, smooth gradients, crisp edges——去"脏"）
   + 负向排脏（noise, grainy, dirty, messy lineart）+ 排彩色发（colorful/gradient/blue hair）
② 质检: VLM 六维评分 + 阈值筛选（--min-score 6.5——低于自动重跑）
③ 色彩统一: colorgrade（自动白平衡去脏感）
④ 超分: 2.0x（--commercial 默认）
⑤ 特征后处理: 泪痣/特殊标记——add_tear_mole.py（精确可控——不靠模型乱画）
⑥ 终检: finalcheck --flip --focus（画师终检——倒置/焦点引导）
⑦ 交付: 大图 + 说明
```

**发色规范（用户 2026-08-15 定——中国高中女生现实发色）**：
```
✅ black（纯黑）/ brown（深棕）——现实发色极限
❌ 金/粉/蓝/渐变（"像中专小太妹"——用户原话——禁用）
参考图发色仅作参考——"勉强能接受"的幻想色不主动用
```

**泪痣规范（用户 2026-08-15 定）**：
```
位置: 左眼内眼角下方（x≈0.445, y≈0.40 比例——不是眼下正中）
大小: 小点（r≈0.0022 比例——视觉 2-3px @1000 宽——不过大）
颜色: 深棕黑（55,40,50）——比纯黑自然
```

**画风"脏"根因与修正（实战）**：
```
- Flux 自然语言对精确特征（纯黑发/泪痣）执行弱 → 用 SDXL 标签
- SDXL 直出偏脏 → 画风质量词 + 负向排脏 + face-detailer + colorgrade 组合
- 泪痣/黑发模型画不准 → 后处理画（泪痣=内眼角点 100% 可控）——业界插画后期点泪痣是标准
- VLM 质检"脸崩 3 张人脸"多为 YOLO 误报（动漫脸）——目视/浏览器视觉二次确认
```

**画师流程边缘规则（2026-08-15 细挖第二轮固化）**：

```
【用途→比例映射】
  竖版插画/立绘: 768x1344（全身）· 896x1152（半身）
  横版封面/宣传: 1344x768（B站封面类——cover.py 有标题留白版）
  方图/头像:     896x896 · 特写: 896x896
  双人:          1216x832
  （客户说"要竖版插画"→ 直接按上表选分辨率——不默认）

【表情/情绪词库】（生成时情绪控制——朋友场景"青春感"类）
  青春活泼: cheerful smile, sparkling eyes, blush
  温柔:     gentle smile, soft eyes, serene
  冷淡/疏离: calm expression, distant gaze, composed
  忧郁:     melancholic, downcast eyes, quiet sadness
  元气:     energetic, bright smile, dynamic pose
  神秘:     enigmatic smile, half-lidded eyes
  （情绪词放 prompt 前半——影响整体气质——比"表情细节"权重高）

【光源一致性】（多图同角色/同场景）
  场景卡含光源方向: "warm golden light from right" 多图共用同一句
  参考图氛围: ref 图自带光源——多图共用 ref 或共用光源句
  终检: consistency_check 核对氛围偏差

【后处理顺序确认】
  face-detailer(create 内) → colorgrade → 泪痣(比例自适应——超分后画尺寸按最终分辨率)
  ——修脸改肤色后 colorgrade 统一——顺序已固化在 commercial_flow v1.1

【质检/VLM 降级链】
  YOLO 误报"脸崩"→ 目视二次确认（不直接弃图）
  VLM 全挂 → 图照常交付标注"未质检"（不阻塞流程）
  一致性核对 → consistency_check（VLM 不可用自动跳过）
```

| `~/stock_analyzer/` | 股票分析系统 (analyzer + app + cron + config) | `cd ~/stock_analyzer && uv run python analyzer.py` |
| `~/boss-agent-cli-dev/` | BOSS直聘 CLI (外部项目 v1.15.0, 264测试) | `boss-agent-cli search --keyword "Python"` |
