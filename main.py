# -*- coding: utf-8 -*-
"""
微信公众号文章全文读取、高保真公式排版与 AI 深度总结插件
支持：
  1. 命令触发：/wx <链接>、/公众号 <链接>
  2. 群聊/私聊链接自动识别
  3. LLM Function Calling (Agent Tool)：@机器人 并发送公众号链接或要求精读时，大模型自主调用
  4. 智能自适应合并转发模式：
     - 当文章无数学公式且开启 fast_text_when_no_formula：
         * 节点 1：以下是对微信公众号 (链接) 内容的解析和总结：
         * 节点 2：纯文本 AI 深度精读总结
         * 后续节点：公众号原文全部正文纯文本（长文自动按段落切分节点）
     - 当文章包含数学公式：
         * 节点 1：以下是对微信公众号 (链接) 内容的解析和总结：
         * 节点 2：总结的图（使用 Markdown + KaTeX 渲染的高颜值卡片）
         * 后续节点：公众号原文的高清图片解析（正文高清长图切片）
"""

import os
import asyncio
import logging
from typing import Optional, List, AsyncGenerator
from astrbot.api.star import Star, register
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.message_components import Plain, Image, Node, Nodes
from astrbot.api.all import Context, AstrBotConfig

from .fetcher import WeChatArticleFetcher
from .summarizer import WeChatArticleSummarizer
from .renderer import WeChatArticleRenderer

logger = logging.getLogger(__name__)

