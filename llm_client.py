"""通用大模型客户端（右路 视觉转写 + 底部裁判），基于 Anthropic Claude。

- read_to_markdown: 让多模态视觉大模型直接「看」同一份文档，转写为 Markdown。
  PDF 优先用 Claude 原生 PDF 能力（视觉 + 文本层）；若对端拒绝，则逐页渲染成图片
  再交给视觉模型，确保走的是视觉路线而非传统 OCR。
- judge: 再调一个大模型当「裁判」，对两份输出打分（满分 10）并给出三条差异点评。
"""
import base64
import logging
import mimetypes
import os
from typing import List

import anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Claude 支持作为 document 直接处理的类型
_PDF_TYPE = "application/pdf"
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# PDF 逐页渲染时的参数
_PDF_RENDER_DPI = 150
_PDF_MAX_PAGES = 30

READ_PROMPT = (
    "请仔细阅读这份文档（PDF 或图片），把它的全部内容完整转写为 GitHub 风格的 Markdown，要求：\n"
    "1. 数学公式使用 LaTeX，行内用 $...$，行间用 $$...$$；\n"
    "2. 表格还原为 Markdown 表格（复杂表格可用 HTML <table>）；\n"
    "3. 代码块使用三反引号围栏并标注语言；\n"
    "4. 保持原文的标题层级与阅读顺序；\n"
    "5. 只输出 Markdown 内容本身，不要任何解释或开场白。"
)


def _client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未配置 ANTHROPIC_API_KEY，请在 .env 中填写。")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
    return anthropic.Anthropic(api_key=api_key, base_url=base_url)


def _model() -> str:
    return os.getenv("LLM_MODEL", "claude-opus-4-8")


def _pdf_document_block(file_path: str) -> dict:
    """Claude 原生 PDF 能力：把整份 PDF 作为 document 块（视觉 + 文本层）。"""
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": _PDF_TYPE, "data": data},
    }


def _image_block(file_path: str, mime: str) -> dict:
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}


def _pdf_to_image_blocks(file_path: str) -> List[dict]:
    """逐页把 PDF 渲染成 PNG，交给视觉模型（不依赖系统库，PyMuPDF 自带渲染）。"""
    import fitz  # PyMuPDF

    blocks: List[dict] = []
    with fitz.open(file_path) as doc:
        total = doc.page_count
        for i in range(min(total, _PDF_MAX_PAGES)):
            pix = doc.load_page(i).get_pixmap(dpi=_PDF_RENDER_DPI)
            png = pix.tobytes("png")
            b64 = base64.standard_b64encode(png).decode("utf-8")
            blocks.append(
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}
            )
    if total > _PDF_MAX_PAGES:
        logger.warning("PDF 共 %d 页，仅渲染前 %d 页", total, _PDF_MAX_PAGES)
    logger.info("PDF 已渲染为 %d 张页面图片", len(blocks))
    return blocks


def _generate_markdown(doc_blocks: List[dict]) -> str:
    """把内容块 + 指令发给视觉大模型，流式收集 Markdown。"""
    content = list(doc_blocks) + [{"type": "text", "text": READ_PROMPT}]
    parts: List[str] = []
    with _client().messages.stream(
        model=_model(),
        max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)
    return "".join(parts).strip()


def read_to_markdown(file_path: str) -> str:
    """让视觉大模型直接阅读文档并转写为 Markdown。"""
    mime, _ = mimetypes.guess_type(file_path)
    name = os.path.basename(file_path)

    if mime == _PDF_TYPE:
        logger.info("Claude 视觉转写开始（PDF 原生能力）: %s", name)
        try:
            md = _generate_markdown([_pdf_document_block(file_path)])
        except anthropic.BadRequestError as exc:
            # 对端不支持/拒绝 PDF document 时，回退到逐页渲染走视觉
            logger.warning("原生 PDF 被拒绝，回退为逐页渲染视觉转写：%s", exc)
            md = _generate_markdown(_pdf_to_image_blocks(file_path))
    elif mime in _IMAGE_TYPES:
        logger.info("Claude 视觉转写开始（图片）: %s", name)
        md = _generate_markdown([_image_block(file_path, mime)])
    else:
        raise ValueError(
            f"视觉大模型仅支持 PDF 与常见图片格式，当前文件类型为 {mime or '未知'}。"
        )

    logger.info("Claude 视觉转写完成，markdown 长度=%d", len(md))
    return md


class JudgeResult(BaseModel):
    """裁判输出结构。三条点评拆成三个固定字段，避免模型把数组拆碎。"""

    somark_score: int = Field(ge=0, le=10, description="SoMark 输出得分，满分 10")
    claude_score: int = Field(ge=0, le=10, description="通用大模型输出得分，满分 10")
    comment_formula: str = Field(
        description="【公式准确性】维度的差异点评，用一段连续的话，不要分行或编号"
    )
    comment_table: str = Field(
        description="【表格结构还原】维度的差异点评，用一段连续的话，不要分行或编号"
    )
    comment_order: str = Field(
        description="【阅读顺序】维度的差异点评，用一段连续的话，不要分行或编号"
    )


JUDGE_PROMPT = """你是一名严格的文档解析评审专家。下面是同一份文档被两套系统解析得到的 Markdown：

【A：SoMark 解析结果】
{somark}

【B：通用大模型 视觉转写结果】
{claude}

请对比 A 与 B，并各给出 0–10 分（somark_score / claude_score）。
然后分别从三个维度各写**一段连续的话**点评（每段都不要换行、不要分点、不要编号）：
- comment_formula：公式准确性（谁的公式 / 符号更准，举例说明）
- comment_table：表格结构还原（跨行跨列、合并单元格是否还原正确）
- comment_order：阅读顺序（标题层级、分页、阅读顺序是否忠实原文）
请客观、具体，指出谁更好以及原因。"""


def judge(somark_md: str, claude_md: str) -> JudgeResult:
    """调用裁判模型，对两份输出打分并给出三个维度的差异点评。"""
    logger.info("裁判模型开始评审")
    prompt = JUDGE_PROMPT.format(somark=somark_md or "(空)", claude=claude_md or "(空)")
    resp = _client().messages.parse(
        model=_model(),
        max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
        output_format=JudgeResult,
    )
    result = resp.parsed_output
    if result is None:
        raise RuntimeError("裁判模型未返回有效的结构化结果。")
    logger.info(
        "裁判完成: SoMark=%d, Claude=%d", result.somark_score, result.claude_score
    )
    return result
