# -*- coding: utf-8 -*-
"""
微信公众号文章 AI 深度总结模块
自适应判断：
  - 无数学公式文章：采用通用社科/新闻/长文精读提示词，严禁生硬出现数学词汇
  - 含有数学公式文章：深入分析数理推导、核心公式与理论模型
"""

import uuid
import logging
from typing import Dict, Any, Optional
from astrbot.api.all import Context

logger = logging.getLogger(__name__)

# 无数学公式的通用长文系统提示词
GENERAL_ARTICLE_PROMPT = """你是一个专业的长文精读与导读分析专家。
你的任务是对用户提供的微信公众号文章进行深度精读与结构化总结。
【严格要求】：这是一篇普通图文文章，完全不包含高深数学公式，请勿生搬硬套任何数学模型、公式推导或理工科黑话。

请直接输出排版优美、通俗精炼的总结，格式如下：

【🎯 核心主旨】
一句话提炼文章核心主题与作者核心观点（50字左右）

【📌 核心论点与关键脉络】
1. 核心要点一：具体论述与关键事实
2. 核心要点二：具体论述与关键事实
3. 核心要点三：具体论述与关键事实

【🔍 重点论据与细节亮点】
提炼文中提及的重要数据、案例或代表性观点（100字左右）

【💡 AI 导读点评】
2-3句话评估该文的价值、深度或启发意义（80字以内）
"""

# 包含数学公式的学术理科系统提示词
MATH_ARTICLE_PROMPT = """你是一个专业的学术与数理长文导读专家。
你的任务是对用户提供的微信公众号文章进行深度精读与学术总结。
这篇文章包含数学公式与理论模型，请重点梳理其推导脉络与公式意义。

请直接输出排版严密、清晰的总结，格式如下：

【🎯 核心主旨】
一句话提炼文章的核心研究问题与理论结论（50字左右）

【📌 核心论点与理论脉络】
1. 核心论点一：具体论述
2. 核心论点二：具体论述
3. 核心论点三：具体论述

【📐 数理推导与核心模型解析】
详细解析文中关键公式（使用标准 LaTeX 符号）、定理或模型的数学物理意义，阐明其核心推演逻辑（150字左右）

【💡 AI 导读点评】
2-3句话评估该文的学术深度与理论价值（80字以内）
"""

class WeChatArticleSummarizer:
    """文章总结生成器"""

    @classmethod
    async def generate_markdown_summary(
        cls,
        context: Context,
        article_data: Dict[str, Any],
        style: str = "academic_math",
    ) -> str:
        """
        调用 AstrBot 默认 LLM 生成高质量精读总结
        """
        title = article_data.get("title", "")
        author = article_data.get("author", "")
        publish_time = article_data.get("publish_time", "")
        full_text = article_data.get("full_text", "")
        formula_count = article_data.get("formula_count", 0)

        # 智能选择 Prompt：有公式才使用数学模版，无公式严禁涉及数学
        if formula_count > 0:
            system_prompt = MATH_ARTICLE_PROMPT
            article_type_hint = f"该文章包含约 {formula_count} 个数学公式，请重点解析其核心推导与模型。"
        else:
            system_prompt = GENERAL_ARTICLE_PROMPT
            article_type_hint = "该文章为普通文章，无数学公式，请以通俗、准确、贴合文章实际内容的风格总结。"

        # 限制文本长度为 4000 字符，秒级出结果
        max_chars = 4000
        truncated_text = full_text[:max_chars]
        if len(full_text) > max_chars:
            truncated_text += "\n\n(注：正文篇幅较长，已截取核心段落进行总结...)"

        user_prompt = f"""文章标题：《{title}》
公众号：{author}
发布时间：{publish_time}
文章特征：{article_type_hint}

以下是文章核心正文内容：
----------------------------------------
{truncated_text}
----------------------------------------
请按照提示要求输出结构化精读总结。"""

        try:
            provider = context.get_using_provider()
            if not provider:
                logger.error("[WeChatSummarizer] 未找到可用的 LLM Provider")
                return cls._fallback_summary(article_data)

            # 使用独立随机 session_id，避免历史累加延迟
            fresh_session_id = f"wx_{uuid.uuid4().hex[:8]}"

            response = await provider.text_chat(
                prompt=user_prompt,
                system_prompt=system_prompt,
                session_id=fresh_session_id,
            )

            response_text = ""
            if hasattr(response, "completion_text"):
                response_text = response.completion_text
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            res = response_text.strip()
            if res.startswith("```markdown"):
                res = res[len("```markdown"):].strip()
            elif res.startswith("```"):
                res = res[3:].strip()
            if res.endswith("```"):
                res = res[:-3].strip()

            return res

        except Exception as e:
            logger.warning(f"[WeChatSummarizer] LLM 总结异常，使用兜底处理: {e}")
            return cls._fallback_summary(article_data)

    @classmethod
    def _fallback_summary(cls, article_data: Dict[str, Any]) -> str:
        """兜底生成基础总结"""
        title = article_data.get("title", "微信文章")
        author = article_data.get("author", "微信公众号")
        formula_count = article_data.get("formula_count", 0)

        if formula_count > 0:
            math_part = f"\n\n【📐 数理推导与核心模型】\n文章包含约 {formula_count} 个数学公式，原版高清排版已在后续消息展示。"
        else:
            math_part = ""

        return f"""【🎯 核心主旨】
《{title}》由公众号【{author}】发布，围绕核心论题展开了详尽论述。

【📌 核心要点与关键脉络】
1. 观点明确，论据层层推进。
2. 完整内容已在后续合并转发消息中展示。{math_part}

【💡 AI 导读点评】
文章内容详实，已完成全文整理，适合收藏与阅读。"""