@register(
    name="astrbot_plugin_wechat_article",
    author="VesperaZephyr",
    desc="自动读取微信公众号文章全部内容，保留数学公式，合并转发高清长图与 Markdown 深度总结导读",
    version="1.3.1",
    repo="https://github.com/VesperaZephyr/astrbot_plugin_wechat_article"
)
class WeChatArticlePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._handling_urls = set()
        logger.info("[WeChatArticlePlugin] 微信公众号全文精读与公式总结插件 v1.3.1 已加载。")

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
    async def tool_read_wechat(self, event: AstrMessageEvent, url: str) -> AsyncGenerator[MessageEventResult, None]:
        """读取微信公众号文章全部内容，保留数学公式，生成高清长图和AI总结导读，并以合并转发消息发送。当用户发送微信公众号文章链接(mp.weixin.qq.com)或要求读取、解析、总结微信公众号文章时必须调用此工具。

        Args:
            url(string): 必填。微信公众号文章链接，必须是以 https://mp.weixin.qq.com/ 开头的完整URL。
        """
        urls = WeChatArticleFetcher.extract_urls(url or event.message_str)
        if not urls:
            yield event.plain_result(f"抱歉，未能在提供的参数中识别到合法的微信公众号文章链接：{url}")
            return

        target_url = urls[0]
        async for res in self._process_article(event, target_url):
            yield res

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def auto_detect_wechat(self, event: AstrMessageEvent):
        """自动检测群聊/私聊中的微信文章链接"""
        # 如果是斜杠指令触发，跳过
        raw_text = event.message_str or ""
        if raw_text.strip().startswith("/"):
            return

        if not self.config.get("enable_auto_detect", True):
            return

        if not self._is_group_allowed(event):
            return

        urls = WeChatArticleFetcher.extract_urls(raw_text)
        if not urls:
            return

        target_url = urls[0]
        # 防重复触发
        if target_url in self._handling_urls:
            return

        self._handling_urls.add(target_url)
        try:
            logger.info(f"[WeChatArticlePlugin] 自动检测到微信文章链接: {target_url}")
            async for res in self._process_article(event, target_url):
                yield res
        finally:
            self._handling_urls.discard(target_url)

    @staticmethod
    def _split_text_to_chunks(text: str, max_chars: int = 1800) -> List[str]:
        """按自然段落拆分超长文本，每段不超过 max_chars"""
        paragraphs = text.split("\n\n")
        chunks = []
        current = []
        current_len = 0

        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            if current_len + len(p_clean) > max_chars and current:
                chunks.append("\n\n".join(current))
                current = [p_clean]
                current_len = len(p_clean)
            else:
                current.append(p_clean)
                current_len += len(p_clean)

        if current:
            chunks.append("\n\n".join(current))
        return chunks or [text]

    async def _process_article(self, event: AstrMessageEvent, url: str):
        """核心业务流程：抓取 -> 判断公式 -> 智能路由(极速纯文本模式 / 高清长图模式) -> 合并转发发送"""
        yield event.plain_result("📖 正在读取微信公众号文章内容，请稍候...")

        try:
            # 1. 异步抓取文章与公式
            article_data = await WeChatArticleFetcher.fetch_article(url)
            if not article_data:
                yield event.plain_result("❌ 抓取文章失败：无法获取微信正文内容，请检查链接是否有效。")
                return

            title = article_data.get("title", "微信文章")
            author = article_data.get("author", "微信公众号")
            publish_time = article_data.get("publish_time", "")
            formula_count = article_data.get("formula_count", 0)
            full_text = article_data.get("full_text", "")

            # 2. 生成 AI 深度总结 (极速模式)
            summary_style = self.config.get("summary_style", "academic_math")
            md_summary_text = await WeChatArticleSummarizer.generate_markdown_summary(
                context=self.context,
                article_data=article_data,
                style=summary_style,
            )

            bot_uin = str(event.get_self_id() or "10000")
            bot_name = "公众号深度解析"
            forward_nodes = []

            # 节点 1：通用提示文字
            first_msg_text = f"以下是对微信公众号 {url} 内容的解析和总结："
            forward_nodes.append(
                Node(content=[Plain(first_msg_text)], name=bot_name, uin=bot_uin)
            )

            # 判断是否走【无公式极速纯文本模式】
            fast_text_mode = self.config.get("fast_text_when_no_formula", True)
            if formula_count == 0 and fast_text_mode:
                logger.info(f"[WeChatArticlePlugin] 文章无数学公式，触发【极速纯文本合并转发】(跳过长图截图)")

                # 节点 2：纯文本总结
                summary_node_text = (
                    f"📑【AI 深度导读】《{title}》\n"
                    f"👤 来源：{author}  "
                    f"{f'📅 {publish_time}' if publish_time else ''}\n"
                    f"{'-' * 35}\n"
                    f"{md_summary_text}"
                )
                forward_nodes.append(
                    Node(content=[Plain(summary_node_text)], name=f"AI 深度总结 · {author}", uin=bot_uin)
                )

                # 后续节点：正文纯文本分段
                chunks = self._split_text_to_chunks(full_text, max_chars=1800)
                total_chunks = len(chunks)
                for idx, chunk in enumerate(chunks, 1):
                    node_label = f"公众号原文 ({idx}/{total_chunks})" if total_chunks > 1 else "公众号原文"
                    forward_nodes.append(
                        Node(content=[Plain(chunk)], name=node_label, uin=bot_uin)
                    )

            else:
                # 包含数学公式，走【高保真长图与卡片图模式】
                logger.info(f"[WeChatArticlePlugin] 检测到包含 {formula_count} 个数学公式，走【高保真长图渲染模式】")

                # 节点 2：Markdown + KaTeX 渲染总结卡片图
                summary_card_path = await WeChatArticleRenderer.render_markdown_summary_card(
                    markdown_text=md_summary_text,
                    title=title,
                    author=author,
                    publish_time=publish_time,
                    formula_count=formula_count
                )
                if summary_card_path and os.path.exists(summary_card_path):
                    forward_nodes.append(
                        Node(content=[Image.fromFileSystem(summary_card_path)], name=f"AI 深度总结导读 · {author}", uin=bot_uin)
                    )

                # 后续节点：正文高清长图
                max_slice_h = int(self.config.get("max_slice_height", 12000))
                article_img_paths = await WeChatArticleRenderer.render_article_image(
                    article_data,
                    max_slice_height=max_slice_h
                )
                total_parts = len(article_img_paths)
                for idx, p in enumerate(article_img_paths, 1):
                    if os.path.exists(p):
                        part_label = f"公众号原文解析 ({idx}/{total_parts})" if total_parts > 1 else "公众号原文解析"
                        forward_nodes.append(
                            Node(content=[Image.fromFileSystem(p)], name=part_label, uin=bot_uin)
                        )

            # 发送合并转发
            if forward_nodes:
                yield event.chain_result([Nodes(forward_nodes)])
            else:
                yield event.plain_result("❌ 未能生成有效的合并转发节点内容。")

        except Exception as e:
            logger.error(f"[WeChatArticlePlugin] 处理文章异常: {e}", exc_info=True)
            yield event.plain_result(f"❌ 解析文章时发生异常: {str(e)}")
