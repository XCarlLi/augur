<h1 align="center">知 几</h1>

<p align="center">
  <em>A Feishu bot that remembers, thinks, and acts — powered by Claude.</em>
</p>

<p align="center">
  <a href="#快速开始"><img src="https://img.shields.io/badge/Quick_Start-5_MIN-blue?style=flat-square" alt="Quick Start"></a>
  <a href="#特性"><img src="https://img.shields.io/badge/Features-6_Modules-green?style=flat-square" alt="Features"></a>
  <a href="#自主-agent"><img src="https://img.shields.io/badge/Agents-4_Autonomous-orange?style=flat-square" alt="Agents"></a>
  <a href="#配置"><img src="https://img.shields.io/badge/License-MIT-gray?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/claude--code--sdk-latest-6B4FBB?style=flat-square" alt="Claude Code SDK">
  <img src="https://img.shields.io/badge/lark--oapi-latest-4A90D9?style=flat-square" alt="Lark OAPI">
  <img src="https://img.shields.io/badge/memory-file--system-2ECC71?style=flat-square" alt="Memory">
  <img src="https://img.shields.io/badge/output-Feishu_Card-34C759?style=flat-square" alt="Output">
  <img src="https://img.shields.io/badge/Feishu-Bot-4285F4?style=flat-square&logo=bytedance&logoColor=white" alt="Feishu">
</p>

<p align="center">
  <a href="#快速开始">Quick Start</a> · <a href="#架构">Architecture</a> · <a href="#自主-agent">Autonomous Agents</a> · <a href="#配置">Configuration</a>
</p>

---

## 序

> 《周易·系辞下》曰：**「知几其神乎。几者，动之微，吉之先见者也。君子见几而作，不俟终日。」**
>
> *To perceive the incipient is truly divine. The incipient is the subtlest beginning of movement, the first visible sign of what is to come. The noble person perceives it and acts — not waiting for the end of the day.*

「知几」—— 取义于此。不是被动等待指令的工具，而是能观察、能记忆、能自主思考的伙伴。

它会记住你说过的话，沉淀你们共同的发现，在清晨为你整理日程，在午间替你探索世界，在深夜把一天的对话化为日记。你不找它时，它在自己读书、思考；你找它时，它带着对你的了解回应。

---

## 特性

<table>
<tr>
<td width="33%" valign="top">

### 三层记忆

**Identity** — 全量注入：性格、偏好、规则\
**Knowledge** — 索引加载：认知沉淀、月度摘要\
**Journal** — 路径加载：14天日志窗口，旧日志可搜索

记忆按目录结构自动组织，无需手动管理。

</td>
<td width="33%" valign="top">

### Soul 人格系统

四种内置性格模板：\
`balanced` · `friendly` · `efficient` · `professional`

聊天中随时切换。Soul 只影响对话风格，不改变记忆结构或功能行为。

</td>
<td width="33%" valign="top">

### 自主 Agent

四个定时 Agent 在后台运行：

| Agent | 时间 |
|-------|------|
| 晨间摘要 | 每日 08:00 |
| 自主探索 | 09:00 / 12:00 / 18:00 |
| 夜间日记 | 00:05 |
| 月度摘要 | 每月 1 日 |

聊天中发送 `开启探索` / `关闭探索` 即时控制。

</td>
</tr>
</table>

<table>
<tr>
<td width="33%" valign="top">

### 多用户隔离

每个用户独立的记忆空间。用户 A 无法读取用户 B 的数据。首次发消息自动初始化。

</td>
<td width="33%" valign="top">

### 平台解耦

核心逻辑与平台无关。当前适配飞书，未来可扩展钉钉、企业微信 —— 只需新增适配器。

</td>
<td width="33%" valign="top">

### 零外部依赖

调度器基于 `asyncio.call_later()`，记忆用纯文件系统。除 `lark-oapi` 和 `claude-code-sdk` 外无其他依赖。

</td>
</tr>
</table>

---

## 快速开始

