"""SoMark 异步解析客户端（左路）。

流程：
1. POST {base}/parse/async 提交任务，立即返回 task_id。
2. POST {base}/parse/async_check 轮询任务状态，直到 SUCCESS / FAILED。
3. 从结果中读取 markdown 输出。

参考：async.md / async_check.md
"""
import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

# 元素输出格式：公式用 latex（KaTeX 可渲染），表格用 html，图片用 url
ELEMENT_FORMATS = {
    "image": "url",
    "formula": "latex",
    "table": "html",
    "cs": "image",
}

# 特色功能配置：开启图像理解、表格图片等，提升排版还原度
FEATURE_CONFIG = {
    "enable_text_cross_page": True,
    "enable_table_cross_page": True,
    "enable_title_level_recognition": True,
    "enable_inline_image": False,
    "enable_table_image": True,
    "enable_image_understanding": True,
    "keep_header_footer": False,
}


class SoMarkError(RuntimeError):
    """SoMark 调用失败。"""


def _base_url() -> str:
    return os.getenv("SOMARK_BASE_URL", "https://somark.tech/api/v1").rstrip("/")


def _api_key() -> str:
    key = os.getenv("SOMARK_API_KEY", "").strip()
    if not key:
        raise SoMarkError("未配置 SOMARK_API_KEY，请在 .env 中填写。")
    return key


def submit_task(file_path: str, timeout: int = 60) -> str:
    """提交解析任务，返回 task_id。"""
    url = f"{_base_url()}/parse/async"
    data = {
        "api_key": _api_key(),
        "output_formats": ["markdown", "json"],
        "element_formats": json.dumps(ELEMENT_FORMATS),
        "feature_config": json.dumps(FEATURE_CONFIG),
    }
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        files = {"file": (filename, f)}
        logger.info("SoMark 提交任务: %s", filename)
        resp = requests.post(url, data=data, files=files, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise SoMarkError(f"提交任务失败: {payload.get('message')} (code={payload.get('code')})")
    task_id = payload["data"]["task_id"]
    logger.info("SoMark 任务已提交, task_id=%s", task_id)
    return task_id


def poll_result(task_id: str, interval: float = 4.0, max_wait: float = 600.0) -> dict:
    """轮询任务结果，返回 result 字典（含 outputs）。"""
    url = f"{_base_url()}/parse/async_check"
    deadline = time.time() + max_wait
    while True:
        resp = requests.post(
            url, data={"task_id": task_id, "api_key": _api_key()}, timeout=60
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise SoMarkError(f"查询失败: {payload.get('message')} (code={payload.get('code')})")
        status = payload["data"]["status"]
        logger.info("SoMark 任务 %s 状态: %s", task_id, status)
        if status == "SUCCESS":
            return payload["data"]["result"]
        if status == "FAILED":
            raise SoMarkError("SoMark 解析失败 (status=FAILED)")
        if time.time() > deadline:
            raise SoMarkError(f"SoMark 解析超时（超过 {max_wait:.0f}s）")
        time.sleep(interval)


def extract_markdown(file_path: str) -> str:
    """端到端：提交 + 轮询，返回 markdown 文本。"""
    task_id = submit_task(file_path)
    result = poll_result(task_id)
    outputs = (result or {}).get("outputs", {})
    markdown = outputs.get("markdown")
    if not markdown:
        raise SoMarkError("SoMark 返回结果中未找到 markdown 字段。")
    logger.info("SoMark 解析完成，markdown 长度=%d", len(markdown))
    return markdown
