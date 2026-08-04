# K-town 多智能体小镇模拟器

## 项目简介
K-town 是一个多智能体小镇模拟游戏，开发者只设定世界规则、资源、初始人物和事件种子；小镇居民通过感知、记忆、交互、学习、传播知识和创造物品，逐渐形成自己的社会结构。玩家既可以旁观，也可以作为真人居民进入其中，和agent共同改变世界。

## 核心特性
- 🤖 **12个智能Agent**：每个Agent有独立的身份、状态、记忆、目标、知识系统，包括铁匠、木匠、采集者、侦察兵、商人、教师、农民、讲故事的人、医生、矿工、长者和旅行者（玩家）
- 🌍 **动态世界**：5个地点（广场、工坊、荒野、学校、矿洞），天气变化、资源分布、事件生成，世界会随时间自主进化
- 📚 **知识自进化**：知识可以创建、传播、质疑、修正、固化，支持冲突检测、版本管理、搜索查询，形成小镇专属的知识库
- 📊 **实时监控**：网页控制台实时查看小镇状态、Agent行为、每日摘要、知识库、交易列表
- 🎮 **玩家交互**：玩家可以移动、添加知识、触发事件、和其他Agent对话、发起和接受交易
- ⏪ **历史回放**：支持查看任意日期的小镇历史，回放发展过程
- 💾 **数据持久化**：所有历史数据保存到SQLite，重启后数据不丢失，支持自动重置
- 🎉 **丰富事件**：天气影响、资源价格变化、社交关系变化、节日、灾害、目标完成等多种事件类型

## 技术栈
- **后端**：Python 3.11+、FastAPI、Uvicorn
- **前端**：HTML5、CSS3、JavaScript、WebSocket
- **数据库**：SQLite
- **LLM支持**：可集成LongCat等LLM服务，用于知识生成和决策

## 快速开始
### 环境要求
- Python 3.11+
- pip包管理器

### 安装依赖
```powershell
pip install -r requirements.txt
```

### 运行服务
```powershell
python main.py
```

### 访问控制台
浏览器打开 http://localhost:8090 即可访问小镇模拟器控制台

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
- `POST /api/player/action`：执行玩家操作（移动、添加知识、触发事件、对话、交易）
- `POST /api/reset`：重置模拟，清空所有数据
- `WS /ws`：WebSocket实时推送状态更新、每日摘要、事件通知

## 玩家操作说明（回合制）
1. **移动**：底部动作栏选地点，切到该地点的分层界面（消耗1行动力，过1小时）
2. **工作/调查**：在当前地点劳作赚钱 / 调查发现线索（调查耗2行动力）
3. **交谈**：点地图上的人 → 档案 → 「对话」，建立关系、交换知识
4. **每日思考**：每天一次「知识」写下想法，若触及遗迹真相会有领悟
5. **休息**：睡觉结束今天，跳到次日清晨，行动力重置
6. **十三时**：每过13天多1点夜间行动力（🌙），夜深人静时出门能看见别人看不见的东西

## 后续计划
- 集成LLM生成更复杂的知识总结和对话内容
- 添加更多职业和地点
- 优化性能，支持更多Agent同时运行
- 完善回放功能，支持可视化回放界面
- 添加多玩家支持，多个玩家可以同时参与模拟

## 贡献指南
欢迎提交Issue和Pull Request，共同完善K-town项目。

## 许可证
MIT License
