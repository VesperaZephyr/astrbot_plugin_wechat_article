# astrbot_plugin_wechat_article 微信公众号全文精读与公式总结插件

<div align="center">

![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-blue.svg)
![Version](https://img.shields.io/badge/Version-1.5.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-orange.svg)
![Author](https://img.shields.io/badge/Author-VesperaZephyr-purple.svg)

专为 **[AstrBot](https://github.com/Soulter/AstrBot)** 打造的微信公众号（mp.weixin.qq.com）全文精读插件。  
彻底解决传统解析器**数学公式丢失空白、排版崩塌、长文刷屏、图片丢失占位**等痛点。

</div>

---

## ✨ 核心特性 (v1.5.0)

- 📐 **全格式 LaTeX 公式保护与离线 MathJax 排版 (New v1.5.0)**：
  - 全面支持包括 `\[ ... \]`、`\( ... \)`、`$$ ... $$`、`$ ... $` 在内的全部 LaTeX 语法；
  - 在 Markdown 解析前建立完整语法防护，防止公式内的下划线 `_` 和星号 `*` 被错误转换为斜体加粗；
  - 采用服务器本地离线 **MathJax 2.7.7** 引擎排版，彻底根治公式乱码，呈现标准教材级矢量数学排版！
- 📸 **微信官方原网页 1:1 极清截图，插图 100% 真实呈现 (New v1.5.0)**：
  - 只要文章含有插图（如游戏资讯、原神PV、壁纸文章）或含有数学公式，直接通过 Playwright Chromium 导航微信原版网页截图；
  - **插图 100% 是真实原版高清图片，绝无 `[配图: 插图]` 占位符！**
  - **公式零浮动、零位移、零变形！** 微信官方怎么排版，长图就怎么呈现；
  - 自动净化页面：剔除底部二维码、点赞、在看、评论等冗余杂项。
- 🎯 **AI 导读自适应定制，拒绝生硬生搬硬套**：
  - **无数学公式文章**：采用社科/资讯通用 Prompt，**严禁生硬出现数学词汇**，语言通俗自然；
  - **包含数学公式文章**：开启专业数理逻辑与公式推导分析。
- ⚡ **无图无公式极速纯文本模式**：
  - 若文章纯为无图短讯/通知，直接以合并转发形式发送纯文本总结与正文，秒级响应。
- 📑 **优雅的合并转发消息结构**：
  - **节点 1**：`以下是对微信公众号 <URL> 内容的解析和总结：`；
  - **节点 2**：AI 深度精读总结（有公式为 MathJax 渲染卡片图，无公式为清晰纯文本总结）；
  - **后续节点**：公众号原文（微信原版高清长图切片，插图真实、排版完美）。
- 🤖 **原生 LLM Agent 工具 (Function Calling)**：
  - 注册 `@filter.llm_tool(name="read_wechat_article")`；
  - 在群聊或私聊中 **@机器人 帮我看看这篇公众号讲了什么 <链接>** 时，大模型可自主感知并调用该工具。

---

## 🚀 安装方法

### 方式一：克隆到插件目录

在 AstrBot 的插件目录中执行：

```bash
cd data/plugins/
git clone https://github.com/VesperaZephyr/astrbot_plugin_wechat_article.git
```

### 方式二：安装依赖

本插件依赖 `beautifulsoup4`、`playwright`、`markdown`、`pillow` 与 `httpx`：

```bash
pip install beautifulsoup4 playwright markdown pillow httpx -i https://mirrors.aliyun.com/pypi/simple/

# 安装 Playwright 的 Chromium 内核
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ python -m playwright install chromium
python -m playwright install-deps chromium
```

安装完成后，在 AstrBot 管理面板重启即可自动加载。

---

## 📖 使用方法

### 1. 自动识别模式（最常用）
在任意群聊或私聊中，直接发送微信公众号文章链接：
```text
https://mp.weixin.qq.com/s/xxxxxx
```
机器人将自动捕获链接，并发送合并转发精读报告。

### 2. 自然语言与 @机器人
直接在群内 @机器人：
```text
@机器人 帮我解析一下这篇公众号文章讲了什么 https://mp.weixin.qq.com/s/xxxxxx
```
大模型将通过内置的 `read_wechat_article` 工具自主处理并回复。

### 3. 指令触发
```text
/wx https://mp.weixin.qq.com/s/xxxxxx
```
（别名支持：`/公众号`、`/微信文章`、`/读公众号`、`/微信总结`）

---

## ⚙️ 配置说明

在 AstrBot Web 控制台的「插件配置」中可以直接调节各项参数：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `enable_auto_detect` | `true` | 是否开启群聊/私聊链接自动识别 |
| `fast_text_when_no_formula` | `true` | 是否在文章无图无公式时启用极速纯文本模式 |
| `render_mode` | `dual_image` | 有公式时的展示形式：`dual_image`(双图合并转发) / `text_summary_with_image`(纯文本+长图) / `image_only` / `summary_only` |
| `summary_style` | `academic_math` | AI 总结风格：`academic_math`(学术与数理精读) / `concise`(极简速读) / `detailed`(详细全面) |
| `max_slice_height` | `12000` | 单张长图最大高度阈值（像素），超过自动进行智能无缝分段切片 |
| `card_theme` | `dark` | 总结卡片配色主题：`dark`(暗色极客) / `light`(优雅浅白) |
| `access_mode` | `blacklist` | 群聊权限控制模式：`blacklist`(黑名单) / `whitelist`(白名单) |
| `group_list` | `""` | 黑名单或白名单的群号列表（逗号分隔） |

---

## 📄 开源许可

本项目遵循 [MIT License](LICENSE) 许可开源。欢迎提交 Issue 或 Pull Request！
