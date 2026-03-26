---
title: Agent Skill 设计模式
parent: AI Capriccio
nav_order: 2
---

# Agent Skill 设计模式

> 基于 Google ADK SkillToolset 的 5 个模式，补充 5 个系统架构模式
> 
> 参考：[Google ADK 文档](https://google.github.io/adk-docs/) | [Multi-agent Design Patterns](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/)

---

## 一、Skill 设计模式（Google）

Google 在 ADK SkillToolset 中提炼了 5 个 Skill 设计模式，聚焦于"Skill 怎么设计"：

### Tool Wrapper

将外部库/API 封装为可调用的 Skill。

```
外部能力（API、SDK、数据库）
        ↓
   Tool Wrapper
        ↓
  标准化 Skill 接口
```

### Generator

基于模板生成结构化输出，保证输出可解析、可执行。

```python
# 输入：自然语言需求
# 输出：结构化 JSON/YAML
{
  "action": "create_issue",
  "project": "OKX",
  "title": "...",
  "assignee": "..."
}
```

### Reviewer

对输出进行标准评估与校验，形成质量闭环。

```
生成内容 → Reviewer 评估 → 通过/打回修改
```

### Inversion

先澄清需求再行动（Interview Before Acting）。

```
用户："帮我订机票"
Agent："去哪？什么时间？几个人？"  ← 先问清楚
Agent：执行订票
```

### Pipeline

多步骤工作流编排。

```
Step 1 → Step 2 → Step 3 → 输出
           ↓
        条件分支
```

---

## 二、系统架构模式（补充）

当从"单 Agent + 几个 Tool"走向"Agent 平台"时，需要考虑以下架构模式，聚焦于"Skill 系统怎么搭"：

### Just-in-time Loading

按需加载 Skill，避免上下文膨胀。

**问题**：100 个 Skill 的说明全塞进 context，token 爆炸。

**解决**：分层加载，用到哪个再加载详细说明。

```
❌ 启动时加载所有 Skill 完整说明
✅ 三层加载：
   - 第一层：名字 + 描述（始终在 context）
   - 第二层：SKILL.md 正文（触发时加载）
   - 第三层：references/（需要时再读）
```

**示例**：Claude 的 Skill 系统就是这样设计的。

---

### Skill Composition

多个 Skill 组合，完成复杂能力。

**问题**：单个 Skill 能力有限，复杂任务做不了。

**解决**：多个专注型 Skill 组合完成复杂流程。

```
"生成周报" = 
  1. Jira Skill      → 拉本周完成的 issue
  2. GitHub Skill    → 拉本周 PR
  3. Generator Skill → 生成 markdown 报告
  4. Lark Skill      → 发送到群

每个 Skill 专注一件事，组合起来完成复杂流程
```

---

### Orchestrator

Agent 只负责调度与路由，不直接实现能力。

**问题**：Agent 和 Skill 耦合太紧，难以扩展。

**解决**：Agent 是调度员，不是执行者。

```
❌ Agent prompt 里写死："你会查天气、订机票、发邮件..."
✅ Agent 只知道"我可以调用 Skills"，具体能力由 Skill 提供

流程：
1. Agent 收到"帮我订明天去上海的机票"
2. Agent 不知道怎么订，但知道有个 flight_booking Skill
3. Agent 调用 Skill，Skill 返回结果
4. Agent 整合结果回复用户
```

---

### Separation of Concerns

能力、决策、数据解耦。

**问题**：一个大 Skill 里又有 API 调用、又有业务逻辑、又有数据处理，难以维护。

**解决**：分层设计，各司其职。

```
以交易复盘系统为例：

┌─────────────────────────────────────┐
│  输出层 Skill    生成报告/图表       │
├─────────────────────────────────────┤
│  决策层 Skill    根据指标给建议      │
├─────────────────────────────────────┤
│  计算层 Skill    算胜率、盈亏比      │
├─────────────────────────────────────┤
│  数据层 Skill    从 OKX 拉交易记录   │
└─────────────────────────────────────┘

好处：每层可以独立测试、复用、替换
```

---

### Registry Pattern

能力归属于系统注册表，Agent 按需查询与调用。

**问题**：多 Agent 场景下，每个 Agent 自己维护一套 Skill 列表，管理混乱。

**解决**：中心化 Registry，所有 Agent 共享。

```
SkillRegistry
├── okx_trading    (v1.2.0)
├── lark_notify    (v2.0.1)  
├── jira_query     (v1.0.0)
└── ...

Agent A ──┐
Agent B ──┼── 从 Registry 查询和调用
Agent C ──┘
```

**好处**：

- 新增 Skill：只需注册一次，所有 Agent 都能用
- 升级 Skill：Registry 里更新，所有 Agent 自动生效
- 权限控制：Registry 层面控制谁能调什么

---

## 三、模式对比

| 类别 | 模式 | 聚焦 |
|------|------|------|
| Skill 设计 | Tool Wrapper | 封装外部能力 |
| Skill 设计 | Generator | 结构化输出 |
| Skill 设计 | Reviewer | 质量校验 |
| Skill 设计 | Inversion | 先问再做 |
| Skill 设计 | Pipeline | 流程编排 |
| 系统架构 | Just-in-time Loading | 按需加载 |
| 系统架构 | Skill Composition | 能力组合 |
| 系统架构 | Orchestrator | 调度解耦 |
| 系统架构 | Separation of Concerns | 分层设计 |
| 系统架构 | Registry Pattern | 中心注册 |

---

## 四、总结

- **Google 的 5 个模式**：聚焦单个 Skill 的设计，回答"Skill 怎么写"
- **补充的 5 个模式**：聚焦 Skill 系统的架构，回答"Skill 平台怎么搭"

当你从"单 Agent + 几个 Tool"走向"Agent 平台"时，后 5 个模式是必须考虑的架构问题。
