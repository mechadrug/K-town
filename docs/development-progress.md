# K-town 开发进度

> **当前产品路线（2026-08-23）**：`docs/product/gameplay-design-v5.md` + `docs/product/world-view-v3.md` + `docs/product/art-direction-v2.md`。
> **当前实施计划**：`docs/plans/2026-08-23-rebuild-plan.md`。本文件下方的 v0.3-v0.5 内容是已实现能力和历史记录，不代表下一步继续补 Phase 9。

## v5 设计与 Phase 0-1 实施（2026-08-23 晚）

### 本次完成：路线重构文档 + 动作单一结算 + dry-wood 切片

- [x] 明确产品核心：玩家作为暂住七天的新居民，在有限时段内选择帮助谁、相信什么，小镇在次日用居民行为、关系和场景变化回应。
- [x] 首个可玩目标收敛为 7 天纵切片：托林、莉娜、梅奶奶；广场、工坊、河谷野径；暴雨预告、旧矿道传闻和工坊屋顶三阶段。
- [x] 冻结失忆/玉佩/十三时、随机危机池、复杂生产链、世界自生成、日常 LLM 与多玩家，直到纵切片可玩。
- [x] 设定绘本水彩舞台的美术规范：先做雨天工坊关键场景，再扩展全镇。
- [x] **Phase 0 数据安全**：`server.db_path` / `server.reset_on_start` 显式配置（默认继续游戏）；`test_smoke.py`/`test_actions.py` 用临时库；玩家首屏移除 reset 按钮。
- [x] **Phase 1 动作单一结算**：`actions.py` ActionResolver 统一校验/扣费/推进/日志；修复 move 双扣 AP、advance(0) 免费推进、NPC 动作与 run() 互相喂食导致的世界无限推进；crisis 同日限次干预；dialogue 同地点校验；删除 trigger_event 玩家入口。
- [x] **bring_dry_wood 纵切片**：`requests.py` 莉娜缺干木料（荒野收集 2AP/2h → 工坊交付 1AP/1h）；`/api/requests` + state payload；前端「🙋 请求」tab 渲染与回应；实服验证交付后请求 completed、莉娜关系 +6。

### 代码状态

- [x] `ActionResolver` 已建立并接管所有玩家/NPC 动作；任何新动作/按钮先声明成本再接入。
- [ ] `Agent.perceive()`、事件快照和”观察 → 原因 → 行动 → 后果”日志尚未形成 v5 所需闭环（Phase 2）。
- [ ] 现有每日目标、危机、身世与进度面板尚未按”具体请求 / 今日三条线”重新组织（Phase 4）。
- [ ] 完整 Agent 存档未解决；”继续游戏”为部分恢复（Phase 6）。

### 下一次开发只做

1. Phase 2：`Agent.perceive()` + step 事件快照 + 决策日志”因为 X 所以 Y”日报叙述；剧本测试（雨天×人格、知识传播×路线）。
2. Phase 3：扩展托林工坊屋顶、梅奶奶镇志两条请求线，补请求状态机与次日后果。
3. 每个请求选项都要有对象、成本、即时反馈和次日观察，再接前端按钮。

## v0.2.1 → v0.3 基底重构（2026-08-04）

### 审计结论（承接设计主计划 §0）
原 v0.2.1 并非"功能完善"：核心缺陷是**决策结果从不执行**（`_handle_action` 零调用点）、
**数据层 4 套并存互相冲突**（tick 10 写库即崩、tick 24 日报即崩）、**前端入口 GBK 编码 500**、
**前端-后端协议失配**。模拟从未成功跨天（DB 中 day_summaries=0 行）。

### 本次完成（Phase 0 落地）
- [x] **统一持久层** `storage.py`：单一 sqlite 连接、权威 DDL、schema 版本检测自动重建，
      取代 db.py / database.py / logger.py / static_db.py 四套；main/tick/api 共享同一实例。
- [x] **接通决策→执行链**：`step()` 在 `decide()` 后调用 `_handle_action(agent, action, tick)`；
      玩家动作同样走此管线。修复其未定义变量 `tick`、缺失方法、假知识传播等 bug。
- [x] **Agent 生活节奏**：新增"傍晚广场聚集/社交"决策层，小镇有真实每日空间节律（移动可见）。
- [x] **Agent 接口补全**：`to_dict()` 含 goals/diary/personality/location_cn/role_cn；新增 `get_location_cn`。
- [x] **api.py 修复**：状态载荷收敛为 `_build_state_payload()`（消除 3 处重复）；
      `/api/history`、`/api/logs/agents` 不再 500；玩家动作支持 work/rest/add_claim/reset/talk。
