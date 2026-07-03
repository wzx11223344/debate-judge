# DebateJudge — 结构化政策辩论系统

**一个严格的经济学辩论引擎，具有正式裁决机制。**

 DebateJudge **不是**"两个AI互相争论"的玩具。它是一个严肃的研究工具，
 用于在经济学框架内进行结构化的政策辩论，具有人格化的辩手、多维评分标准、
 谬误检测和完整的记录系统。

---

## 核心理念

> 每个辩手人格都不是政治漫画式的夸张，而是代表一种具有自身假设、价值优先级和修辞规范的**合法经济学传统**。

系统通过让两种不同的经济学思想流派就具体政策问题进行正式辩论，由第三方裁判进行公正裁决，帮助研究者和决策者理解复杂政策议题的多维视角。

## 这不是什么

- 两个聊天机器人自由发挥的"辩论"
- 没有结构、没有约束的随意对话
- 政治立场的简单二元对抗
- 仅关注谁更"能说会道"

## 这是什么

- 具有正式辩论格式的严谨结构（开场陈述 -> 交叉质询 -> 反驳 -> 总结陈词 -> 裁决）
- 基于经济学传统的辩手人格（新古典、制度、行为、公共选择、凯恩斯、奥地利、马克思、能力方法）
- 包含谬误检测和证据质量评估的六维评分标准
- 支持 Markdown 和 HTML 双格式输出的完整辩论记录
- 三种辩论格式：政策辩论、学术研讨会、快速交锋

---

## 架构

```
debate-judge/
├── README.md
├── requirements.txt
├── debate_judge/
│   ├── __init__.py           # 公共 API
│   ├── arena.py              # 辩论编排引擎 (DebateArena)
│   ├── agents.py             # 辩手人格 + 裁判代理
│   ├── formats.py            # 辩论格式定义 (3种内置格式)
│   ├── scoring.py            # 评分标准 + 谬误检测 + 证据评估
│   └── transcript.py         # 辩论记录 + Markdown/HTML 输出
├── config/
│   └── personas.yaml         # 预置辩手和裁判人格库 (8+3)
├── examples/
│   ├── minimum_wage.py       # 最低工资辩论示例
│   └── carbon_pricing.py     # 碳定价机制辩论示例
└── tests/
    └── test_debate.py        # 完整单元测试 (30+ 测试)
```

### 组件说明

| 模块 | 功能 |
|------|------|
| `arena.py` | 辩论编排引擎，管理完整辩论生命周期，强制执行格式和轮次 |
| `agents.py` | `DebaterAgent` (基于经济学流派的辩手) + `JudgeAgent` (公正裁判) |
| `formats.py` | 三种辩论格式 + 可序列化的格式定义 + 注册机制 |
| `scoring.py` | 六维度评分标准、7种谬误检测模式、证据质量评估 |
| `transcript.py` | 结构化记录、Markdown/HTML 导出、关键节点提取、关键词搜索 |

---

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

