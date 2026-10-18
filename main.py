# -*- coding: utf-8 -*-
"""
微信公众号文章全文读取、高保真公式排版与 AI 深度总结插件
v1.4.0 核心突破：
  1. 无公式文章：走极速纯文本合并转发，总结严禁生硬出现数学词汇，完整提取图片说明文字与段落；
  2. 有公式文章：
     - 总结卡片使用离线原生无乱码字体渲染；
     - 原文采用 Playwright 直接导航微信官网 (page.goto) 截图，100% 还原原版排版与矢量公式，彻底解决“公式浮动”与“图片缺失”！
"""

import os
import asyncio
import logging
from typing import Optional, List, AsyncGenerator
from astrbot.api.star import Star, register
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.message_components import Plain, Image, Node, Nodes
from astrbot.api.event import MessageChain
from ._cooperation import is_command_message, split_text, event_tool_serialized
from astrbot.api.all import Context, AstrBotConfig

from .fetcher import WeChatArticleFetcher
from .summarizer import WeChatArticleSummarizer
from .renderer import WeChatArticleRenderer

logger = logging.getLogger(__name__)

@register(
    name="astrbot_plugin_wechat_article",
    author="VesperaZephyr",
    desc="自动读取微信公众号文章全部内容，保留数学公式，合并转发微信原版高清长图与 Markdown 深度总结导读",
    version="1.6.0",
    repo="https://github.com/VesperaZephyr/astrbot_plugin_wechat_article"
)
class WeChatArticlePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._handling_urls = set()
        logger.info("[WeChatArticlePlugin] 微信公众号全文精读与公式总结插件 v1.4.0 已加载。")

    def _is_group_allowed(self, event: AstrMessageEvent) -> bool:
        """检查群聊是否允许使用"""
        group_id = event.get_group_id()
        if not group_id:
            return True

        access_mode = self.config.get("access_mode", "blacklist")
        raw_list = str(self.config.get("group_list", "")).strip()
        groups = [g.strip() for g in raw_list.split(",") if g.strip()]

        if access_mode == "whitelist":
            return str(group_id) in groups
        else:
            return str(group_id) not in groups

    @filter.command("wx", alias={"公众号", "微信文章", "读公众号", "微信总结"})
    async def cmd_wechat(self, event: AstrMessageEvent, url: str = ""):
        """读取微信公众号文章全部内容，保留数学公式并以合并转发形式输出"""
        if not self._is_group_allowed(event):
            return

        urls = WeChatArticleFetcher.extract_urls(url or event.message_str)
        if not urls:
            yield event.plain_result("请在命令后附带微信公众号文章链接，例如：\n/wx https://mp.weixin.qq.com/s/xxxxxx")
            return

        target_url = urls[0]
        async for res in self._process_article(event, target_url):
            yield res

    @filter.llm_tool(name="read_wechat_article")
    @event_tool_serialized('wechat_article')
    async def tool_read_wechat(self, event: AstrMessageEvent, url: str = "") -> str:
        """读取微信公众号文章，发送正文与导读，并返回可供模型判断的执行状态。

        Args:
            url(string): 微信公众号文章的完整链接。
        """
        if not self._is_group_allowed(event):
            return "本群未允许使用公众号精读功能。"
        urls = WeChatArticleFetcher.extract_urls(str(url or event.message_str or ""))
        if not urls:
            return "未识别到合法的微信公众号文章链接，请提供 mp.weixin.qq.com 文章链接。"
        if urls[0] in (event.get_extra('wechat_article_delivered_urls') or ()):
            return "公众号文章已在当前消息中发送，请不要重复读取。"
        status = ''
        async for result in self._process_article(event, urls[0]):
            await event.send(MessageChain(result.chain))
            status = ' '.join(c.text for c in result.chain if isinstance(c, Plain)) or status
        if urls[0] in (event.get_extra('wechat_article_delivered_urls') or ()):
            return '公众号内容已发送。\n' + str(event.get_extra('wechat_article_tool_content') or '')
        return status or "公众号文章未能发送成功，请检查链接或稍后重试。"

    @filter.event_message_type(filter.EventMessageType.ALL, priority=60)
    async def auto_detect_wechat(self, event: AstrMessageEvent):
        """自动检测群聊/私聊中的微信文章链接"""
        raw_text = event.message_str or ""
        if is_command_message(event, raw_text) or getattr(event, "is_at_or_wake_command", False):
            return

        if not self.config.get("enable_auto_detect", True):
            return

        if not self._is_group_allowed(event):
            return

        urls = WeChatArticleFetcher.extract_urls(raw_text)
        if not urls:
            return

        target_url = urls[0]
        key = (event.unified_msg_origin, target_url)
        if key in self._handling_urls:
            return

        self._handling_urls.add(key)
        try:
            logger.info(f"[WeChatArticlePlugin] 自动检测到微信文章链接: {target_url}")
            async for res in self._process_article(event, target_url):
                yield res
            if event.get_extra('wechat_article_delivered'):
                event.stop_event()
        finally:
            self._handling_urls.discard(key)

    @staticmethod
    def _split_text_to_chunks(text: str, max_chars: int = 1800) -> List[str]:
        return split_text(text, max_chars)

    async def _process_article(self, event: AstrMessageEvent, url: str):
        delivered = set(event.get_extra('wechat_article_delivered_urls') or ())
        if url in delivered:
            yield event.plain_result('本条消息中的这篇公众号文章已发送。')
            return
        yield event.plain_result('📖 正在读取微信公众号文章内容，请稍候...')
        try:
            article = await WeChatArticleFetcher.fetch_article(url)
            if not article:
                yield event.plain_result('无法获取微信正文，请检查链接是否有效。')
                return
            title = article.get('title') or '微信文章'
            author = article.get('author') or '微信公众号'
            full_text = article.get('full_text') or ''
            formula_count = article.get('formula_count') or 0
            image_count = article.get('image_count') or 0
            mode = self.config.get('render_mode', 'dual_image')
            summary = ''
            if mode != 'image_only':
                summary = await WeChatArticleSummarizer.generate_markdown_summary(
                    context=self.context, article_data=article,
                    style=self.config.get('summary_style', 'academic_math'),
                    umo=event.unified_msg_origin)
            bot_uin = str(event.get_self_id() or '10000')
            nodes = [Node(content=[Plain(f'《{title}》 · {author}\n来源：{url}')], name='公众号深度解析', uin=bot_uin)]
            if summary:
                card = ''
                if mode == 'dual_image' and formula_count > 0:
                    card = await self._safe_summary_card(summary_text=summary, title=title, author=author,
                                                         publish_time=article.get('publish_time', ''),
                                                         formula_count=formula_count,
                                                         theme=self.config.get('card_theme', 'light'))
                if card and os.path.exists(card):
                    nodes.append(Node(content=[Image.fromFileSystem(card)], name='AI 深度导读', uin=bot_uin))
                else:
                    for chunk in self._split_text_to_chunks(summary):
                        nodes.append(Node(content=[Plain(chunk)], name='AI 深度导读', uin=bot_uin))
            if mode != 'summary_only':
                images = []
                fast = self.config.get('fast_text_when_no_formula', True) and not (formula_count or image_count)
                if not fast or mode == 'image_only':
                    images = await self._safe_article_images(url=url, max_slice_height=max(1000, min(12000, int(self.config.get('max_slice_height', 12000)))))
                images = [path for path in images if os.path.exists(path)]
                if images:
                    for index, path in enumerate(images, 1):
                        nodes.append(Node(content=[Image.fromFileSystem(path)], name=f'公众号原文 {index}/{len(images)}', uin=bot_uin))
                elif full_text.strip():
                    for chunk in self._split_text_to_chunks(full_text):
                        nodes.append(Node(content=[Plain(chunk)], name='公众号原文（文字）', uin=bot_uin))
                else:
                    nodes.append(Node(content=[Plain('原文暂时无法截图，且没有可读取的正文，请打开来源链接查看。')], name='正文读取状态', uin=bot_uin))
            yield event.chain_result([Nodes(nodes)])
            delivered.add(url)
            event.set_extra('wechat_article_delivered_urls', list(delivered))
            event.set_extra('wechat_article_delivered', True)
            event.set_extra('wechat_article_tool_content', f'标题：{title}\n来源：{url}\n实际导读：{summary[:6000]}' if summary else f'标题：{title}\n来源：{url}\n实际正文片段：{full_text[:6000]}')
        except Exception as exc:
            logger.error(f'[WeChatArticlePlugin] 处理文章异常: {exc}', exc_info=True)
            yield event.plain_result(f'解析文章失败：{exc}')

    async def _safe_summary_card(self, **kwargs):
        try:
            return await WeChatArticleRenderer.render_markdown_summary_card(**kwargs)
        except Exception as exc:
            logger.warning("Summary card failed; retaining text: %s", exc)
            return ''

    async def _safe_article_images(self, **kwargs):
        try:
            return await WeChatArticleRenderer.render_direct_wechat_article(**kwargs)
        except Exception as exc:
            logger.warning("Article screenshot failed; retaining source text: %s", exc)
            return []

    async def terminate(self):
        from .renderer import close_browser
        await close_browser()
