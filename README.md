# K-town 多智能体小镇模拟器

## 项目简介
K-town 是一个多智能体小镇模拟游戏。居民有自己的感知、记忆、关系、情绪和目标，会在玩家不干预时继续生活；玩家不是镇长，而是一位会被小镇记住的普通居民。

当前 Demo 已从七天纵切片扩展为四周篇章：玩家在有限时段里决定帮助谁、相信什么、把时间留给哪里；居民会自主行动，章节选择会留下场景标记并在后续周次回响。详见 `docs/product/gameplay-design-v6.md`。

## 核心特性
- 🤖 **12个智能Agent**：每个Agent有独立的身份、状态、记忆、目标、知识系统，包括铁匠、木匠、采集者、侦察兵、商人、教师、农民、讲故事的人、医生、矿工、长者和旅行者（玩家）
- 🌍 **动态世界**：5个地点（广场、工坊、荒野、学校、矿洞），天气变化、资源分布、事件生成，世界会随时间自主进化
- 📚 **知识自进化**：知识可以创建、传播、质疑、修正、固化，支持冲突检测、版本管理、搜索查询，形成小镇专属的知识库
- 📊 **实时监控**：网页控制台实时查看小镇状态、Agent行为、每日摘要、知识库、交易列表
- 🎮 **玩家交互**：玩家可以移动、添加知识、回应居民请求、调查公共压力、干预危机、和其他 Agent 对话、发起和接受交易
- ⏪ **历史回放**：支持查看任意日期的小镇历史，回放发展过程
- 💾 **数据层**：历史数据由 SQLite 统一管理；版本化存档包含世界、居民、知识、请求、章节状态、事件队列和 RNG
- 🎉 **丰富事件**：天气影响、资源价格变化、社交关系变化、节日、灾害、目标完成等多种事件类型

## 技术栈
- **后端**：Python 3.11+、FastAPI、Uvicorn
- **前端**：HTML5、CSS3、JavaScript、WebSocket
- **数据库**：SQLite
- **LLM支持**：可集成LongCat等LLM服务，用于知识生成和决策

## 快速开始
### 环境要求
- Conda 环境 `python_class`
- Python 3.11.14（已验证）
- `E:\anaconda\envs\python_class\python.exe`

### 安装依赖
```powershell
& "E:\anaconda\envs\python_class\python.exe" -m pip install -r requirements.txt
```

### 运行服务
```powershell
.\run_server.ps1
```