默认使用本地 Ollama (http://localhost:11434/v1, model="qwen2.5:7b")。
也可以配置为使用任何 OpenAI 兼容的 API。

### 运行示例辩论

```bash
# 最低工资政策辩论
python examples/minimum_wage.py

# 碳定价机制辩论 (学术研讨会格式)
python examples/carbon_pricing.py
```

### 编程使用

```python
from debate_judge import DebateArena, Persona, JudgePersona, AgentConfig

# 配置 LLM
config = AgentConfig(
    model="qwen2.5:7b",
    api_base="http://localhost:11434/v1",
    api_key="ollama",
)

# 定义辩手人格
institutional = Persona(
    name="制度经济学家",
    school="Institutional",
    key_assumptions=["制度塑造激励", "路径依赖", "有限理性"],
    value_priorities=["公平", "制度质量", "分配效应"],
    rhetorical_style="历史比较、案例分析",
    constraints=["必须提供制度案例", "必须讨论转型成本"],
)

neoclassical = Persona(
    name="新古典经济学家",
    school="Neoclassical",
    key_assumptions=["理性主体", "市场效率", "价格信号"],
    value_priorities=["效率", "增长", "消费者福利"],
    rhetorical_style="量化、模型驱动、均衡分析",
    constraints=["必须引用经济机制", "必须承认市场失灵"],
)

# 创建辩论
arena = DebateArena(
    topic="联邦最低工资应提高至每小时15美元并随通胀指数化",
    debater_a_persona=institutional,   # 正方
    debater_b_persona=neoclassical,    # 反方
    format="standard",                 # 政策辩论格式
    config=config,
)

# 运行辩论
result = arena.run()

# 保存记录
arena.save_transcript("debate_result.md", format="markdown")
arena.save_transcript("debate_result.html", format="html")

print(f"胜方: {result['winner_name']}")
print(f"分差: {result['margin']}")
```

---

## 辩论格式

### 政策辩论 (Policy Debate) — 默认

| 轮次 | 发言方 | 内容 | 时限 |
|------|--------|------|------|
| 1 | 正方 | 开场陈述 | ~5分钟 |
| 2 | 反方 | 开场陈述 | ~5分钟 |
| 3 | 正方 | 交叉质询反方 | ~3分钟 |
| 4 | 反方 | 质询答辩 | ~3分钟 |
| 5 | 正方 | 反驳 | ~4分钟 |
| 6 | 反方 | 交叉质询正方 | ~3分钟 |
| 7 | 正方 | 质询答辩 | ~3分钟 |
| 8 | 反方 | 反驳 | ~4分钟 |
| 9 | 正方 | 总结陈词 | ~3分钟 |
| 10 | 反方 | 总结陈词 | ~3分钟 |
| 11 | 裁判 | 最终裁决 | — |

### 学术研讨会 (Academic Seminar)

适用于复杂理论讨论：立场论文 -> 同行评审 -> 修订 -> 小组讨论 -> 共识声明 -> 裁决

### 快速交锋 (Rapid Fire)

适用于快速观点碰撞：1分钟开场 -> 6轮30秒交锋 -> 1分钟总结 -> 即时裁决

---

## 评分系统

六维度评分，每项 0-10 分，加权计算：

| 维度 | 权重 | 说明 |
|------|------|------|
| 实证基础 (empirical_grounding) | 25% | 证据质量和引用 |
| 逻辑一致性 (logical_coherence) | 20% | 内部逻辑、无谬误 |
| 回应反方 (counterargument_addressing) | 20% | 如何处理反对意见 |
| 政策可行性 (policy_feasibility) | 15% | 现实可操作性 |
| 价值表述 (value_articulation) | 10% | 规范基础的清晰性 |
| 修辞效果 (rhetorical_effectiveness) | 10% | 说服力和表达清晰度 |

### 谬误检测

系统自动检测 7 种常见逻辑谬误：
- **人身攻击** (ad hominem)
- **稻草人** (straw man)
- **虚假二分** (false dichotomy)
- **诉诸权威** (appeal to authority)
- **滑坡谬误** (slippery slope)
- **诉诸情感** (appeal to emotion)
- **窃取论点** (begging the question)

### 证据质量评估

自动评估论证中的证据强度，区分：
- **强证据**：RCT、自然实验、DID、元分析、弹性估计、NBER/CBO 引用
- **弱证据**：常识断言、轶事推理、"显然"、"众所周知"

---

## 辩手人格库

`config/personas.yaml` 包含 8 种经济学流派人格 + 3 种裁判人格：

| 流派 | 核心假设 | 价值优先级 |
|------|----------|------------|
| 新古典 (Neoclassical) | 理性主体、市场效率、价格信号 | 效率、增长、消费者福利 |
| 制度 (Institutional) | 制度塑造激励、路径依赖、有限理性 | 公平、制度质量、分配 |
| 行为 (Behavioral) | 认知偏差、助推、参考依赖 | 福利、选择架构、证据为本 |
| 公共选择 (Public Choice) | 政府失灵、寻租、集中利益分散成本 | 自由、宪政约束、激励相容 |
| 凯恩斯 (Keynesian) | 总需求不足、价格粘性、不确定性 | 充分就业、宏观稳定、逆周期 |
| 奥地利 (Austrian) | 市场是发现过程、知识分散、资本异质 | 自由、自发秩序、企业家发现 |
| 马克思 (Marxist) | 资本积累驱动、阶级关系、内源性危机 | 劳动者福利、去商品化、民主管理 |
| 能力方法 (Capabilities) | 发展是自由扩展、多维福祉、转换因素 | 能力、能动性、参与 |

---

## 输出格式

### Markdown
完整的辩论记录，包含所有发言、评分和裁决，适合存档和分享。

### HTML
带样式的交互式页面，包括：
- 颜色编码的发言人（绿色=正方，红色=反方，金色=裁判）
- 可折叠的轮次区域
- 评分卡片和逐轮对比表
- 关键节点高亮

---

## 运行测试

```bash
python -m pytest tests/test_debate.py -v
```

测试覆盖：
- 评分标准的正确性
- 谬误检测的准确性
- 格式定义的序列化
- 人格加载和系统提示生成
- 记录生成和导出
- 编排引擎的集成测试

---

## 配置

### 使用其他 LLM

```python
config = AgentConfig(
    model="gpt-4o",
    temperature=0.7,
    api_base="https://api.openai.com/v1",
    api_key="sk-your-key",
)
```

### 自定义辩论格式

```python
from debate_judge.formats import DebateFormat, Turn

custom = DebateFormat(
    name="快速研讨",
    description="简化版研讨会辩论",
    turns=[
        Turn("a", "opening", "开场陈述", token_limit=500),
        Turn("b", "opening", "开场陈述", token_limit=500),
        Turn("a", "rebuttal", "反驳", token_limit=400),
        Turn("b", "rebuttal", "反驳", token_limit=400),
        Turn("a", "closing", "总结", token_limit=300),
        Turn("b", "closing", "总结", token_limit=300),
    ],
)

arena = DebateArena(topic="...", format=custom)  # 不推荐: format 需要 str
# 使用方法：保存到文件后使用 get_format() 加载
```

---

## 许可

MIT License
