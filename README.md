# K-town 多智能体小镇模拟器

## 项目简介
K-town 是一个多智能体小镇模拟游戏，开发者只设定世界规则、资源、初始人物和事件种子；小镇居民通过感知、记忆、交互、学习、传播知识和创造物品，逐渐形成自己的社会结构。玩家既可以旁观，也可以作为真人居民进入其中，和agent共同改变世界。

## 核心特性
- 🤖 **10+智能Agent**：每个Agent有独立的身份、状态、记忆、目标、知识系统
- 🌍 **动态世界**：天气变化、资源分布、事件生成，世界会随时间自主进化
- 📚 **知识自进化**：知识可以创建、传播、质疑、修正、固化，形成小镇专属的知识库
- 📊 **实时监控**：网页控制台实时查看小镇状态、Agent行为、每日摘要
- ⏪ **历史回放**：支持查看任意日期的小镇历史，回放发展过程
- 💾 **数据持久化**：所有历史数据保存到SQLite，重启后数据不丢失

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
├── models.py              # 数据模型和枚举
├── world.py               # 世界状态管理
├── agent.py               # Agent系统
├── events.py              # 事件系统
├── knowledge.py           # 知识引擎
├── tick.py                # Tick循环引擎
├── api.py                 # REST API和WebSocket
├── config.py              # 配置加载
├── config.yaml            # 配置文件
├── db.py                  # 数据库持久化
├── logger.py              # 日志系统
├── templates/
│   └── index.html         # 前端控制台
├── docs/
│   ├── product/           # 产品设计文档
│   ├── architecture/      # 架构设计文档
│   ├── plans/             # 开发计划
│   ├── development-progress.md # 开发进度
│   └── handoff.md         # 交接记录
└── requirements.txt       # 依赖列表
```

## 配置说明
编辑config.yaml文件可以配置：
- 服务端口
- LLM服务地址和密钥
- Tick速度
- 世界设定
- Agent数量

## 后续计划
- 添加更多职业和地点
- 集成LLM生成更复杂的知识
- 完善历史回放功能
- 优化性能，支持更多Agent同时运行

## 贡献指南
欢迎提交Issue和Pull Request，共同完善K-town项目。

## 许可证
MIT License
