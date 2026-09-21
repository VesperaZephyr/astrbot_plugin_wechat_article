# -*- coding: utf-8 -*-
"""
Playwright 高清长图渲染引擎
核心技术：
1. 原文直接截图：直接导航微信公众号原网页 (page.goto) 截取，100% 还原微信官方原始排版与矢量 SVG 公式，零公式浮动，零图片丢失！
2. 总结卡片渲染：采用 Markdown 公式防护 + 本地离线 MathJax 2.7.7 引擎，彻底消除公式乱码与下划线斜体破坏！
"""

import os
import re
import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
import mistune
from PIL import Image as PILImage
from playwright.async_api import async_playwright, Browser, Playwright

logger = logging.getLogger(__name__)

_BROWSER_LOCK = asyncio.Lock()
_GLOBAL_PLAYWRIGHT: Optional[Playwright] = None
_GLOBAL_BROWSER: Optional[Browser] = None

OUTPUT_DIR = "/AstrBot/data/temp/wechat_article"

# 本地离线 MathJax 路径
LOCAL_MATHJAX_PATH = "/AstrBot/data/plugins/astrbot_plugin_mathsolve/vendor/md2img/mathjax-2.7.7/MathJax.js"

# 数学公式防护正则
_BLOCK_MATH_RE = re.compile(r'\$\$([\s\S]*?)\$\$')
_INLINE_MATH_RE = re.compile(r'(?<!\$)\$([^\$\n]+?)\$(?!\$)')

def _protect_math_for_markdown(text: str) -> Tuple[str, List[str]]:
    """在 Markdown 解析前保护数学公式，避免被 _ * 等语法破坏"""
    pieces = []
    def repl_block(m):
        pieces.append(m.group(0))
        return f"<!--MATH_BLOCK_{len(pieces)-1}-->"
    def repl_inline(m):
        pieces.append(m.group(0))
        return f"<!--MATH_INLINE_{len(pieces)-1}-->"
    text = _BLOCK_MATH_RE.sub(repl_block, text)
    text = _INLINE_MATH_RE.sub(repl_inline, text)
    return text, pieces

def _restore_math_tokens(html: str, pieces: List[str]) -> str:
    """Markdown 解析完成后安全恢复数学公式"""
    for i, piece in enumerate(pieces):
        html = html.replace(f"<!--MATH_BLOCK_{i}-->", piece)
        html = html.replace(f"<!--MATH_INLINE_{i}-->", piece)
    return html

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
                "--allow-file-access-from-files",
            ]
        )
        return _GLOBAL_BROWSER


