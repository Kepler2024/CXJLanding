# 异步解析 — 查询结果

根据 task_id 查询异步任务状态与解析结果

Source: https://docs.somark.tech/api-reference/endpoint/async-check

## Page content

接口端点异步解析 — 查询结果根据 task_id 查询异步任务状态与解析结果POST/parse/async_check试一试PythonPythonimport time
import requests

url = "https://somark.tech/api/v1/parse/async_check"
task_id = "c5e6c983f28a4e6eb5d6c061343a8642"

while True:
    response = requests.post(url, data={
        "task_id": task_id,
        "api_key": "sk-***",
    })
    result = response.json()
    status = result["data"]["status"]

    if status == "SUCCESS":
        print(result["data"]["result"])
        break
    elif status == "FAILED":
        print("解析失败")
        break

    time.sleep(3)200{
  "code": 0,
  "message": "查询成功",
  "data": {
    "record_id": 12345,
    "task_id": "c5e6c983f28a4e6eb5d6c061343a8642",
    "status": "SUCCESS",
    "file_name": "document.pdf",
    "metadata": {
      "page_num": 5,
      "file_type": ".pdf"
    },
    "result": {
      "file_name": "document.pdf",
      "outputs": {
        "markdown": "# 第一章 引言\n\n本文档介绍了...",
        "json": {
          "pages": [
            {
              "page_num": 0,
              "blocks": [
                {
                  "idx": 0,
                  "type": "title",
                  "bbox": [
                    72,
                    50,
                    540,
                    80
                  ],
                  "content": "第一章 引言",
                  "format": "text",
                  "captions": [],
                  "img_url": "",
                  "title_level": 1
                },
                {
                  "idx": 1,
                  "type": "text",
                  "bbox": [
                    72,
                    100,
                    540,
                    200
                  ],
                  "content": "本文档介绍了...",
                  "format": "text",
                  "captions": [],
                  "img_url": ""
                }
              ],
              "page_size": {
                "h": 1684,
                "w": 1190
              },
              "merge_content_from_pre_page": false
            }
          ]
        }
      }
    }
  }
}路径变更：该接口路径已从 /extract/async_check 更改为 /parse/async_check。旧路径将于 2026-12-31 停用，请在此之前迁移至新路径。
任务状态
status含义QUEUING排队等待处理PROCESSING解析进行中SUCCESS解析成功，result 字段有值FAILED解析失败
建议每隔 3~5 秒轮询一次，直到 status 为 SUCCESS 或 FAILED。如果你还没提交任务，先看 异步解析 — 提交任务；如果你不想轮询，可以改用 同步解析；返回异常时继续看错误码说明。请求体multipart/form-datatask_idstring必填提交任务时返回的任务 IDapi_keystring必填API 密钥，格式 sk-***响应200 - application/json查询成功codeinteger状态码，0 为成功，非 0 见错误码示例:0messagestring示例:"查询成功"dataobjectHide child attributesdata.record_idinteger解析记录 ID示例:12345data.task_idstring任务 ID示例:"c5e6c983f28a4e6eb5d6c061343a8642"data.statusenum<string>任务状态可用选项: QUEUING, PROCESSING, SUCCESS, FAILED 示例:"SUCCESS"data.file_namestring文件名示例:"document.pdf"data.metadataobjectShow child attributesdata.resultobject解析结果，status 为 SUCCESS 时有值，其余为 nullShow child attributes异步解析 — 提交任务用量查询⌘Igithub技术支持This documentation is built and hosted on Mintlify, a developer documentation platform
