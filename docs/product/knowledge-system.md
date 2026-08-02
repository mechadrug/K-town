# 知识系统

**版本**: v0.1
**最后更新**: 2026-08-02

## 1. 核心概念

K-town 中的知识不是原始聊天记录。它是结构化的、演化的、社会传播的小镇知识通过智能体行为增长和变化——它永远不会被开发者一次性写死。

## 2. KnowledgeClaim 结构

KnowledgeClaim 包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string (UUID) | 唯一标识 |
| subject | string | 主体（如"森林边缘"、"老井"） |
| claim | string | 声明内容（如"晚上有狼出没"） |
| source | ClaimSource | 来源：观察、对话、推理、谣言、玩家 |
| confidence | float64 | 置信度 0.0-1.0 |
| scope | ClaimScope | 范围：私有、群体、公开 |
| createdAt | int64 | 创建 tick |
| createdBy | string | 创建者 Agent ID |
| location | string | 知识形成地点 |
| contradictedBy | string[] | 矛盾声明 ID 列表 |
| solidified | bool | 是否已固化为"小镇百科" |
| version | int | 版本号（修正时递增） |

## 3. 知识生命周期

### 3.1 观察
Agent 直接感知事件并创建新 KnowledgeClaim：
- source = observation
- confidence = 0.7-0.9（直接观察相当可靠）
- scope = private

### 3.2 总结
Agent 拥有多个相关声明时（如三次观察到狼踪迹），可以合成高层声明：
- source = reasoning
- confidence = 源平均值 * 0.9（轻微衰减）
- 原始声明链接为证据。

### 3.3 传播
两个 Agent 对话时交换声明：
- 说话者分享 scope != private 或关系紧密的声明。
- 听众接收声明时 confidence = 说话者置信度 * 关系强度 * 0.8。
- source 变为 conversation 或 rumor（取决于说话者置信度）。

### 3.4 质疑
Agent 接收到与已有知识矛盾的声明时：
- 如果新声明置信度更高：降低旧声明置信度。
- 如果置信度相近：两个声明都标记为 contradictedBy。
- Agent 可能寻求更多证据。

### 3.5 修正
强证据反驳现有声明时：
- 旧声明置信度降低。
- 新声明创建，version = old.version + 1。
- 旧声明的 contradictedBy 更新。

### 3.6 固化
声明达到高置信度（如 > 0.85）且被多个 Agent 持有时：
- 可固化为小镇常识。
- 固化声明出现在小镇广场公告板上。
- 固化声明更难被反驳（需要更强反证）。

## 4. 谣言机制

谣言是 source = rumor 且 confidence < 0.5 的声明：
- 比事实传播更快（Agent 喜欢八卦）。
- 每次转述时声明文本略微变异。
- 置信度随跳数递减，除非被验证。
- 传到谨慎性格 Agent 处可能被阻断。

## 5. 玩家与知识

- 玩家可以引入新声明（如"我在森林里看到了什么"）。
- 玩家声明 source = player，confidence = 0.6。
- Agent 根据自身性格和与玩家的关系相信、怀疑或调查玩家声明。
