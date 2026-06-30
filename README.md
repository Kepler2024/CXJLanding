# SoMark 解析 vs 通用大模型 OCR · 同台对战

一个 Gradio 应用：上传同一份排版复杂的文档（PDF / 图片），让 **SoMark 解析** 与 **通用大模型（Claude）** 在同一份文档上同台对战。

- **左路**：调用 SoMark 的 `/parse`（异步 `parse/async` + `parse/async_check`）API 得到 Markdown。
- **右路**：对接多模态大模型（Claude），让它直接把同一份文档 OCR 成 Markdown。
- 两路输出都用 [`somarkdown`](https://github.com/SoMarkAI/gradio_somarkdown) 渲染，公式 / 表格 / 代码块正确可视化。
- 并排 side-by-side，并提供按行高亮的差异视图。
- 底部再调一个大模型当 **裁判**：对两份输出打分（满分 10）+ 给出三条差异点评（公式准确性、表格结构还原、阅读顺序）。

## 目录结构

| 文件 | 说明 |
|---|---|
| `app.py` | Gradio 主程序（上传首页、并排渲染、差异高亮、裁判面板） |
| `somark_client.py` | SoMark 异步解析客户端（左路） |
| `llm_client.py` | 通用大模型 OCR + 裁判（右路 / 底部） |
| `log_config.py` | 日志配置：带时间日期、按天自动轮转 |
| `Dockerfile` / `docker-compose.yml` | 容器化部署 |

## 配置

复制 `.env.example` 为 `.env` 并填写两组 API key 与 base url：

```bash
cp .env.example .env
```

```
SOMARK_API_KEY=sk-***
SOMARK_BASE_URL=https://somark.tech/api/v1
ANTHROPIC_API_KEY=sk-ant-***
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

## 本地运行

```bash
pip install -r requirements.txt
python app.py
# 打开 http://localhost:7860
```

## Docker 部署（hope 服务器）

采用**端口映射**方式（不使用 `network: host`），具备**自动重启**，日志**自动轮转**并持久化到宿主机 `./logs`：

```bash
docker compose up -d --build
# 对外端口可用 HOST_PORT 覆盖，默认 7860
HOST_PORT=8080 docker compose up -d --build

# 查看日志（容器内按天轮转的文件在 ./logs/app.log，旧文件后缀 .YYYY-MM-DD）
docker compose logs -f
tail -f logs/app.log
```

- **端口映射**：`docker-compose.yml` 中 `ports: ["${HOST_PORT:-7860}:7860"]`。
- **自动重启**：`restart: unless-stopped`。
- **日志轮转**：应用层 `TimedRotatingFileHandler` 按天轮转保留 14 天；容器层 `json-file` 驱动按大小轮转。每条日志均以 `YYYY-MM-DD HH:MM:SS` 时间日期开头。

## 说明

- 右路（通用大模型直连 OCR）支持 PDF 与常见图片（PNG/JPG/WebP/GIF）。SoMark 还支持 Word/PPT/Excel。
- 左右两路在后台并行执行，缩短等待时间。
