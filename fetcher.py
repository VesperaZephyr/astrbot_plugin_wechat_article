# -*- coding: utf-8 -*-
"""
微信公众号文章抓取与结构化提取模块
"""

import re
import logging
from typing import Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup
from .formula_processor import WeChatFormulaProcessor

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

class WeChatArticleFetcher:
    """微信公众号文章获取与解析器"""

    @staticmethod
    def extract_urls(text: str) -> list[str]:
        """从任意文本中提取微信公众号文章链接"""
        pattern = (
            r"https?://mp\.weixin\.qq\.com/s(?:"
            r"/[A-Za-z0-9_-]+(?:\?[^\s<>\"']*)?"
            r"|\?(?=[^\s<>\"']*__biz=)[^\s<>\"']+"
            r")"
        )
        return re.findall(pattern, text)

    @classmethod
    async def fetch_article(cls, url: str) -> Optional[Dict[str, Any]]:
        """
        异步抓取微信公众号文章，返回结构化数据
        """
        headers = dict(DEFAULT_HEADERS)
        headers["Referer"] = url

        try:
            async with httpx.AsyncClient(headers=headers, timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.error(f"[WeChatFetcher] 请求失败: HTTP {resp.status_code} ({url})")
                    return None
                html = resp.text

        except Exception as e:
            logger.error(f"[WeChatFetcher] 网络异常: {e}", exc_info=True)
            return None

        # 检查是否为有效微信文章
        if "var msg_title" not in html and 'id="js_content"' not in html:
            logger.warning("[WeChatFetcher] 页面未包含微信公众号正文标识")
            return None

        soup = BeautifulSoup(html, "html.parser")

        # 1. 提取标题
        title = ""
        title_el = soup.find(id="activity-name")
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "").strip()
        if not title:
            # 正则回退提取
            m = re.search(r'var msg_title = [\'"]([^\'"]+)[\'"]', html)
            if m:
                title = m.group(1).strip()
        if not title:
            title = "微信公众号文章"

        # 2. 提取公众号名称 / 作者
        author = ""
        author_el = soup.find(id="js_name") or soup.find(id="js_author_name")
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            m = re.search(r'var nickname = [\'"]([^\'"]+)[\'"]', html)
            if m:
                author = m.group(1).strip()
        if not author:
            author = "微信公众号"

        # 3. 提取发布时间
        publish_time = ""
        m_time = re.search(r'var ct = [\'"]?([0-9]{10})[\'"]?', html)
        if m_time:
            import datetime
            ts = int(m_time.group(1))
            publish_time = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

        # 4. 提取正文容器
        content_el = soup.find(id="js_content")
        if not content_el:
            logger.error("[WeChatFetcher] 找不到正文 #js_content")
            return None

        # 确保正文可见 (微信有时加 style="visibility: hidden")
        content_el["style"] = "visibility: visible !important;"

        # 处理公式
        formula_count = WeChatFormulaProcessor.process_for_rendering(content_el)

        # 修复图片懒加载：将 data-src 复制到 src，并移除可能阻碍渲染的内联隐藏样式
        for img in content_el.find_all("img"):
            real_src = img.get("data-src") or img.get("data-original") or img.get("src")
            if real_src:
                img["src"] = real_src
                # 微信防裂图样式
                img["referrerpolicy"] = "no-referrer"
                img["loading"] = "eager"
            # 移除宽度为0的占位
            img_style = img.get("style", "")
            img_style += "; max-width: 100% !important; height: auto !important; display: block; margin: 10px auto;"
            img["style"] = img_style

        # 修复视频和音频卡片样式占位
        for iframe in content_el.find_all(["iframe", "video"]):
            iframe["referrerpolicy"] = "no-referrer"

        # 提取供 LLM 阅读的含 LaTeX 的全文文本
        llm_text = WeChatFormulaProcessor.extract_text_with_latex(content_el)

        return {
            "url": url,
            "title": title,
            "author": author,
            "publish_time": publish_time,
            "formula_count": formula_count,
            "content_html": str(content_el),
            "full_text": llm_text,
            "char_count": len(llm_text),
        }