- [x] **前端修复**：`index-v2.html` 由 GBK 转 UTF-8（GET / 不再 500）；`app-v2.js` 协议对齐
      （move→target）、对话接线真实 `/api/dialogue/*`、档案目标/日记真实渲染；
      `animations-v2.css` 未闭合注释修复、`style-v2.css` 补 `--bg-card`。
- [x] **清理**：删除 client/（Godot）、server/（Go）、v1 前端六件套、9 个孤儿/一次性模块、
      一次性文档脚本、NUL 损坏的 .gitignore（重写）、修复 run_server.ps1（固定解释器启动 main.py）、
      k_town.db 移出 git 跟踪。
- [x] **冒烟测试** `test_smoke.py`：60 tick 全通过（Agent 移动、体力消耗、跨 2 天、
      日报内存+落库、知识产生、无异常）。

### 验证结果（2026-08-04）
- ✅ 使用项目解释器运行 `test_smoke.py` → ALL PASS OK
- ✅ 使用项目解释器运行 `main.py` 启动 8090；GET / 200；/api/state、/api/history/1、/api/logs/agents/1 全 200
- ✅ 服务器存活 ≥15 tick 无异常；5 地点均有居民；派系生成；知识 100+ 条

### 已知问题 / 下一步（详见设计主计划 Phase 1–4）
- tick.py 仍为单体（约 1960 行），拆分属 P2 后置（勿在闭环稳定前大动）
- 断点恢复需 Agent 状态持久化（当前仅知识/日报/快照落库，Agent 实例不落库；关掉自动重置可保留知识）

---

## v0.4 体验落地（历史记录，2026-08-04，承接 `docs/plans/2026-08-04-gameplay-plan.md`）

> 历史玩法设计：`docs/product/gameplay-design-v3.md`。当前玩法基线见 `docs/product/gameplay-design-v5.md`。

### 板块 1–4（P0，提交 74bc46c / d7bc8aa / 1564f8d / 624d3bc）
- [x] **F0.1 图标系统统一**：新增 `static/icons.js` 单一 emoji 来源，清空全部 `?` 占位符（含 town-map 注释乱码与 JS BOM）
- [x] **F0.2 Tab 显示修复**：`switchTab` 显式驱动 `style.display`（原内联 `display:none` 覆盖 `.active`），初始化即加载任务/知识
- [x] **F0.3 对话系统重设计**：话题由「性格×心情×正在做的事×关系」生成；选项按好感门控；后果=双向好感/情绪梯度/知识交换，入日报
- [x] **F0.4 交互模型**：点居民=看档案（含当前活动/心情），对话=唯一动作；对话头部显示关系等级与心情
- [x] **F0.5 小镇脉搏首屏**：侧栏第一块改为小镇脉搏（此刻各处/心情分布/正在流传/你在哪），玩家数值收敛到顶栏
- [x] **F0.6 每日目标薄层**：重写 quests.py，每天 3 目标（真实动作池），进度挂 `_handle_action` 实时推进，完成即发奖励
- [x] **F0.7 知识流动视图**：知识 Tab 按主题聚类，展示 来自谁→传到谁→置信度→冲突/固化

### P1 深化（提交 6368806）
- [x] **F1.3 Agent 日记**：日结按当天行为写日记，档案"最近日记"可见（12/12 Agent 实测）
- [x] **F1.1 关系后果化**：decide 社交层好友优先交谈、宿敌在场回避
- [x] **F1.2 食物经济闭环**：采集计供给、日结按饥饿计需求、食物贵则更卖力采集；实测价格 [5,2,10] 随供需波动
- [x] **F1.4 事件链**：补调度商人来访/动物袭击/神秘陌生人/小镇集会/金色发现；修复潜伏的 `Event` 导入 bug

### P2 取舍（提交 68f8364）
- [x] **F2.1 移除死系统**：删除 narrative.py / town_evolution.py（含 NameError bug）/ achievements.py；
      保留已接线的 factions 与作为 Phase 2 定价积木的 trade.py
- [x] **F2.2 知识持久化**：knowledge.py 写穿钩子 + `load_from_db` 断点恢复；storage 补 `get_knowledge_pool`；实测往返 2 条正确
- [ ] **F2.3 tick.py 拆分**：后置（详见设计主计划 P2）

