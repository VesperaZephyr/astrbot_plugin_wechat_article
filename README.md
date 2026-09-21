# astrbot_plugin_wechat_article 微信公众号全文精读与公式总结插件

<div align="center">

![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-blue.svg)
![Version](https://img.shields.io/badge/Version-1.3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-orange.svg)
![Author](https://img.shields.io/badge/Author-VesperaZephyr-purple.svg)

专为 **[AstrBot](https://github.com/Soulter/AstrBot)** 打造的微信公众号（mp.weixin.qq.com）全文精读插件。  
解决传统解析器**数学公式丢失空白、排版崩塌、长文刷屏**等痛点，支持**无公式秒回纯文本**与**有公式高保真长图**智能自适应。

</div>

---

## ✨ 核心特性

- ⚡ **无公式极速纯文本模式 (New v1.3.0)**：
  - 自动检测文章是否含有数学公式；
  - **若文章没有数学公式**，自动跳过耗时的无头浏览器截图渲染，直接以合并转发形式发送**纯文本 AI 总结 + 原文分段文本**，响应提升 5 倍以上，秒级出结果！
- 📐 **数学公式高保真长图还原**：
  - **若文章包含数学公式**（微信内联 SVG 或 `data-formula` 属性），自动激活高保真渲染管线；
  - 总结卡片使用 **Markdown + KaTeX** 渲染为专业暗色卡片图；正文输出 2 倍高清长图，行内与独立块级公式完美对齐排版。
- 📑 **优雅的合并转发消息结构**：
  - 彻底杜绝长图/大段文本在聊天窗口刷屏；
  - **节点 1**：`以下是对微信公众号 <URL> 内容的解析和总结：`；
  - **节点 2**：AI 深度精读总结（有公式为渲染卡片图，无公式为纯文本总结）；
  - **后续节点**：公众号原文内容（有公式为高清长图切片，无公式为完整段落纯文本）。
- 🖼️ **防盗链与懒加载还原**：
  - 自动将微信 `data-src` 图片属性注入为真实 `src`，并注入 `<meta name="referrer" content="no-referrer">`，彻底防止裂图。
- ✂️ **超长文章智能分段切片**：
  - 若长图高度超过阈值（默认 12,000px），自动使用 Pillow 进行高精度无缝切片，避免 QQ 移动端强行压缩模糊。
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
| `fast_text_when_no_formula` | `true` | **无公式文章启用快速纯文本模式**：跳过长图渲染直接合并转发纯文本+总结，秒级响应 |
| `render_mode` | `dual_image` | 有公式时的展示形式：`dual_image`(双图合并转发) / `text_summary_with_image`(纯文本+长图) / `image_only` / `summary_only` |
| `summary_style` | `academic_math` | AI 总结风格：`academic_math`(学术与数理精读) / `concise`(极简速读) / `detailed`(详细全面) |
| `max_slice_height` | `12000` | 单张长图最大高度阈值（像素），超过自动进行智能无缝分段切片 |
| `card_theme` | `dark` | 总结卡片配色主题：`dark`(暗色极客) / `light`(优雅浅白) |
| `access_mode` | `blacklist` | 群聊权限控制模式：`blacklist`(黑名单) / `whitelist`(白名单) |
| `group_list` | `""` | 黑名单或白名单的群号列表（逗号分隔） |

---

## 📄 开源许可

本项目遵循 [MIT License](LICENSE) 许可开源。欢迎提交 Issue 或 Pull Request！
