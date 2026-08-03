# K-town 知识自进化系统设计

## 1. 知识数据结构
知识以`KnowledgeClaim`的形式存储，包含以下字段：
```python
@dataclass
class KnowledgeClaim:
    id: str  # 唯一标识
    subject: str  # 知识主题
    claim: str  # 知识内容
    source: ClaimSource  # 来源：观察/对话/推理/传闻/玩家
    confidence: float  # 置信度：0.2-1.0
    scope: ClaimScope  # 可见范围：私有/群体/公共
    created_by: str  # 创建者ID
    location: str  # 发现地点
    created_at: float  # 创建时间
    contradicted_by: List[str]  # 反驳该知识的知识ID列表
    solidified: bool  # 是否已固化为公共知识
    version: int  # 版本号，每次更新+1
```

## 2. 知识操作流程
### 2.1 观察
- Agent通过观察环境事件获得新知识
- 初始置信度为0.6，来源为observation
- 可见范围为私有

### 2.2 总结
- Agent可以将多个相关的短期记忆总结为稳定的知识
- 总结后的知识置信度提升0.1，最高1.0
- 需要调用LLM进行总结（v0.1阶段可用规则引擎替代）

### 2.3 传播
- Agent之间通过社交互动传播知识
- 传播后的知识置信度乘以0.8（信息衰减）
- 接收者可以根据自己的判断选择接受或拒绝

### 2.4 质疑
- Agent发现冲突的知识时，会降低冲突知识的置信度
- 创建新的知识条目作为反证，confidence初始为0.7
- 如果反证的confidence高于原知识，原知识会被标记为矛盾

### 2.5 修正
- Agent可以用新的证据更新旧的知识
- 更新后版本号+1，confidence提升0.1
- 所有引用该知识的Agent会收到更新通知

### 2.6 固化
- 公共知识的confidence达到0.9以上，且被至少5个Agent接受，会被固化为小镇公共知识
- 固化的知识会被记录到小镇档案馆，所有Agent可以查询
- 固化的知识不可再修改，只能被新的知识反驳

## 3. 知识冲突解决
当两个知识条目冲突时：
1. 比较两个知识的confidence，高的胜出
2. 如果confidence相同，比较版本号，新的胜出
3. 如果都相同，比较支持该知识的Agent数量，多的胜出
4. 失败的知识的confidence降低0.2

## 4. 知识分类（v0.1阶段）
- **地理知识**：关于小镇地图、地点、资源分布的知识
- **技能知识**：关于工作技巧、制作方法的知识
- **社会知识**：关于其他Agent、人际关系的知识
- **传闻**：未经证实的信息，confidence普遍低于0.6
