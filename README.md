<p align="center">
  <img src="assets/logo.png" width="120" alt="知几">
</p>

<h1 align="center">知 几</h1>

<p align="center">
  <em>A Feishu bot that remembers, thinks, and acts — powered by Claude.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/claude--code--sdk-latest-6B4FBB?style=flat-square" alt="Claude Code SDK">
  <img src="https://img.shields.io/badge/lark--oapi-latest-4A90D9?style=flat-square" alt="Lark OAPI">
  <img src="https://img.shields.io/badge/memory-file--system-2ECC71?style=flat-square" alt="Memory">
  <img src="https://img.shields.io/badge/Feishu-Bot-4285F4?style=flat-square&logo=bytedance&logoColor=white" alt="Feishu">
</p>

<p align="center">
  <a href="#快速开始">Quick Start</a> · <a href="#架构">Architecture</a> · <a href="#自主-agent">Autonomous Agents</a> · <a href="#配置">Configuration</a>
</p>

---

## 序

> 《周易·系辞下》曰：**「知几其神乎。几者，动之微，吉之先见者也。君子见几而作，不俟终日。」**
>

「知几」—— 取义于此。每个人和 AI 的对话都不一样。知几从你们的日常交流中生长出来——你聊什么它就记什么，你关心什么它就了解什么。用得越久，它就越是你的，而不是别人的。足够了解一个人之后，很多事不必等人开口。

---


## 快速开始

**环境要求：** Python 3.12+

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

## 许可

Copyright 2026 XCarlLi

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

> http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
