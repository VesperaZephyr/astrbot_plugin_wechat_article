# -*- coding: utf-8 -*-
"""
微信公众号数学公式保真处理器
处理包含 <span data-formula="..."> 和 <section data-formula="..."> 的数学公式
"""

import re
from typing import Tuple, Dict, Any
from bs4 import BeautifulSoup, Tag

class WeChatFormulaProcessor:
    """处理微信公众号中的数学公式"""

    @staticmethod
    def process_for_rendering(soup: BeautifulSoup) -> int:
        """
        处理 HTML DOM 中的数学公式，以便在 Playwright 中完美渲染长图。
        - 确保内联 SVG 公式有正确的 vertical-align，避免文字基线错位
        - 确保块级公式居中显示并有适当的上下边距
        - 为没有 SVG 渲染的公式（纯 data-formula）注入 KaTeX 兼容占位
        返回检测并处理的公式数量
        """
        formula_count = 0

        # 1. 查找所有带 data-formula 的标签
        formula_elements = soup.find_all(attrs={"data-formula": True})
        formula_count = len(formula_elements)

        for el in formula_elements:
            formula_type = el.get("data-formula-type", "")
            latex_code = el.get("data-formula", "").strip()

            # 给公式元素添加统一的 class 便于 CSS 控制
            current_class = el.get("class", [])
            if isinstance(current_class, str):
                current_class = [current_class]

            if formula_type == "inline-equation" or el.name == "span":
                current_class.append("wx-formula-inline")
                el["class"] = current_class
                # 修复行内公式可能被微信默认样式挤压的问题
                style = el.get("style", "")
                if "vertical-align" not in style:
                    style += "; display: inline-block; vertical-align: -0.25ex;"
                el["style"] = style
            else:
                current_class.append("wx-formula-block")
                el["class"] = current_class
                style = el.get("style", "")
                if "text-align" not in style:
                    style += "; display: block; text-align: center; margin: 1em 0; overflow-x: auto;"
                el["style"] = style

            # 如果内部没有任何 SVG 或图片子元素，生成一个 KaTeX 渲染节点
            if not el.find(["svg", "img", "embed"]):
                math_span = soup.new_tag("span", **{"class": "katex-render-needed"})
                math_span.string = f"${latex_code}$" if "inline" in formula_type else f"$${latex_code}$$"
                el.append(math_span)

        return formula_count

    @staticmethod
    def extract_text_with_latex(soup: BeautifulSoup) -> str:
        """
        将正文提取为带有标准 LaTeX 公式 ($...$ 和 $$...$$) 的纯文本 / Markdown，
        专门供大模型 (LLM) 进行深度数学理解与总结。
        """
        # 深拷贝避免破坏原 DOM
        soup_copy = BeautifulSoup(str(soup), "html.parser")

        # 替换所有公式标签为标准 LaTeX 标记
        for el in soup_copy.find_all(attrs={"data-formula": True}):
            formula_type = el.get("data-formula-type", "")
            latex_code = el.get("data-formula", "").strip()
            if not latex_code:
                continue

            if formula_type == "inline-equation" or el.name == "span":
                el.replace_with(f" ${latex_code}$ ")
            else:
                el.replace_with(f"\n\n$${latex_code}$$\n\n")

        # 移除 script, style 等无用标签
        for tag in soup_copy(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # 替换图片为占位符提示
        for img in soup_copy.find_all("img"):
            alt = img.get("alt", "") or "图片"
            img.replace_with(f" [{alt}] ")

        # 提取整洁文本
        text = soup_copy.get_text(separator="\n", strip=True)
        # 去除多余的空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