启动脚本会自动结束占用 8090 的上一份 K-town 服务，并固定使用 Conda 环境 `python_class`。
如果 PowerShell 禁止执行脚本，可使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_server.ps1
```

不使用启动脚本时，必须显式调用正确的解释器：

```powershell
& "E:\anaconda\envs\python_class\python.exe" main.py
```

### 访问控制台
浏览器打开 http://localhost:8090 即可访问小镇模拟器控制台

### 运行注意事项

- 不要使用裸命令 `python`。本机它会解析到 Conda base 的 `E:\anaconda\python.exe`，并可能弹出 `python.exe - Application Error (0xc0000022)`。
- `run_server.ps1` 每次会结束占用 8090 的上一份 K-town 服务；日志在 `logs/server.log` 与 `logs/server.err.log`。
- 启动模式由 `config.yaml` 的 `server.reset_on_start` 控制：默认 `false` 会继续版本化存档，设为 `true` 才会开始新游戏并清空受管表。不要在服务运行时执行会重置数据库的测试。
- LLM 密钥优先通过环境变量 `LLM_API_KEY` 提供；`config.yaml` 是本地忽略文件，不要提交或公开其中的密钥。

### 当前状态与后续改进

当前已完成四周 Demo 的核心闭环和交付验收：第 1–4 周章节、请求分支、因果回信、次日后果、今日三条线、版本化存档、确定性回放，以及桌面/移动端/reduced-motion 浏览器回归均已通过。

后续工作是可选的长期平衡调优和架构演进：参数调整需附固定 seed 回放证据；只有在继续扩展系统前，才评估拆分 `tick.py`。

当前权威文档：`docs/product/gameplay-design-v6.md`、`docs/product/gameplay-design-v5.md`、`docs/product/world-view-v3.md`、`docs/product/art-direction-v2.md`、`docs/plans/2026-08-25-multiweek-demo-plan.md`。

## 项目结构
```
K-town/
├── main.py                # 服务入口
├── models.py              # 数据模型和枚举（Agent、知识、事件、交易等）
├── world.py               # 世界状态管理（地点、天气、资源）
├── agent.py               # Agent系统（行为逻辑、目标系统、记忆系统）
├── events.py              # 事件系统（事件总线、调度器、22种事件类型）
├── knowledge.py           # 知识引擎（创建、传播、质疑、修正、固化、搜索）
├── tick.py                # Tick循环引擎（回合制：1AP=1小时，模拟循环、每日摘要）
├── storage.py             # ★唯一数据访问层（SQLite，单一连接/权威DDL）
├── quests.py              # 每日目标薄层
├── dialogue.py            # 对话系统
├── factions.py            # 派系
├── api.py                 # REST API和WebSocket接口
├── config.py / config.yaml# 配置
├── test_smoke.py          # 冒烟测试
├── templates/
│   └── index-v2.html      # 前端控制台（分层地图界面）
├── docs/
│   ├── product/           # 产品设计文档（PRD、世界观、Agent模型、知识系统）
│   ├── architecture/      # 架构设计文档（总体架构、后端、前端、日志）
│   ├── plans/             # 开发计划
│   ├── development-progress.md # 开发进度
│   └── handoff.md         # 交接记录
└── requirements.txt       # 依赖列表
```

## 配置说明
编辑config.yaml文件可以配置：
- 服务端口（默认8090）
- LLM服务地址和密钥
- Tick速度（回合制：1 AP = 度过 1 小时）
- 世界设定（一天 20 小时，清晨 5 点醒来，清醒 12 小时）
- Agent数量（默认12个）

## 主要API接口
- `GET /api/state`：获取当前世界状态、Agent状态、玩家状态、知识统计、交易列表
- `GET /api/knowledge`：获取所有知识列表
- `GET /api/knowledge/public`：获取所有公共知识
- `GET /api/knowledge/search`：按主题、位置、创建者搜索知识
- `GET /api/knowledge/{claim_id}`：获取指定知识的详细信息（包括版本历史、冲突列表）
- `POST /api/knowledge/solidify/{claim_id}`：手动固化知识
- `GET /api/agents/{agent_id}`：获取指定Agent的详细信息（包括知识列表）
- `GET /api/days`：获取所有每日摘要
- `GET /api/day/{day}`：获取指定日期的每日摘要
- `GET /api/history/{day}`：获取指定日期的完整历史（摘要、日志、快照、事件）
- `GET /api/replay?start_day=1&end_day=5`：获取指定时间范围的历史数据用于回放
- `GET /api/logs/player`：获取玩家操作日志
- `POST /api/player/action`：执行玩家操作（移动、工作/调查、添加知识、回应请求、对话、交易）
- `GET /api/requests`：获取居民请求、选项、成本和状态
- `GET /api/today-threads`：获取首屏今日三条线
- `GET /api/campaign`：获取当前章节、周次、评分、旗标和结局
- `GET /api/crises` / `POST /api/crisis/{id}/intervene`：查看和干预活动危机
- `POST /api/reset`：重置模拟，清空所有数据
- `WS /ws`：WebSocket实时推送状态更新、每日摘要、事件通知

## 当前代码的玩家操作
1. **移动**：底部动作栏选地点，切到该地点的分层界面（消耗1行动力，过1小时）
2. **工作/调查**：在当前地点劳作赚钱 / 调查发现线索（调查耗2行动力）
3. **交谈**：点地图上的人 → 档案 → 「对话」，建立关系、交换知识
4. **每日思考**：每天一次「知识」写下想法，若触及遗迹真相会有领悟
5. **休息**：睡觉结束今天，跳到次日清晨，行动力重置
6. **十三时**：每过13天多1点夜间行动力（🌙），夜深人静时出门能看见别人看不见的东西

## 当前 Demo 与后续计划
- 四周章节：雨前的七天、河水改道、灯火与账本、归灯集；第 29 天生成组合结局
- 前端扩展边界：`state-contract-v2.js`、`api-client-v2.js`、`campaign-view-v2.js` 与 `data-app-action` 事件委托
- 持续完善浏览器回归、章节平衡和可读性；新增内容先遵守 `docs/architecture/frontend-v2.md`
- 四周 Demo 稳定后，再评估世界自生成、更多地点、LLM 日常行为和多玩家

## 贡献指南
欢迎提交Issue和Pull Request，共同完善K-town项目。

## 许可证
MIT License
