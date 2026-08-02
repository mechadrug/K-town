# K-town

一个多智能体小镇模拟游戏。居民是独立的 AI 智能体，拥有持久记忆、知识、目标和社会关系。

## v0.1 功能

- 2D 小镇地图（广场、工坊、荒野）
- 10 个 AI 智能体，各有角色、日程和目标
- 5 种事件类型（天气、资源、社交、制作、谣言）
- 知识系统：观察 → 传播 → 质疑 → 固化
- 玩家可以进入小镇并影响事件
- WebSocket 实时同步 + HTTP API
- 日志与回放系统

## 技术栈

| 层 | 技术 |
|----|------|
| 服务端 | Go 1.21+ (tick 循环, 事件总线, Agent 状态机) |
| 客户端 | Godot 4.x GDScript (2D 渲染, WebSocket) |
| LLM | LongCat-2.0 (OpenAI 兼容 API) |

## 快速开始

### 服务端

` + "`powershell`" + `
# 安装依赖
go mod tidy

# 运行（默认 tick 率 1s）
go run cmd/server

# 构建
go build -o ktown-server cmd/server
` + "`" + `

配置 ` + "`config.yaml`" + `：

` + "`yaml`" + `
llm:
  base_url: https://api.longcat.chat/anthropic
  api_key: your_key_here
  model: LongCat-2.0
` + "`" + `

### 客户端

1. 打开 Godot 4.x
2. 导入 ` + "`client/project.godot`" + `
3. 运行 Main 场景

## 项目结构

` + "`" + `
K-town/
├── cmd/server          # Go 入口
├── internal/           # Go 模块
│   ├── config/         # 配置加载
│   ├── world/          # 世界状态
│   ├── event/          # 事件总线
│   ├── agent/          # Agent 系统
│   ├── knowledge/      # 知识引擎
│   ├── log/            # 日志系统
│   ├── api/            # HTTP/WebSocket API
│   ├── tick/           # Tick 循环
│   └── llm/            # LLM 客户端
├── client/             # Godot 客户端
│   ├── scenes/         # 场景文件
│   └── scripts/        # GDScript
├── docs/               # 文档
│   ├── product/        # 产品设计
│   ├── architecture/   # 架构设计
│   └── plans/          # 实施计划
└── config.yaml         # 配置文件（本地）
` + "`" + `

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| WS | /ws | WebSocket 实时同步 |
| GET | /api/state | 完整世界状态 |
| GET | /api/agents/:id | Agent 详情 |
| GET | /api/timeline?day=N | 事件时间线 |
| POST | /api/player/action | 玩家动作 |

## 许可证

MIT