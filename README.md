# astrbot_plugin_wechat_article 微信公众号全文精读与公式总结插件

<div align="center">

![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-blue.svg)
![Version](https://img.shields.io/badge/Version-1.2.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-orange.svg)
![Author](https://img.shields.io/badge/Author-VesperaZephyr-purple.svg)

专为 **[AstrBot](https://github.com/Soulter/AstrBot)** 打造的微信公众号（mp.weixin.qq.com）全文精读插件。  
彻底解决传统解析器**数学公式丢失空白、排版崩塌、长文刷屏**的痛点。

</div>

---

## ✨ 核心特性

- 📐 **数学公式高保真还原**：
  - 微信公众号在移动端使用内联 `<svg>` 矢量图形结合 `data-formula` 属性展现公式；
  - 本插件深度遍历微信 DOM，完美解析行内公式与独立块级公式，并在长图中保留原貌，同时为大模型还原为标准 LaTeX 语法（`$...$` 与 `$$...$$`）。
- 📑 **优雅的合并转发消息**：
  - 不再用单张或多张大图刷屏群聊，自动打包为单个干净整洁的 QQ 合并转发卡片；
  - **节点 1**：引导语与来源提示；
  - **节点 2**：由大模型总结、结合 Markdown + KaTeX 引擎渲染的高颜值暗色卡片图；
  - **节点 3+**：公众号原文 2 倍高清正文长图（保留完整图文排版）。
- 🖼️ **防盗链与懒加载还原**：
  - 自动将微信 `data-src` 图片属性注入为真实 `src`，并注入 `<meta name="referrer" content="no-referrer">`，彻底解决图片裂图问题。
- ✂️ **超长文章智能分段切片**：
  - 若文章篇幅过长（高度超过 12,000px），自动使用高精度无缝切片，防止 QQ 移动端严重压缩模糊。
- 🤖 **原生 LLM Agent 工具支持 (Function Calling)**：
  - 不仅支持群聊自动识别链接与 `/wx <链接>` 指令，更注册了 `@filter.llm_tool`；
  - 用户在群聊或私聊中 **@机器人 读一下这篇公众号文章** 时，大模型能够感知并自主调用该插件！

---

## 🚀 安装方法

### 方式一：克隆到插件目录

在 AstrBot 的插件目录中执行：

```bash
cd data/plugins/
git clone https://github.com/VesperaZephyr/astrbot_plugin_wechat_article.git
```

### 方式二：安装依赖

本插件依赖 `beautifulsoup4`、`playwright`、`markdown` 和 `pillow`：

```bash
pip install beautifulsoup4 playwright markdown pillow -i https://mirrors.aliyun.com/pypi/simple/

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
| `render_mode` | `dual_image` | 内容展示形式：`dual_image`(双图合并转发) / `text_summary_with_image`(纯文本+长图) / `image_only` / `summary_only` |
| `summary_style` | `academic_math` | AI 总结风格：`academic_math`(学术与数理精读) / `concise`(极简速读) / `detailed`(详细全面) |
| `max_slice_height` | `12000` | 单张长图最大高度阈值（像素），超过自动进行智能无缝分段切片 |
| `card_theme` | `dark` | 总结卡片配色主题：`dark`(暗色极客) / `light`(优雅浅白) |
| `access_mode` | `blacklist` | 群聊权限控制模式：`blacklist`(黑名单) / `whitelist`(白名单) |
| `group_list` | `""` | 黑名单或白名单的群号列表（逗号分隔） |

---

## 📄 开源许可

本项目遵循 [MIT License](LICENSE) 许可开源。欢迎提交 Issue 或 Pull Request！