### v0.4 验证
- ✅ 使用项目解释器运行 `test_smoke.py` → ALL PASS OK（60 tick，Agent 移动、跨天、日报落库、知识产生、无异常）
- ✅ 实服 8090：GET / 200；/api/state（factions/无 era 残留）、/api/quests、/api/knowledge、/api/dialogue/options 全 200 无错误日志

### 世界观与回合制改造（板块 6-7，提交 feb1cc4 / c196f2e）
- [x] **20 小时世界观**：几十万年后地球转速变慢 → 一天 20 小时（清醒 12h + 睡眠 8h），清晨 5 点醒来；
      全链适配（agent 作息 6-14 工作 / 14-17 傍晚 / 17-5 夜；world 价格更新；events 日程；前端昼夜/时段/日数；地图月相）
- [x] **回合制**：1 AP = 1 小时，玩家行动驱动世界推进（advance + wait_caught_up）；
      「休息」= 睡觉结束今天，跳到次日清晨、AP 重置；夜晚拦截行动与对话
- [x] **知识驱动发展**：劳作精进技能（技能提升产出）；小镇重建——居民攒钱逐级修缮破旧建筑（Lv1→5，阈值平方增长）
- [x] **世界观 lore**：world-view-v2 补充"末世重建"玩家伏笔

### 玩家体验修复（板块 5，提交 5e6a61b，承接实机反馈）
- [x] **修复移动无效**：玩家脱离 NPC 自主循环（不再被 `decide()` 拉回工作地）；AP 不足时动作拦截并返回错误 toast
- [x] **对话入口去重**：移除与档案重复的右下角聊天按钮；对话唯一入口 = 点居民 → 档案 → 对话
- [x] **按钮意义**：全部动作按钮加 `title` 悬停说明
- [x] **新手引导**：复用已写未接线的 `.guide-*` 样式，首访弹出 4 步引导；顶栏 ❓ 可重开
- [x] **对比度**：`--text-muted` 加深（#A1887F→#795548），白色背景文字可读

---

## 设计定稿（2026-08-06）：世界自生成（远期支柱）

- [x] **世界自生成设计**：`docs/product/world-self-generation.md`（玩家命题：NPC 按自己的意志触发游戏资产设计，item 维度无限大）
      —— 结论：**可行**。核心洞察「资产原型 = 带结构化参数的可执行知识」，复用知识引擎的社会共识机制；
      反失控设计（创作成本 + 社会共识门槛 + 失传/考古生命周期）；**Phase 0–4 顺序不变**，
      master plan 增补 Phase 5；P1 资产数据化（纯重构）可与 Phase 2 并行铺垫

---

## 设计重构 v0.5 起步（2026-08-20）：游戏感三件套 + 仓库清理

> 背景：用户回顾初心（2025-04 博客：有自我意识的小镇、性格、**心情值系统**、因行为而学习改变），
> 判定 v0.4"可玩的观察型小镇"缺**游戏感**：情绪无闭环（初心灵魂缺失）、事件只能旁观、无长期目标、界面无生活感。

### 产出（本次文档 + 清理）
- [x] **gameplay-design-v4.md**（取代 v3）：三支柱 + 游戏感三件套
      —— 情绪闭环（4 维情绪×性格偏移→决策渗透→情绪记忆→习惯→性格演化，近似 RL 规则表）、
      危机干预（灾害/疫病/谣言/资源危机，四干预→结局分支）、长期目标线（重建弧线 + 身世之谜接线）。
- [x] **art-direction-v1.md**：美术方向成文（水彩软化像素、地图道路/像素小人/建筑细节、动效接入、死 CSS 清理）。
- [x] **路线图 Phase 6-9**：v0.5a 情绪闭环 / v0.5b 危机干预+经济修复 / v0.5c 长期目标线 / v0.5d UI 美术重构。
- [x] **仓库清理**：删 15 个根目录一次性脚本（check_cliches/fix_*/verify*/final_check/find_exact）+ k_town.db + __pycache__；
      docs/archive/2026-08-20/ 归档 vision.md / world-v0.1.md / report_260528_001.md（加状态横幅）；
      世界观五篇入库；知识固化阈值统一 0.85（knowledge-system 原 0.9 修正）。
- [x] **CLAUDE.md 同步**：仓库布局更新（v4/art-direction/世界观/archive）、仓库卫生规则（一次性脚本不入库）。

> 说明：当前分支里，Phase 9 已经开始落地：`static/town-map-v2.js` 里已加手绘土路与像素小人，`templates/index-v2.html` 里已加危机横幅和目标 Tab；剩余仍是纹理、天气/粒子接入、建筑窗光和死 CSS 清理。

