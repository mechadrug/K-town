# K-town 开发进度

> 当前路线图：`docs/design-master-plan-2026-08-04.md`（修正版主计划，Phase 0–4）
> 版本口径：v0.4（可玩的观察型小镇 + 回合制 + 二十时世界观，2026-08-04）

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
      一次性文档脚本、NUL 损坏的 .gitignore（重写）、修复 run_server.ps1（python main.py）、
      k_town.db 移出 git 跟踪。
- [x] **冒烟测试** `test_smoke.py`：60 tick 全通过（Agent 移动、体力消耗、跨 2 天、
      日报内存+落库、知识产生、无异常）。

### 验证结果（2026-08-04）
- ✅ `python test_smoke.py` → ALL PASS OK
- ✅ `python main.py` 启动 8090；GET / 200；/api/state、/api/history/1、/api/logs/agents/1 全 200
- ✅ 服务器存活 ≥15 tick 无异常；5 地点均有居民；派系生成；知识 100+ 条

### 已知问题 / 下一步（详见设计主计划 Phase 1–4）
- tick.py 仍为单体（约 1960 行），拆分属 P2 后置（勿在闭环稳定前大动）
- 断点恢复需 Agent 状态持久化（当前仅知识/日报/快照落库，Agent 实例不落库；关掉自动重置可保留知识）

---

## v0.4 体验落地（2026-08-04，承接 `docs/plans/2026-08-04-gameplay-plan.md`）

> 玩法设计：`docs/product/gameplay-design-v3.md`（游戏大师视角权威设计）

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
- ✅ `python test_smoke.py` → ALL PASS OK（60 tick，Agent 移动、跨天、日报落库、知识产生、无异常）
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

### 待办（下一步实施，见主计划 Phase 6-9）
- Phase 6 情绪闭环（4 维情绪 + 习惯概率表 + 性格演化）——初心灵魂，优先级最高
- Phase 7 危机事件 + 玩家干预 + 经济修复（NPC 交易/物品用途/价格入决策）
- Phase 8 长期目标线（重建 + 身世碎片）
- Phase 9 UI/美术重构（按 art-direction-v1）