class WeChatArticleRenderer:
    """微信文章长图与总结卡片渲染器"""

    @classmethod
    def _ensure_output_dir(cls):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    @classmethod
    async def render_direct_wechat_article(cls, url: str, max_slice_height: int = 12000) -> List[str]:
        """
        直接通过 Playwright 访问微信公众号原网页进行 1:1 官方原版极清截图。
        彻底消除自定义 HTML 导致的公式错位、公式浮动、图片丢失问题。
        返回生成的切片图片路径列表。
        """
        cls._ensure_output_dir()
        browser = await get_browser()

        context = await browser.new_context(
            viewport={"width": 800, "height": 1200},
            device_scale_factor=2, # 2x Retina 高清抗锯齿
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            logger.info(f"[WeChatRenderer] 开始导航微信原网页截图: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # 页面净化与懒加载图片唤醒
            await page.evaluate("""() => {
                const content = document.getElementById("js_content");
                if (content) {
                    content.style.visibility = "visible";
                    content.style.opacity = "1";
                }

                // 强制所有 data-src 注入真实 src
                document.querySelectorAll("img").forEach(img => {
                    const dataSrc = img.getAttribute("data-src") || img.getAttribute("data-original");
                    if (dataSrc) {
                        img.src = dataSrc;
                        img.removeAttribute("loading");
                    }
                });

                // 移除底部二维码、点赞、在看、评论区及底部推荐
                const junkSelectors = [
                    "#js_pc_qr_code", ".qr_code_pc_outer", "#like_comment_box",
                    "#js_tags", ".rich_media_area_extra", ".reward_area",
                    "#js_view_source", ".original_area_primary", ".article-tag__list",
                    ".appmsg_read_count_primary", "#js_cmt_area", ".js_related_article",
                    "#js_bottom_banner", "#js_profile_qrcode"
                ];
                junkSelectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });

                // 美化背景为白底卡片
                if (document.body) {
                    document.body.style.backgroundColor = "#f6f8fa";
                }
                const container = document.querySelector("#img-content") || document.querySelector(".rich_media_area_primary");
                if (container) {
                    container.style.backgroundColor = "#ffffff";
                    container.style.padding = "30px 36px";
                    container.style.borderRadius = "16px";
                    container.style.margin = "20px auto";
                    container.style.boxShadow = "0 8px 30px rgba(0,0,0,0.06)";
                }
            }""")

            # 等待 2 秒让图片和 SVG 渲染完全稳定
            await page.wait_for_timeout(2000)

            target_el = await page.query_selector("#img-content") or await page.query_selector(".rich_media_area_primary") or await page.query_selector("body")
            box = await target_el.bounding_box()
            target_h = int(box["height"]) if box else 2000

            # 动态扩展高度
            await page.set_viewport_size({"width": 800, "height": target_h + 100})

            uid = uuid.uuid4().hex[:8]
            full_img_path = os.path.join(OUTPUT_DIR, f"wx_direct_{uid}_full.png")
            await target_el.screenshot(path=full_img_path, type="png")

            # 使用 Pillow 检查并切片
            with PILImage.open(full_img_path) as im:
                img_w, img_h = im.size
                if img_h <= max_slice_height:
                    return [full_img_path]

                logger.info(f"[WeChatRenderer] 原版截图高达 {img_h}px (阈值 {max_slice_height}px)，进行智能分段切片...")
                file_paths = []
                part_idx = 1
                for y in range(0, img_h, max_slice_height):
                    bottom = min(y + max_slice_height, img_h)
                    part_img = im.crop((0, y, img_w, bottom))
                    part_path = os.path.join(OUTPUT_DIR, f"wx_direct_{uid}_part{part_idx}.png")
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
        summary_text: str,
        title: str,
        author: str,
        publish_time: str = "",
        formula_count: int = 0
    ) -> str:
        """
        基于 Markdown + 本地离线 MathJax 渲染 AI 深度总结卡片。
        彻底解决公式乱码、斜体误伤与文字错乱。
        """
        cls._ensure_output_dir()
        browser = await get_browser()

        # 1. 保护公式
        protected_md, pieces = _protect_math_for_markdown(summary_text)

        # 2. 解析 Markdown
        parser = mistune.create_markdown(escape=False, plugins=["table", "url", "strikethrough"])
        html_body = parser(protected_md)

        # 3. 恢复公式
        html_body = _restore_math_tokens(html_body, pieces)

        badge_info = f'<span class="badge">包含 {formula_count} 个数学公式</span>' if formula_count > 0 else '<span class="badge">深度精读</span>'

        # MathJax 离线路径引用
        if os.path.exists(LOCAL_MATHJAX_PATH):
            mathjax_script_tag = f'<script type="text/javascript" src="file://{LOCAL_MATHJAX_PATH}?config=TeX-MML-AM_CHTML"></script>'
        else:
            mathjax_script_tag = '<script type="text/javascript" src="https://cdn.bootcdn.net/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML"></script>'

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<script type="text/x-mathjax-config">
  MathJax.Hub.Config({{
    tex2jax: {{
      inlineMath: [["$","$"], ["\\\\(","\\\\)"]],
      displayMath: [["$$","$$"], ["\\\\[","\\\\]"]],
      processEscapes: true
    }},
    "HTML-CSS": {{
      scale: 96,
      linebreaks: {{ automatic: true, width: "container" }}
    }}
  }});
</script>
{mathjax_script_tag}
<style>
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "WenQuanYi Zen Hei", sans-serif;
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
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
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
    font-weight: 600;
  }}
  .article-title {{
    font-size: 22px;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.45;
    margin-bottom: 8px;
  }}
  .article-author {{
    font-size: 14px;
    color: #94a3b8;
    margin-bottom: 24px;
  }}
  .md-body {{
    font-size: 15px;
    line-height: 1.8;
    color: #cbd5e1;
  }}
  .md-body h1, .md-body h2, .md-body h3 {{
    color: #38bdf8;
    font-weight: 700;
    margin: 20px 0 10px;
    font-size: 16.5px;
    border-left: 3.5px solid #38bdf8;
    padding-left: 10px;
  }}
  .md-body h3:first-child {{
    margin-top: 0;
  }}
  .md-body p {{
    margin: 8px 0;
    word-break: break-word;
  }}
  .md-body ul, .md-body ol {{
    padding-left: 20px;
    margin: 8px 0;
  }}
  .md-body li {{
    margin: 6px 0;
  }}
  .md-body strong {{
    color: #f1f5f9;
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
      {html_body}
    </div>
    <div class="card-footer">
      <span>AstrBot WeChat DeepSummary</span>
      <span>正文高清原文长图已在后续消息合并发送 ⇣</span>
    </div>
  </div>
</body>
</html>"""

        # 保存为本地 HTML 文件以解决 Chromium file:// 跨域加载安全限制
        uid = uuid.uuid4().hex[:8]
        tmp_html_path = os.path.join(OUTPUT_DIR, f"summary_page_{uid}.html")
        with open(tmp_html_path, "w", encoding="utf-8") as f:
            f.write(full_html)

        context = await browser.new_context(
            viewport={"width": 800, "height": 1000},
            device_scale_factor=2,
        )
        page = await context.new_page()

        try:
            await page.goto(f"file://{tmp_html_path}", wait_until="load")

            # 等待 MathJax 准备好并执行数学公式排版
            if pieces:
                try:
                    await page.wait_for_function("() => !!(window.MathJax && window.MathJax.Hub)", timeout=4000)
                    await page.evaluate("""() => new Promise((resolve) => {
                        MathJax.Hub.Queue(["Typeset", MathJax.Hub], () => resolve(true));
                    })""")
                except Exception as e:
                    logger.warning(f"[WeChatRenderer] MathJax Typeset wait failed/timed out: {e}")

            card_el = await page.query_selector("#summary-card") or await page.query_selector("body")
            box = await card_el.bounding_box()
            target_h = int(box["height"]) if box else 1000
            await page.set_viewport_size({"width": 800, "height": target_h + 80})

            img_path = os.path.join(OUTPUT_DIR, f"wx_summary_{uid}.png")
            await card_el.screenshot(path=img_path, type="png")

            # 清理临时 html
            try:
                os.remove(tmp_html_path)
            except Exception:
                pass

            return img_path

        finally:
            await page.close()
            await context.close()