### 待办（下一步实施，见主计划 Phase 6-9）
- [x] Phase 6 情绪闭环（4 维情绪 + 习惯概率表 + 性格演化）
- [x] Phase 7 危机事件 + 玩家干预 + 经济修复
- [x] Phase 8 长期目标线（重建 + 身世碎片）
- [ ] Phase 9 UI/美术重构（道路/像素小人/目标页签已落地；待补动效、噪点、数据展示和清理）

---

## v0.5 实施：游戏感三件套（2026-08-20，Phase 6-8 落地）

### Phase 6 情绪闭环（初心灵魂，emotions.py）
- [x] 4 维情绪（愉悦/焦虑/愤怒/悲伤 0-100）取代单一 Mood 5 档，主导情绪驱动 UI 表情
- [x] 事件×性格→情绪偏移（被批评：敏感者悲伤×1.8，大大咧咧×0.5——初心核心）
- [x] 情绪→决策渗透（焦虑→避险调查、愉悦→社交、愤怒→冲突/效率、悲伤→独处）
- [x] 情绪记忆→习惯形成（情境→行为→概率表，近似 RL：行为→反馈→概率更新）
- [x] 习惯固化→性格慢速演化（同情境同行为累计 7 次触发，敏感者改变更剧烈）
- [x] 情绪传染沿关系网（好友>陌生人，稳定高者抗传染）
- [x] 玩家情绪只由自身行动反馈驱动（不被 NPC 生理逻辑拖拽）
- [x] 平衡：情绪回归速率 8%-15%/tick，避免 30 天全员情绪爆表
- 验证：test_emotions.py 16/16；30 天模拟情绪健康分层（低稳定者更易焦虑/悲伤）

### Phase 7 危机事件与玩家干预（crisis.py）
- [x] 4 危机：暴风雨/疫病/谣言风暴/食物短缺，带倒计时与进度条
- [x] NPC 性格化反应矩阵（尽责者组织/敏感者恐慌/亲善者帮忙/内向者隔离/自私者囤积）
- [x] 玩家四干预（帮忙3AP/调查2AP/澄清1AP/旁观0AP），澄清对谣言×1.5、帮忙对灾害×1.2
- [x] 结局分支：达标→缓解（关系↑愉悦↑），未达标→恶化（受伤/焦虑↑/关系↓）
- [x] 无人干预时 NPC 自救（性格反应推进进度）——小镇能自己面对危机
- [x] 触发概率 12%/天；60 天模拟 8 次危机 5 缓解 3 恶化（玩家旁观时小镇可自愈）
- [x] 经济修复：NPC 当场响应玩家交易（发起即判断，市价合理接受/高价拒绝）
- 验证：test_crisis.py 20/20

### Phase 8 长期目标线
- [x] 身世之谜：每日思考触及真相关键词 → 收集记忆碎片（5 片：遗迹/石碑/十三/玉佩/大缓变），集齐解锁"大缓变不是天灾"真相
- [x] 重建弧线：/api/progress 暴露修缮进度（已修缮/阈值/金币/等级）
- [x] state payload 新增 progress 字段（rebuild + lore）
- 验证：test_progress.py 10/10

### 待办
- [ ] Phase 9 UI/美术重构（art-direction-v1.md）：补齐四维情绪/危机/身世进度展示、动效接入和死 CSS 清理

---

## 2026-08-23 运行与交接补充

### 正确启动

```powershell
.\run_server.ps1
```

启动脚本固定使用 Conda `python_class`，自动结束占用 8090 的上一实例，并等待 `GET /api/state` 返回 200。不要用裸 `python`；本机裸命令会命中损坏的 base 解释器并触发 `0xc0000022`。

### 已验证

- `test_crisis.py`：20/20
- `test_emotions.py`：16/16
- `test_progress.py`：10/10（Windows 控制台需 UTF-8 输出）
- Python `compileall`、`static/town-map-v2.js` 语法检查通过
- 首页、静态资源、`/api/state`、`/api/crises`、`/api/progress` 返回 200

### 当前改进优先级

1. 持久化：将 `auto_reset=True` 改为显式配置，恢复 world snapshot 与完整 Agent 状态。
2. 测试：让 `test_smoke.py` 接受独立数据库路径，避免覆盖运行中的 `k_town.db`。
3. UI：展示四维情绪、危机细节和 lore/rebuild 进度，完成天气/粒子、夜间窗光、纸面纹理与死 CSS 清理。
4. 架构与平衡：稳定行为后拆分 `tick.py`，再做长期模拟和情绪/危机/修缮参数调优。
