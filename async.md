# 异步解析 — 提交任务

提交文件解析任务，立即返回 task_id，文档在后台处理

Source: https://docs.somark.tech/api-reference/endpoint/async-submit

## Page content

接口端点异步解析 — 提交任务提交文件解析任务，立即返回 task_id，文档在后台处理POST/parse/async试一试PythonPythonimport json
import requests

url = "https://somark.tech/api/v1/parse/async"

data = {
    "output_formats": ["markdown", "json"],
    "api_key": "sk-***",
    "element_formats": json.dumps({
        "image": "url",
        "formula": "latex",
        "table": "html",
        "cs": "image",
    }),
    "feature_config": json.dumps({
        "enable_text_cross_page": False,
        "enable_table_cross_page": False,
        "enable_title_level_recognition": False,
        "enable_inline_image": False,
        "enable_table_image": True,
        "enable_image_understanding": True,
        "keep_header_footer": False,
    }),
}

files = {"file": ("example.pdf", open("example.pdf", "rb"))}

response = requests.post(url, data=data, files=files)
task_id = response.json()["data"]["task_id"]
print(f"任务已提交，task_id: {task_id}")200{
  "code": 0,
  "message": "任务已提交",
  "data": {
    "task_id": "c5e6c983f28a4e6eb5d6c061343a8642",
    "status": "QUEUING"
  }
}路径变更：该接口路径已从 /extract/async 更改为 /parse/async。旧路径将于 2026-12-31 停用，请在此之前迁移至新路径。
参数变更：extract_config 已更名为 feature_config。请将请求中的 extract_config 字段替换为 feature_config。
异步解析需要配合两个接口一起使用，单独调用提交任务接口不会直接返回解析结果。

调用当前接口提交任务，接口会立即返回 task_id。
使用这个 task_id 调用结果查询接口轮询任务状态。
当状态变为成功后，再从结果查询接口读取解析结果。建议轮询间隔为 3~5 秒。

output_formats 、 element_formats 和 feature_config 的参数说明与同步解析相同；如果你要看鉴权、限制和模式选择，回到 API 概览。请求体multipart/form-datafilefile必填待解析的文件，支持 PDF、图片、Word、PPT 和 Excel 格式api_keystring必填API 密钥，格式 sk-***output_formatsenum<string>[]输出格式，可多选。不传时默认为 ["markdown", "json"]。支持 json / markdown / zip，其中 zip 将所有输出文件打包为压缩包可用选项: json, markdown, zip element_formatsobject元素格式配置，控制各类元素的输出格式Show child attributesfeature_configobject特色功能配置（参数已从 extract_config 更名为 feature_config）Show child attributes响应200 - application/json任务提交成功codeinteger状态码，0 为成功，非 0 见错误码示例:0messagestring示例:"任务已提交"dataobjectHide child attributesdata.task_idstring任务 ID，用于后续轮询示例:"c5e6c983f28a4e6eb5d6c061343a8642"data.statusstring初始状态，固定为 QUEUING示例:"QUEUING"同步解析异步解析 — 查询结果⌘Igithub技术支持This documentation is built and hosted on Mintlify, a developer documentation platform
