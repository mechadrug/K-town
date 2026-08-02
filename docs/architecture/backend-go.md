# 后端：Go 服务器

**版本**: v0.1
**最后更新**: 2026-08-02

## 1. 服务边界

Go 服务器是单一二进制，内部模块清晰分离：

| 模块 | 职责 |
|------|------|
| cmd/server | 入口、配置加载、优雅关闭 |
| internal/tick | Tick 循环引擎 |
| internal/world | 世界状态、地点、资源、调度事件 |
| internal/agent | Agent 状态机、决策逻辑 |
| internal/knowledge | KnowledgeClaim CRUD、传播、质疑 |
| internal/event | 事件总线（发布/订阅） |
| internal/api | WebSocket + HTTP 处理器 |
| internal/log | 事件/决策/知识日志 |
| internal/llm | LLM 客户端封装 |

## 2. 核心数据结构

### 世界状态
世界包含时间、天气、地点和资源。每个地点有类型、在场 Agent 和进行中事件。

### Agent
Agent 包含身份、状态、记忆、知识库、目标列表和日程。生命周期为：感知 -> 思考 -> 行动。

### 知识引擎
处理创建声明、传播声明、质疑声明和固化声明的逻辑。

### 事件总线
管理按地点的订阅/发布和调度事件。

## 3. API 层

**WebSocket 端点**：/ws
- 服务端 -> 客户端：StateDelta 消息（Agent 移动、新事件、声明创建）
- 客户端 -> 服务端：PlayerAction 消息（移动、互动、引入声明）

**HTTP 端点**：
- GET /api/state - 完整世界状态（初始加载）
- GET /api/agents/:id - Agent 详情
- GET /api/timeline?day=N - 指定日期的事件时间线
- POST /api/player/action - 提交玩家动作

## 4. 依赖包

| 包 | 用途 |
|-----|------|
| gorilla/websocket | WebSocket 支持 |
| gin 或 net/http | HTTP 服务器 |
| lib/pq 或 pgx | PostgreSQL 驱动 |
| go-redis | Redis 客户端 |
| sashabaranov/go-openai | OpenAI 兼容 LLM 客户端 |
| google/uuid | UUID 生成 |
| sirupsen/logrus 或 zerolog | 结构化日志 |

## 5. v0.1 简化

- 无数据库：所有状态在内存
- 无 Redis：事件总线是进程内通道
- 无向量数据库：声明按 ID/地点查询
- LLM 调用模拟或在功能标志后（无需 API 费用即可开发）
