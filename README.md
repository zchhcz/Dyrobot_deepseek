# 🤖 dyrobot - 抖音群聊 AI 聊天机器人

基于 Playwright 浏览器自动化 + DeepSeek 大语言模型的**抖音网页版群聊 AI 机器人**。支持多角色切换、技能系统、对话上下文管理，提供 CLI 和 PyQt6 GUI 两种运行模式。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-orange.svg)](https://platform.deepseek.com)

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🤖 **AI 聊天** | 基于 DeepSeek API 的智能对话，支持上下文记忆 |
| 🎭 **角色系统** | 内置多种预设人设（雪之下雪乃、比企谷八幡、张雪峰等），可自定义角色，运行时随时切换 |
| 🔧 **技能系统** | 关键词触发的专业提示词注入，支持 YAML 和 Claude Code SKILL.md 格式 |
| 📊 **GUI 控制面板** | PyQt6 深色主题可视化界面，包含仪表盘、日志、角色、技能、设置五个页面 |
| 💬 **群聊命令** | 群内直接发送命令控制机器人：切换角色、查看技能、重置上下文等 |
| 🌐 **多群支持** | 同时监控多个抖音群聊 |
| 🔒 **登录管理** | 扫码登录 + Cookie 持久化，首次扫码后自动保持登录 |

---

## 📦 快速开始

### 1. 环境要求

- Python 3.10+
- Chrome/Chromium 浏览器（Playwright 自动管理）
- DeepSeek API Key ([获取地址](https://platform.deepseek.com))

### 2. 安装依赖

```bash
# 克隆项目
git clone <your-repo-url>
cd dyrobot

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
python -m playwright install chromium
```

### 3. 配置

复制配置模板并编辑：

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入必填项：

```yaml
deepseek:
  api_key: "sk-xxxxxxxxxxxxxxxx"   # 填入你的 DeepSeek API Key

groups:
  - name: "技术交流群"
    url: "https://www.douyin.com/chat?isPopup=1"  # 群聊页面完整 URL
```

**获取群聊 URL**: 打开抖音网页版，进入目标群聊，复制浏览器地址栏的完整 URL。

### 4. 运行

```bash
# CLI 模式（终端运行）
python main.py

# GUI 模式（可视化控制面板）
python main.py --gui

# 使用自定义配置文件
python main.py --config prod.yaml
```

首次运行会弹出浏览器窗口，用抖音 App 扫码登录。登录状态自动保存，下次启动无需重复扫码。

---

## 🎭 角色系统

机器人支持多种预设角色，每个角色有独立的人设、性格和说话风格。

### 预设角色

| 角色 | 文件 | 说明 |
|------|------|------|
| 小助手 | `default.yaml` | 默认友好助手，简洁自然 |
| 雪之下雪乃 | `yukino.yaml` | 《我的青春恋爱物语果然有问题》角色 |
| 比企谷八幡 | `hachiman.yaml` | 《我的青春恋爱物语果然有问题》角色 |
| 张雪峰 | `张雪峰.yaml` | 考研名师视角的教育/职业规划顾问 |

### 触发方式

在群聊中 **@角色名** 即可触发该角色回复：

```
@小助手 今天天气怎么样？
@雪之下雪乃 你觉得这个问题怎么看？
@张雪峰 我孩子要填志愿了，该怎么选专业？
```

### 切换角色

```bash
# 群聊命令
<System>:character list              # 查看所有可用角色
<System>:character 张雪峰            # 切换为张雪峰
```

### 自定义角色

在 `characters/` 目录下创建新的 `.yaml` 文件：

```yaml
name: "我的角色"
description: "简短描述"
personality: "性格特点"
background: "角色背景故事"
speaking_style: "说话风格"
system_prompt: |
  完整的系统提示词内容...
bound_skills:       # 可选：绑定的技能列表
  - skill_name
```

---

## 🔧 技能系统

技能是预定义的提示词模板，当用户消息匹配关键词时自动激活。

### 预设技能

| 技能 | 触发词示例 |
|------|-----------|
| 天气查询 | 天气、气温、下雨、穿什么 |
| 翻译服务 | 翻译、英文、怎么说 |
| 编程帮助 | 代码、编程、bug、报错 |

### 创建技能

在 `skills/` 目录下创建 `.yaml` 文件：

```yaml
name: "my_skill"
description: "技能描述"
triggers:
  - "关键词1"
  - "关键词2"
  - "正则.*模式"    # 支持正则表达式
prompt: |
  当匹配此技能时，添加到系统提示词的指令...
```

---

## 💬 群聊命令

在群聊中发送 `<System>:命令` 控制机器人：

| 命令 | 说明 |
|------|------|
| `<System>:help` | 显示帮助（包含所有命令、角色、技能） |
| `<System>:reset` | 清空你与机器人的对话上下文 |
| `<System>:status` | 显示当前状态（对话轮数、角色等） |
| `<System>:character [list\|名称]` | 查看可用角色或切换角色 |
| `<System>:skills` | 查看可用技能及触发词 |

---

## 📊 GUI 控制面板

通过 `python main.py --gui` 启动可视化界面：

| 页面 | 功能 |
|------|------|
| 📊 **仪表盘** | 机器人状态监控、启动/停止控制、运行时长、最近消息流 |
| 📋 **日志** | 实时彩色日志查看，支持级别过滤、关键词搜索 |
| 🎭 **角色** | 查看所有角色详情、一键切换角色 |
| 🔧 **技能** | 查看已加载技能列表、触发词 |
| ⚙ **设置** | 图形化编辑配置文件 |

---

## ⚙️ 配置详解

完整配置示例：

```yaml
deepseek:
  api_key: "sk-xxx"           # DeepSeek API Key
  model: "deepseek-chat"      # 模型选择
  max_tokens: 2048            # 最大回复长度
  temperature: 0.7            # 0-2，越高回复越随机

bot:
  name: "小助手"              # 机器人名称
  trigger_mode: "mention"     # mention=仅@触发，all=所有消息
  reply_cooldown: 2.0         # 回复最小间隔(秒)
  character: "default"        # 默认角色
  characters_dir: "characters"
  skills_dir: "skills"

groups:
  - name: "技术交流群"
    url: "https://www.douyin.com/chat?isPopup=1"
  - name: "摸鱼群"
    url: "https://..."        # 可添加多个群

context:
  max_history_rounds: 10      # 保留最近 N 轮对话
  session_timeout: 1800       # 对话超时(秒)

browser:
  headless: false             # 是否隐藏浏览器窗口
  slow_mo: 100               # 键入延迟(ms)
```

---

## 🔧 故障排查

| 现象 | 可能原因 | 解决方案 |
|------|---------|---------|
| 扫码登录失败 | 扫码超时 | 重新运行，尽快扫码 |
| 消息监控无响应 | DOM 选择器过时 | 查看[选择器调整指南](USAGE.md#dom-选择器调整) |
| API 报错 | API Key 无效或欠费 | 检查 DeepSeek 控制台余额 |
| Cookie 登录失效 | Cookie 过期 | 删除 `data/cookies.json`，重新扫码 |
| GUI 启动报错 | PyQt6 未安装 | `pip install PyQt6>=6.5.0` |

---

## 📁 项目结构

```
dyrobot/
├── main.py                     # 程序入口
├── config.yaml                 # 主配置文件（需自行创建）
├── config.example.yaml         # 配置模板
├── requirements.txt            # Python 依赖
├── characters/                 # 角色定义目录
│   ├── default.yaml
│   ├── yukino.yaml
│   ├── hachiman.yaml
│   └── 张雪峰.yaml
├── skills/                     # 技能定义目录
│   ├── weather.yaml
│   ├── translation.yaml
│   ├── yukino/                 # SKILL.md 格式
│   ├── hachiman/
│   └── zhangxuefeng-skill-main/
├── src/
│   ├── bot.py                  # Bot 主控逻辑
│   ├── browser/                # 浏览器自动化
│   ├── llm/                    # LLM 客户端
│   ├── core/                   # 核心功能模块
│   │   ├── router.py           # 消息路由
│   │   ├── context.py          # 上下文管理
│   │   ├── commands.py         # 命令处理
│   │   ├── character.py        # 角色管理
│   │   └── skills.py           # 技能管理
│   └── gui/                    # PyQt6 GUI
└── data/
    └── cookies.json            # 登录 Cookie（自动生成）
```

---

## 📝 开发

### 依赖说明

```
playwright>=1.40.0      # 浏览器自动化
pyyaml>=6.0            # YAML 配置解析
httpx>=0.25.0          # HTTP 客户端
PyQt6>=6.5.0           # GUI 框架
```

### 核心模块工作流程

```
用户消息 → ChatMonitor (DOM 监听)
         → MessageRouter (去重、@检测、频率限制)
         → CommandHandler (命令优先处理)
         → ContextManager (加载对话历史)
         → CharacterManager + SkillManager (构建系统提示词)
         → DeepSeekClient (调用 LLM 生成回复)
         → ChatMonitor (发送回复到群聊)
```

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## ⚠️ 免责声明

本项目仅供学习和研究使用。使用本项目时请遵守抖音平台的服务条款和相关法律法规。因使用本项目导致的任何问题，作者不承担任何责任。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📚 更多文档

- [详细使用指南](USAGE.md)
- [更新日志](CHANGELOG.md)

---

**Enjoy your AI chatbot! 🎉**