**环境要求：** Python 3.12+, [Claude Code SDK](https://docs.anthropic.com/en/docs/claude-code-sdk)

```bash
# 克隆
git clone git@github.com:XCarlLi/augur.git && cd augur

# 安装依赖
pip install -e .

# 交互式配置（引导创建飞书应用、填写凭证）
python -m augur.cli.setup

# 启动
python -m augur
```

首次配置会生成 `config.toml`。如需手动编辑，参见 [配置](#配置) 一节。

---

## 架构

```
                  ┌─── 平台层（可替换） ───┐
                  │                         │
__main__.py ────► feishu.py                 │  将来: dingtalk.py, wecom.py
  │               │  (WebSocket + REST)     │
  │               └─────────────────────────┘
  │
  ├── config.py
  ├── store.py              ┐
  ├── user.py               │
  ├── permissions.py        │  核心层（平台无关）
  ├── memory.py             │
  ├── autonomous.py         │
  ├── scheduler.py          │
  │   └── jobs/*            │
  └── agent.py              │
      └── prompt.py         ┘
```

### 数据目录

```
data/
├── users/{sender_id}/              # 每用户独立
│   ├── identity/                   # Full Load — 每次完整注入
│   │   ├── soul.md                 #   性格定义
│   │   ├── profile.md              #   用户信息
│   │   └── rules/                  #   行为规则
│   ├── knowledge/                  # Index Load — 首行摘要
│   │   ├── insights.md             #   认知积累
│   │   ├── topics/                 #   领域知识沉淀
│   │   └── summaries/              #   月度摘要
│   ├── journal/                    # Path Load — 近 14 天路径
│   │   ├── diary/                  #   每日日记
│   │   └── exploration/            #   探索笔记
│   ├── souls/                      #   多性格切换
│   └── settings.json               #   运行时开关
├── chats/{chat_id}/
│   ├── log.jsonl                   # 对话日志
│   └── scratch/                    # 工作目录
└── templates/souls/                # 默认性格模板
```

### Prompt 构建流

系统提示由两部分拼接 —— 核心层所有平台共用，平台层可替换：

```
┌────────────────────────────────┐
│  Core Prompt（平台无关）        │
│  1. Identity (Full Load)       │
│  2. Active Soul                │
│  3. Knowledge Index            │
│  4. Journal Paths (14d)        │
│  5. Context + Recent Log       │
├────────────────────────────────┤
│  Platform Prompt（可替换）      │
│  · 飞书 CLI 文档               │
│  · 消息格式说明                 │
└────────────────────────────────┘
```

---

## 自主 Agent

知几在无人交互时也在工作。所有 Agent 受限运行：不能修改代码、不能执行危险命令、只能写入指定目录。

| Agent | 职责 | 输出 |
|-------|------|------|
| **晨间摘要** | 拉取飞书日历 + 任务，生成当日提醒 | 发送到 DM |
| **自主探索** | 晨读深度阅读 / 午间时事 / 傍晚自由思考 | 有发现则分享，否则静默 |
| **夜间日记** | 从当日对话生成日记，沉淀重要发现到 `knowledge/topics/` | 静默写入 |
| **月度摘要** | 每月 1 号汇总上月日记和探索 | 写入 `knowledge/summaries/` |

### 知识沉淀模型

```
journal/diary/ (14天窗口)
    │
    ├── 重要发现 ──► knowledge/topics/ (永久索引)
    │
    └── 月度汇总 ──► knowledge/summaries/ (永久索引)
```

日记 Agent 每晚运行时判断：今天有没有值得长期记住的认知变化？有则沉淀，没有则什么都不做。大部分日子什么都不做。

---

## 配置

### config.toml

```toml
[feishu]
app_id = "cli_xxx"
app_secret = "xxx"

[claude]
model = "claude-sonnet-4-5"

[schedule]
timezone = "Asia/Shanghai"
morning_hour = 8
exploration_hours = [9, 12, 18]

[users.ou_xxx]
name = "你的名字"
default_soul = "balanced"
```

### 聊天命令

| 命令 | 效果 |
|------|------|
| `开启探索` / `关闭探索` | 切换自主探索 |
| `开启日记` / `关闭日记` | 切换夜间日记 |
| `开启晨报` / `关闭晨报` | 切换晨间摘要 |
| `状态` | 查看所有开关 |
| `stop` | 中止当前任务 |

---

## 设计哲学

> *Do one thing well.* — Unix Philosophy
>
> *Bad programmers worry about the code. Good programmers worry about data structures and their relationships.* — Linus Torvalds

- **数据结构优先** — 目录名即加载策略（`identity/` = full, `knowledge/` = index, `journal/` = paths）
- **每个文件一个职责** — 全部模块 ≤ 200 行
- **不为未来设计** — 没有 `AbstractFactoryProvider`，只有解决当前问题的最简代码
- **消除特殊情况** — 通过更好的抽象，而非 `if/elif` 堆砌

---

## 许可

MIT
