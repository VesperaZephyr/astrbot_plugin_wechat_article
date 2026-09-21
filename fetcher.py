# -*- coding: utf-8 -*-
"""
微信公众号文章抓取与结构化提取模块
支持精准提取图片说明文字与 LaTeX 数学公式
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

        content_el["style"] = "visibility: visible !important;"

        # 处理公式统计
        formula_count = WeChatFormulaProcessor.process_for_rendering(content_el)

        # 统计正文真实插图数
        images = content_el.find_all("img")
        image_count = len([img for img in images if img.get("data-src") or img.get("src") or img.get("data-original")])

        # 提取供 LLM 阅读的全文文本（包含图片说明与 LaTeX 公式）
        llm_text = cls._extract_clean_text(content_el)

        return {
            "url": url,
            "title": title,
            "author": author,
            "publish_time": publish_time,
            "formula_count": formula_count,
            "image_count": image_count,
            "content_html": str(content_el),
            "full_text": llm_text,
            "char_count": len(llm_text),
        }

    @classmethod
    def _extract_clean_text(cls, soup: BeautifulSoup) -> str:
        """
        深层提取正文：
        1. 保留图片描述文字 (alt, title, figcaption, 下方紧邻的说明)
        2. 保留 LaTeX 数学公式
        """
        soup_copy = BeautifulSoup(str(soup), "html.parser")

        # 1. 提取公式为 LaTeX 格式
        for el in soup_copy.find_all(attrs={"data-formula": True}):
            formula_type = el.get("data-formula-type", "")
            latex_code = el.get("data-formula", "").strip()
            if not latex_code:
                continue

            if formula_type == "inline-equation" or el.name == "span":
                el.replace_with(f" ${latex_code}$ ")
            else:
                el.replace_with(f"\n\n$${latex_code}$$\n\n")

        # 2. 提取图片说明文字
        for img in soup_copy.find_all("img"):
            desc_parts = []
            alt = img.get("alt", "").strip()
            if alt and alt != "图片":
                desc_parts.append(alt)
            title_attr = img.get("title", "").strip()
            if title_attr:
                desc_parts.append(title_attr)

            # 寻找微信图片下方的 caption / 配图说明
            parent = img.parent
            if parent:
                sibling = parent.find_next_sibling(["figcaption", "span", "p"])
                if sibling:
                    sib_text = sibling.get_text(strip=True)
                    if 0 < len(sib_text) <= 50 and any(w in sib_text for w in ["图", "示意", "如图", "来源", "▲", "▼"]):
                        desc_parts.append(sib_text)

            desc = " - ".join(desc_parts) if desc_parts else "插图"
            img.replace_with(f"\n[配图: {desc}]\n")

        for tag in soup_copy(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        text = soup_copy.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
