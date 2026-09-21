# -*- coding: utf-8 -*-
"""
Playwright 高清长图渲染引擎
包含：
1. 微信公众号正文排版高清长图渲染 (支持公式与图片懒加载还原)
2. 基于 Markdown + KaTeX 的专业导读总结卡片图渲染
"""

import os
import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional
import markdown
from PIL import Image as PILImage
from playwright.async_api import async_playwright, Browser, Playwright

logger = logging.getLogger(__name__)

_BROWSER_LOCK = asyncio.Lock()
_GLOBAL_PLAYWRIGHT: Optional[Playwright] = None
_GLOBAL_BROWSER: Optional[Browser] = None

OUTPUT_DIR = "/AstrBot/data/temp/wechat_article"

async def get_browser() -> Browser:
    """获取或初始化复用的 Playwright 浏览器实例"""
    global _GLOBAL_PLAYWRIGHT, _GLOBAL_BROWSER
    async with _BROWSER_LOCK:
        if _GLOBAL_BROWSER is not None and _GLOBAL_BROWSER.is_connected():
            return _GLOBAL_BROWSER

        if _GLOBAL_PLAYWRIGHT is None:
            _GLOBAL_PLAYWRIGHT = await async_playwright().start()

        _GLOBAL_BROWSER = await _GLOBAL_PLAYWRIGHT.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        return _GLOBAL_BROWSER


class WeChatArticleRenderer:
    """微信文章长图与总结卡片渲染器"""

    @classmethod
    def _ensure_output_dir(cls):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    @classmethod
    async def render_article_image(cls, article_data: Dict[str, Any], max_slice_height: int = 12000) -> List[str]:
        """
        渲染微信公众号正文高清长图。
        若整图高度超过 max_slice_height，使用 Pillow 自动进行智能无缝切片。
        返回生成的图片绝对路径列表。
        """
        cls._ensure_output_dir()
        browser = await get_browser()

        title = article_data.get("title", "微信文章")
        author = article_data.get("author", "微信公众号")
        publish_time = article_data.get("publish_time", "")
        formula_count = article_data.get("formula_count", 0)
        content_html = article_data.get("content_html", "")

        formula_badge = f'<span class="badge formula-badge">包含 {formula_count} 个数学公式</span>' if formula_count > 0 else ""

        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="referrer" content="no-referrer">
<title>{title}</title>
<style>
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "WenQuanYi Zen Hei", sans-serif;
    background-color: #f7f9fa;
    color: #2c3e50;
    line-height: 1.85;
    letter-spacing: 0.03em;
    padding: 30px 20px 50px;
    display: flex;
    justify-content: center;
  }}
  .article-card {{
    width: 780px;
    background: #ffffff;
    border-radius: 18px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
    padding: 42px 48px;
    overflow: hidden;
  }}
  .header {{
    border-bottom: 2px solid #f0f2f5;
    padding-bottom: 24px;
    margin-bottom: 30px;
  }}
  .title {{
    font-size: 26px;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.45;
    margin-bottom: 16px;
  }}
  .meta-info {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 14px;
    color: #8c9ba5;
  }}
  .author {{
    font-weight: 600;
    color: #07c160;
    background: rgba(7, 193, 96, 0.08);
    padding: 3px 10px;
    border-radius: 6px;
  }}
  .badge {{
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 500;
  }}
  .formula-badge {{
    background: #eef2ff;
    color: #4f46e5;
    border: 1px solid #c7d2fe;
  }}
  .content {{
    font-size: 16.5px;
    color: #333333;
  }}
  .content p, .content section {{
    margin: 1.1em 0;
    word-break: break-word;
  }}
  .content img {{
    max-width: 100% !important;
    height: auto !important;
    display: block;
    margin: 18px auto;
    border-radius: 8px;
  }}
  .content blockquote {{
    border-left: 4px solid #07c160;
    background: #fcfcfc;
    padding: 12px 18px;
    margin: 1.2em 0;
    color: #555;
    font-style: normal;
    border-radius: 0 8px 8px 0;
  }}
  /* 微信公式保真样式 */
  .wx-formula-inline, span[data-formula-type="inline-equation"] {{
    display: inline-block !important;
    vertical-align: -0.28ex !important;
    margin: 0 2px !important;
  }}
  .wx-formula-block, section[data-formula-type="block-equation"] {{
    display: block !important;
    text-align: center !important;
    margin: 1.4em 0 !important;
    overflow-x: auto !important;
    padding: 6px 0;
  }}
  svg {{
    display: inline-block !important;
    overflow: visible !important;
  }}
  .footer {{
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px dashed #e2e8f0;
    text-align: center;
    font-size: 13px;
    color: #a0aec0;
  }}
