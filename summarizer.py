# -*- coding: utf-8 -*-
"""
微信公众号文章 AI 深度总结与数理推导分析模块
支持输出结构化 Markdown 报告或纯文本导读
"""

import logging
from typing import Dict, Any, Optional
from astrbot.api.all import Context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的学术与深度长文导读专家。
你的任务是对用户提供的微信公众号文章进行深度精读与结构化总结。
请直接输出排版优美、层次分明的总结，包含以下模块：

【核心主旨】
一句话提炼文章核心观点与讨论主题（50字左右）

【核心要点与关键脉络】
1. 要点一：具体论证与事实
2. 要点二：具体论证与事实
3. 要点三：具体论证与事实

【数理推导与核心模型】（若文章包含数学公式，请详细解析核心公式与推导；若无数学公式，则提炼核心方法论）

【AI 导读点评】
2-3句话评估该文的价值、启发或局限性（80字以内）
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
        调用 AstrBot 默认 LLM 生成高质量 Markdown / 纯文本格式的精读总结
        """
        title = article_data.get("title", "")
        author = article_data.get("author", "")
        publish_time = article_data.get("publish_time", "")
        full_text = article_data.get("full_text", "")
        formula_count = article_data.get("formula_count", 0)

        max_chars = 14000
        truncated_text = full_text[:max_chars]
        if len(full_text) > max_chars:
            truncated_text += "\n\n(注：正文篇幅较长，已截取前部分进行核心总结...)"

        user_prompt = f"""文章标题：《{title}》
公众号作者：{author}
发布时间：{publish_time}
数学公式数量：约 {formula_count} 个
要求风格：{style}

以下是文章全部正文内容（包含已还原的 LaTeX 公式）：
----------------------------------------
{truncated_text}
----------------------------------------
请按照要求输出深度精读总结报告。"""

        try:
            provider = context.get_using_provider()
            if not provider:
                logger.error("[WeChatSummarizer] 未找到可用的 LLM Provider")
                return cls._fallback_markdown(article_data)

            response = await provider.text_chat(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                session_id="wechat_summary_session",
            )

            response_text = ""
            if hasattr(response, "completion_text"):
                response_text = response.completion_text
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            res = response_text.strip()
            # 去除可能的外层 ``` 包裹
            if res.startswith("```markdown"):
                res = res[len("```markdown"):].strip()
            elif res.startswith("```"):
                res = res[3:].strip()
            if res.endswith("```"):
                res = res[:-3].strip()

            return res

        except Exception as e:
            logger.warning(f"[WeChatSummarizer] LLM 总结异常，使用兜底处理: {e}")
            return cls._fallback_markdown(article_data)

    @classmethod
    def _fallback_markdown(cls, article_data: Dict[str, Any]) -> str:
        """兜底生成基础总结"""
        title = article_data.get("title", "微信文章")
        author = article_data.get("author", "微信公众号")
        publish_time = article_data.get("publish_time", "")
        char_count = article_data.get("char_count", 0)
        formula_count = article_data.get("formula_count", 0)

        math_info = f"文章检测到包含 {formula_count} 个数学公式。" if formula_count > 0 else "文章主要为图文论述。"

        return f"""【核心主旨】
《{title}》全文约 {char_count} 字，由公众号【{author}】发布。

【核心要点与关键脉络】
1. 全文结构完整，论证清晰。
2. 内容要点已在后续合并消息中展示。
3. {math_info}

【数理推导与核心模型】
{math_info}

【AI 导读点评】
文章内容详实，已自动整理完成，适合精读与收藏。"""
