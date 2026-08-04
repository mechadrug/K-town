# K-town 系统架构设计

## 1. 整体架构
K-town采用客户端-服务器架构：
- **服务端**：Python + FastAPI，负责模拟逻辑、数据存储、API提供
- **客户端**：Web前端（HTML/CSS/JS），负责展示和用户交互
- **通信方式**：REST API + WebSocket实时推送

## 2. 服务端模块划分
### 2.1 入口层（main.py）
- 负责初始化所有模块
- 启动Tick引擎和HTTP服务器
- 管理WebSocket连接

### 2.2 配置模块（config.py）
- 加载YAML配置文件
- 管理所有可配置参数

### 2.3 数据模型（models.py）
- 定义所有数据类：KnowledgeClaim, Agent, WorldState等
- 提供序列化和反序列化方法

### 2.4 世界模块（world.py）
- 管理世界状态：天气、地点、资源分布
- 处理天气变化、资源刷新等世界事件

### 2.5 Agent模块（agent.py）
- 实现Agent的感知、思考、决策、行动逻辑
- 管理Agent的状态、记忆、目标、知识

### 2.6 事件模块（events.py）
- 实现事件总线，处理事件的发布和订阅
- 实现事件调度器，生成日常和随机事件

### 2.7 知识模块（knowledge.py）
- 实现知识引擎，管理所有知识条目
- 处理知识的创建、传播、质疑、修正、固化

### 2.8 数据访问层（storage.py）
- 唯一 SQLite 数据访问层（单一连接、权威 DDL、schema 版本自动重建）
- 统一承载日志（世界事件/Agent决策/知识变化）、每日摘要、世界快照、知识池持久化

### 2.9 LLM模块（llm.py）
- 封装LLM调用接口（Anthropic 兼容，mock 兜底）
- 用于关键场景的辅助决策（每日限次 + 缓存）

### 2.10 Tick引擎（tick.py）
- 驱动整个模拟循环（回合制：1 AP = 1 小时）
- 每个 Tick 更新世界状态、处理事件、驱动Agent行动
- 生成每日摘要，保存历史数据

### 2.11 API模块（api.py）
- 提供REST API接口
- 提供WebSocket实时推送接口

### 2.12 任务/对话/派系（quests.py / dialogue.py / factions.py）
- 每日目标薄层、语境化对话系统、派系聚类

## 3. 数据流
1. Tick引擎驱动每个模拟周期
2. 世界模块更新天气、资源等状态
3. 事件模块生成新事件，发布到事件总线
4. Agent模块处理事件，更新Agent状态
5. 知识模块处理知识变化
6. 日志模块记录所有变化
7. API模块通过WebSocket推送更新到前端
8. 数据库模块定期保存快照

## 4. 技术栈
- **Python 3.11+**：核心开发语言
- **FastAPI**：HTTP服务器框架
- **Uvicorn**：ASGI服务器
- **SQLite**：嵌入式数据库
- **PyYAML**：配置文件解析
- **aiohttp**：HTTP客户端，用于LLM调用