</style>
</head>
<body>
  <div class="article-card" id="capture-container">
    <div class="header">
      <h1 class="title">{title}</h1>
      <div class="meta-info">
        <span class="author">📱 {author}</span>
        {f'<span>📅 {publish_time}</span>' if publish_time else ''}
        {formula_badge}
      </div>
    </div>
    <div class="content" id="js_content_wrap">
      {content_html}
    </div>
    <div class="footer">
      Generated by AstrBot WeChat Article Reader · 高保真数学公式长图
    </div>
  </div>
</body>
</html>"""

        context = await browser.new_context(
            viewport={"width": 900, "height": 1000},
            device_scale_factor=2,
        )
        page = await context.new_page()

        try:
            await page.set_content(html_template, wait_until="load", timeout=35000)

            # 注入 JS 确保所有图片的 data-src 注入
            await page.evaluate("""
                () => {
                    const imgs = document.querySelectorAll('img');
                    imgs.forEach(img => {
                        const real = img.getAttribute('data-src') || img.getAttribute('data-original');
                        if (real && img.src !== real) {
                            img.src = real;
                        }
                    });
                }
            """)

            try:
                await page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass

            card_el = await page.query_selector("#capture-container")
            if not card_el:
                card_el = await page.query_selector("body")

            box = await card_el.bounding_box()
            target_h = int(box["height"]) if box else 1500
            await page.set_viewport_size({"width": 900, "height": target_h + 100})

            uid = uuid.uuid4().hex[:8]
            full_img_path = os.path.join(OUTPUT_DIR, f"wx_article_{uid}_full.png")
            await card_el.screenshot(path=full_img_path, type="png")

            # 使用 Pillow 进行无缝切片
            with PILImage.open(full_img_path) as im:
                img_w, img_h = im.size
                if img_h <= max_slice_height:
                    return [full_img_path]

                logger.info(f"[WeChatRenderer] 长图高度为 {img_h}px (阈值 {max_slice_height}px)，进行分段切片...")
                file_paths = []
                part_idx = 1
                for y in range(0, img_h, max_slice_height):
                    bottom = min(y + max_slice_height, img_h)
                    part_img = im.crop((0, y, img_w, bottom))
                    part_path = os.path.join(OUTPUT_DIR, f"wx_article_{uid}_part{part_idx}.png")
                    part_img.save(part_path, "PNG")
                    file_paths.append(part_path)
                    part_idx += 1

                try:
                    os.remove(full_img_path)
                except Exception:
                    pass

                return file_paths

        finally:
            await page.close()
            await context.close()

    @classmethod
    async def render_markdown_summary_card(
        cls,
        markdown_text: str,
        title: str,
        author: str,
        publish_time: str = "",
        formula_count: int = 0
    ) -> str:
        """
        将大模型生成的 Markdown 文本使用 Playwright + KaTeX 渲染为高颜值卡片图
        返回生成的图片文件路径
        """
        cls._ensure_output_dir()
        browser = await get_browser()

        # 将 Markdown 转换为 HTML
        md_html_body = markdown.markdown(
            markdown_text,
            extensions=["tables", "fenced_code", "nl2br", "sane_lists"]
        )

        badge_info = f'<span class="badge">包含 {formula_count} 个数学公式</span>' if formula_count > 0 else ""

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdn.bootcdn.net/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<script src="https://cdn.bootcdn.net/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
<style>
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    padding: 30px;
    display: flex;
    justify-content: center;
  }}
  .card {{
    width: 720px;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 20px;
    padding: 38px 42px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  }}
  .card-top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #334155;
    padding-bottom: 16px;
    margin-bottom: 22px;
  }}
  .topic-tag {{
    font-size: 13px;
    font-weight: 700;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    padding: 4px 12px;
    border-radius: 8px;
  }}
  .badge {{
    font-size: 12px;
    color: #a78bfa;
    background: rgba(167, 139, 250, 0.12);
    padding: 3px 10px;
    border-radius: 6px;
  }}
  .article-meta {{
    margin-bottom: 24px;
  }}
  .article-title {{
    font-size: 22px;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.4;
    margin-bottom: 8px;
  }}
  .article-author {{
    font-size: 14px;
    color: #94a3b8;
  }}
  /* Markdown 内容区样式定制 */
  .md-body {{
    font-size: 15px;
    line-height: 1.75;
    color: #cbd5e1;
  }}
  .md-body h1, .md-body h2, .md-body h3 {{
    color: #38bdf8;
    font-weight: 700;
    margin: 20px 0 12px;
    font-size: 17px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .md-body h3:first-child {{
    margin-top: 0;
  }}
  .md-body p {{
    margin: 10px 0;
    word-break: break-word;
  }}
  .md-body ul, .md-body ol {{
    padding-left: 20px;
    margin: 10px 0;
  }}
  .md-body li {{
    margin: 6px 0;
  }}
  .md-body strong {{
    color: #f1f5f9;
  }}
  .md-body blockquote {{
    background: rgba(56, 189, 248, 0.07);
    border-left: 4px solid #38bdf8;
    padding: 10px 14px;
    border-radius: 0 8px 8px 0;
    margin: 14px 0;
    color: #e2e8f0;
  }}
  .md-body code {{
    background: #0f172a;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 14px;
    color: #f472b6;
  }}
  /* KaTeX 公式在暗色背景下的优化 */
  .katex {{
    font-size: 1.08em;
    color: #f8fafc;
  }}
  .katex-display {{
    margin: 1em 0 !important;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 8px 0;
  }}
  .card-footer {{
    margin-top: 30px;
    padding-top: 16px;
    border-top: 1px solid #334155;
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: #64748b;
  }}
</style>
</head>
<body>
  <div class="card" id="summary-card">
    <div class="card-top">
      <span class="topic-tag">✦ 微信公众号 AI 深度导读</span>
      {badge_info}
    </div>
    <div class="article-meta">
      <h1 class="article-title">{title}</h1>
      <div class="article-author">来源：{author} {f'· {publish_time}' if publish_time else ''}</div>
    </div>
    <div class="md-body">
      {md_html_body}
    </div>
    <div class="card-footer">
      <span>AstrBot WeChat DeepSummary</span>
      <span>正文高清解析已在后续消息合并发送 ⇣</span>
    </div>
  </div>

  <script>
    renderMathInElement(document.body, {{
      delimiters: [
        {{left: "$$", right: "$$", display: true}},
        {{left: "$", right: "$", display: false}}
      ],
      throwOnError: false
    }});
  </script>
</body>
</html>"""

        context = await browser.new_context(
            viewport={"width": 800, "height": 1000},
            device_scale_factor=2,
        )
        page = await context.new_page()

        try:
            await page.set_content(full_html, wait_until="networkidle", timeout=20000)
            card_el = await page.query_selector("#summary-card")
            if not card_el:
                card_el = await page.query_selector("body")

            box = await card_el.bounding_box()
            target_h = int(box["height"]) if box else 1000
            await page.set_viewport_size({"width": 800, "height": target_h + 80})

            uid = uuid.uuid4().hex[:8]
            img_path = os.path.join(OUTPUT_DIR, f"wx_summary_{uid}.png")
            await card_el.screenshot(path=img_path, type="png")
            return img_path

        finally:
            await page.close()
            await context.close()
