# RAG 测试文档集

这是用于测试 Agentic RAG 系统的文档集合，包含了 AI 和机器学习领域的核心知识。

## 文档列表

1. **machine_learning.md** - 机器学习基础
   - 监督学习、无监督学习、强化学习
   - 常见算法和应用
   - 挑战和解决方案

2. **deep_learning.md** - 深度学习与神经网络
   - CNN、RNN、Transformer 架构
   - 训练技术和优化方法
   - 框架和突破性应用

3. **natural_language_processing.md** - 自然语言处理
   - 文本处理和分析任务
   - BERT、GPT 等现代模型
   - NLP 应用和挑战

4. **computer_vision.md** - 计算机视觉
   - 图像分类、目标检测、分割
   - 3D 视觉和视频分析
   - 实际应用场景

5. **reinforcement_learning.md** - 强化学习
   - MDP 和基础算法
   - 深度强化学习（DQN、PPO、SAC）
   - 多智能体和实际应用

## 测试用例

### 1. 文档索引测试
```
使用 doc_index 工具索引所有文档到 'ai_knowledge' 集合
```

### 2. 语义搜索测试
```
查询示例：
- "什么是深度学习？"
- "如何训练神经网络？"
- "BERT 和 GPT 的区别"
- "强化学习在游戏中的应用"
```

### 3. 重排序测试
```
搜索 "machine learning algorithms" 并使用 rerank 工具优化结果
```

### 4. 多轮对话测试
```
Agent: 搜索关于 CNN 的信息
Agent: 基于结果，深入了解图像分类
Agent: 比较不同的目标检测算法
```

## 使用方法

1. 启动 DbRheo-CLI Agent
2. 使用 `doc_index` 工具索引文档
3. 使用 `vector_search` 进行语义搜索
4. 使用 `rerank` 优化搜索结果
5. 观察 Agent 如何自主组合使用这些工具

## 预期效果

- Agent 能够理解文档内容并建立索引
- 能够根据语义相似度返回相关内容
- 重排序能够提升结果相关性
- Agent 能够根据需要自主决定使用哪个工具