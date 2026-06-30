"""SoMark 解析 vs 通用大模型视觉转写 —— 同台对战 Gradio 应用。

首页上传一份排版复杂的文档（PDF / 图片）：
- 左路调用 SoMark /parse API 得到 Markdown；
- 右路用多模态视觉大模型直接阅读同一份文档转写为 Markdown；
两路并行执行、谁先完成谁先出结果（体现速度差异），都用 somarkdown 渲染并并排高亮差异，
底部再调一个大模型当裁判，对两份输出打分并给出三条差异点评。
"""
import difflib
import html
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from log_config import setup_logging  # noqa: E402  (需在 load_dotenv 后读取 LOG_DIR)

setup_logging()
logger = logging.getLogger("app")

from gradio_somarkdown import SoMarkDown  # noqa: E402
import llm_client  # noqa: E402
import somark_client  # noqa: E402

KATEX_OPTS = {"throwOnError": False}

SOMARK_NAME = "SoMark"
CLAUDE_NAME = "通用大模型视觉"

# 使用正常的系统无衬线字体（含中文），避免 Gradio 默认主题的怪异字体
NORMAL_FONT = [
    "system-ui",
    "-apple-system",
    "PingFang SC",
    "Microsoft YaHei",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "sans-serif",
]
THEME = gr.themes.Soft(
    font=NORMAL_FONT,
    primary_hue=gr.themes.colors.indigo,
).set(body_text_size="15px")

APP_CSS = """
/* 全局字体 */
.gradio-container, .gradio-container button, .gradio-container input,
.gradio-container textarea, .gradio-container label, .prose, .somarkdown {
  font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei",
    "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

/* 顶部标题 */
.app-header { padding: 6px 2px 2px; }
.app-title { font-size: 26px; font-weight: 800; margin: 0; letter-spacing: .3px; }
.app-sub { opacity: .72; font-size: 14px; margin-top: 6px; line-height: 1.6; }
.app-sub code { background: rgba(128,128,128,.18); padding: 1px 6px; border-radius: 5px; }

/* 状态徽章 */
.badge { display:inline-flex; align-items:center; gap:7px; padding:6px 13px;
  border-radius:999px; font-size:13px; font-weight:700; }
.badge-running { background:rgba(99,102,241,.16); color:#818cf8; }
.badge-ok      { background:rgba(34,197,94,.16);  color:#4ade80; }
.badge-fail    { background:rgba(239,68,68,.16);  color:#f87171; }
.spinner { width:12px; height:12px; border:2px solid currentColor;
  border-top-color:transparent; border-radius:50%; display:inline-block;
  animation:spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 速度对比条 */
.speed-wrap { border:1px solid rgba(128,128,128,.2); border-radius:14px;
  padding:16px 18px; margin:6px 0 2px; background:rgba(128,128,128,.05); }
.speed-title { font-weight:800; margin-bottom:12px; font-size:15px; }
.speed-row { display:flex; align-items:center; gap:12px; margin:9px 0; }
.speed-label { width:150px; font-size:13px; font-weight:700; }
.speed-track { flex:1; background:rgba(128,128,128,.12); border-radius:8px;
  overflow:hidden; height:28px; }
.speed-fill { height:100%; display:flex; align-items:center; justify-content:flex-end;
  padding:0 12px; color:#fff; font-size:12px; font-weight:800; border-radius:8px;
  white-space:nowrap; transition:width .5s ease; }
.speed-fill.somark { background:linear-gradient(90deg,#3b82f6,#2563eb); }
.speed-fill.claude { background:linear-gradient(90deg,#8b5cf6,#7c3aed); }
.speed-fill.fail   { background:#ef4444; }
.speed-note { margin-top:12px; font-size:13.5px; color:#f59e0b; font-weight:700; }

/* 裁判卡片 */
.judge-card { border:1px solid rgba(128,128,128,.2); border-radius:18px;
  padding:22px; margin-top:8px; background:rgba(128,128,128,.05); }
.judge-head { font-size:19px; font-weight:800; margin-bottom:18px; }
.score-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:22px; }
.score-col { border:1px solid rgba(128,128,128,.18); border-radius:14px;
  padding:16px 18px; background:rgba(128,128,128,.04); }
.score-name { font-size:13px; font-weight:700; opacity:.8; }
.score-num { font-size:38px; font-weight:800; line-height:1.05; margin:6px 0; }
.score-num.somark { color:#3b82f6; } .score-num.claude { color:#8b5cf6; }
.score-max { font-size:16px; opacity:.5; font-weight:700; margin-left:2px; }
.score-track { height:9px; background:rgba(128,128,128,.16); border-radius:6px;
  overflow:hidden; margin-top:8px; }
.score-fill { height:100%; border-radius:6px; transition:width .7s ease; }
.score-fill.somark { background:linear-gradient(90deg,#3b82f6,#2563eb); }
.score-fill.claude { background:linear-gradient(90deg,#8b5cf6,#7c3aed); }
.win-pill { float:right; font-size:12px; font-weight:800; padding:2px 9px;
  border-radius:999px; background:rgba(245,158,11,.18); color:#f59e0b; }
.comment-title { font-weight:800; margin:4px 0 12px; font-size:15px; }
.comment-card { display:flex; gap:13px; padding:13px 15px;
  border:1px solid rgba(128,128,128,.18); border-radius:12px; margin-bottom:10px;
  background:rgba(128,128,128,.04); }
.comment-idx { flex:0 0 28px; height:28px; border-radius:50%;
  background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; display:flex;
  align-items:center; justify-content:center; font-weight:800; font-size:14px; }
.comment-body { flex:1; font-size:14px; line-height:1.75; }
.comment-tag { display:inline-block; font-size:12px; font-weight:800;
  padding:2px 9px; border-radius:6px; margin-right:8px;
  background:rgba(99,102,241,.18); color:#818cf8; }

/* 提示 / 错误卡片 */
.warn-card { border:1px solid rgba(239,68,68,.3); background:rgba(239,68,68,.08);
  color:#f87171; border-radius:12px; padding:14px 16px; font-weight:600; }
.hint-card { opacity:.6; font-size:14px; padding:14px 0; }

/* 差异视图：白底深字，保证高亮可读 */
.diff-wrap { background:#ffffff; border-radius:10px; padding:8px; overflow:auto;
  max-height:600px; }
.diff-wrap, .diff-wrap td, .diff-wrap th { color:#111 !important;
  font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; }
.diff-wrap table.diff { border-collapse:collapse; width:100%; }
.diff-wrap .diff_header { background:#eee; }
.diff-wrap .diff_add { background:#a6f3a6; }
.diff-wrap .diff_chg { background:#f7f78a; }
.diff-wrap .diff_sub { background:#f7a6a6; }
"""


# ----------------------------- HTML 片段 -----------------------------

def _badge(name: str, status: str, elapsed: float = None) -> str:
    if status == "running":
        return f'<div class="badge badge-running"><span class="spinner"></span>{name} · 解析中…</div>'
    if status == "ok":
        return f'<div class="badge badge-ok">✅ {name} · {elapsed:.2f}s</div>'
    return f'<div class="badge badge-fail">❌ {name} · 失败</div>'


def _speed_bar(t_s, ok_s, t_c, ok_c) -> str:
    times = [t for t, ok in [(t_s, ok_s), (t_c, ok_c)] if ok and t]
    maxt = max(times) if times else 1.0
    faster = None
    if ok_s and ok_c:
        faster = "somark" if t_s <= t_c else "claude"

    def row(label, t, ok, key):
        if not ok:
            return (
                f'<div class="speed-row"><div class="speed-label">{label}</div>'
                f'<div class="speed-track"><div class="speed-fill fail" style="width:100%">失败</div></div></div>'
            )
        pct = max(10.0, (t / maxt) * 100.0)
        win = " 🥇" if faster == key else ""
        return (
            f'<div class="speed-row"><div class="speed-label">{label}{win}</div>'
            f'<div class="speed-track"><div class="speed-fill {key}" style="width:{pct:.0f}%">{t:.2f}s</div></div></div>'
        )

    rows = row(SOMARK_NAME, t_s, ok_s, "somark") + row(CLAUDE_NAME, t_c, ok_c, "claude")
    note = ""
    if faster and min(t_s, t_c) > 0:
        ratio = max(t_s, t_c) / min(t_s, t_c)
        fname = SOMARK_NAME if faster == "somark" else CLAUDE_NAME
        note = f'<div class="speed-note">⚡ {fname} 更快，约 {ratio:.1f}× （{min(t_s, t_c):.2f}s vs {max(t_s, t_c):.2f}s）</div>'
    return f'<div class="speed-wrap"><div class="speed-title">⏱️ 解析速度对比</div>{rows}{note}</div>'


def _judge_card(v: "llm_client.JudgeResult") -> str:
    def gauge(score, key, label, win):
        pill = '<span class="win-pill">领先</span>' if win else ""
        return (
            f'<div class="score-col"><div class="score-name">{label}{pill}</div>'
            f'<div class="score-num {key}">{score}<span class="score-max">/10</span></div>'
            f'<div class="score-track"><div class="score-fill {key}" style="width:{score * 10}%"></div></div></div>'
        )

    s_win = v.somark_score > v.claude_score
    c_win = v.claude_score > v.somark_score
    grid = gauge(v.somark_score, "somark", SOMARK_NAME, s_win) + gauge(
        v.claude_score, "claude", CLAUDE_NAME, c_win
    )

    dims = [
        ("公式准确性", v.comment_formula),
        ("表格结构还原", v.comment_table),
        ("阅读顺序", v.comment_order),
    ]

    def card(idx, label, text):
        body = html.escape((text or "").strip()).replace(chr(10), "<br>")
        return (
            f'<div class="comment-card"><div class="comment-idx">{idx}</div>'
            f'<div class="comment-body"><span class="comment-tag">{label}</span>{body}</div></div>'
        )

    comments = "".join(card(i + 1, lbl, txt) for i, (lbl, txt) in enumerate(dims))
    return (
        f'<div class="judge-card"><div class="judge-head">🧑‍⚖️ 裁判评分</div>'
        f'<div class="score-grid">{grid}</div>'
        f'<div class="comment-title">三条差异点评</div>{comments}</div>'
    )


def _judge_loading() -> str:
    return (
        '<div class="judge-card"><div class="badge badge-running">'
        '<span class="spinner"></span>裁判模型评分中…</div></div>'
    )


def _judge_placeholder() -> str:
    return '<div class="hint-card">上传文档并点击「开始对战」后，这里显示裁判评分与三条差异点评。</div>'


def _warn(msg: str) -> str:
    return f'<div class="warn-card">⚠️ {html.escape(msg)}</div>'


def _diff_html(left: str, right: str) -> str:
    differ = difflib.HtmlDiff(wrapcolumn=80)
    table = differ.make_table(
        (left or "").splitlines(),
        (right or "").splitlines(),
        fromdesc="SoMark",
        todesc="通用大模型视觉",
        context=False,
    )
    return f'<div class="diff-wrap">{table}</div>'


# ----------------------------- 主流程 -----------------------------

def _run_timed(fn, path):
    """执行解析并计时，返回 (markdown, error, elapsed)。"""
    t = time.perf_counter()
    try:
        return fn(path), None, time.perf_counter() - t
    except Exception as exc:  # noqa: BLE001
        logger.exception("解析失败")
        return "", str(exc), time.perf_counter() - t


def run_battle(file_obj):
    """生成器：左右并行，谁先完成谁先出结果，最后出速度对比与裁判评分。"""
    if file_obj is None:
        raise gr.Error("请先上传一份文档（PDF 或图片）。")
    path = file_obj if isinstance(file_obj, str) else file_obj.name
    logger.info("开始对战，文件: %s", path)

    state = {
        "left_status": _badge(SOMARK_NAME, "running"),
        "left_md": "",
        "right_status": _badge(CLAUDE_NAME, "running"),
        "right_md": "",
        "speed": "",
        "diff": "",
        "left_raw": "",
        "right_raw": "",
        "judge": _judge_placeholder(),
    }

    def snap():
        return (
            state["left_status"], state["left_md"], state["right_status"],
            state["right_md"], state["speed"], state["diff"],
            state["left_raw"], state["right_raw"], state["judge"],
        )

    yield snap()

    somark = {"md": "", "err": None, "t": 0.0}
    claude = {"md": "", "err": None, "t": 0.0}

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_map = {
            pool.submit(_run_timed, somark_client.extract_markdown, path): "somark",
            pool.submit(_run_timed, llm_client.read_to_markdown, path): "claude",
        }
        for fut in as_completed(fut_map):
            side = fut_map[fut]
            md, err, elapsed = fut.result()
            if side == "somark":
                somark.update(md=md, err=err, t=elapsed)
                state["left_md"] = md if md else _warn_text("SoMark 解析失败", err)
                state["left_raw"] = md
                state["left_status"] = _badge(SOMARK_NAME, "ok" if md else "fail", elapsed)
            else:
                claude.update(md=md, err=err, t=elapsed)
                state["right_md"] = md if md else _warn_text("视觉转写失败", err)
                state["right_raw"] = md
                state["right_status"] = _badge(CLAUDE_NAME, "ok" if md else "fail", elapsed)
            yield snap()

    # 速度对比 + 差异
    state["speed"] = _speed_bar(somark["t"], somark["err"] is None, claude["t"], claude["err"] is None)
    state["diff"] = _diff_html(somark["md"], claude["md"])
    yield snap()

    # 裁判
    if somark["md"] and claude["md"]:
        state["judge"] = _judge_loading()
        yield snap()
        try:
            verdict = llm_client.judge(somark["md"], claude["md"])
            state["judge"] = _judge_card(verdict)
        except Exception as exc:  # noqa: BLE001
            logger.exception("裁判评分失败")
            state["judge"] = _warn(f"裁判评分失败：{exc}")
    else:
        state["judge"] = _warn("有一路解析失败，无法进行裁判评分。")
    yield snap()


def _warn_text(title: str, err: str) -> str:
    return f"> ⚠️ **{title}**：{err}"


# ----------------------------- 页面 -----------------------------

def build_demo() -> gr.Blocks:
    with gr.Blocks(title="SoMark vs 通用大模型 · 同台对战") as demo:
        gr.HTML(
            '<div class="app-header">'
            '<div class="app-title">📄 SoMark 解析 vs 通用大模型视觉转写 · 同台对战</div>'
            '<div class="app-sub">上传一份排版复杂的文档（PDF / 图片，最好含公式、表格、代码块）。'
            '左路 <code>SoMark /parse</code> API，右路多模态视觉大模型直接阅读，'
            '两路并行 —— 谁先解析完谁先出结果，并由裁判打分。</div></div>'
        )

        with gr.Row():
            file_in = gr.File(
                label="上传文档（PDF / PNG / JPG / WebP / GIF）",
                file_types=[".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"],
                type="filepath",
            )
        run_btn = gr.Button("🚀 开始对战", variant="primary", size="lg")

        with gr.Row(equal_height=True):
            with gr.Column():
                gr.Markdown("### 🅰️ SoMark 解析结果")
                left_status = gr.HTML("")
                left_view = SoMarkDown(katex=KATEX_OPTS, height=600)
            with gr.Column():
                gr.Markdown("### 🅱️ 通用大模型视觉转写结果")
                right_status = gr.HTML("")
                right_view = SoMarkDown(katex=KATEX_OPTS, height=600)

        speed_view = gr.HTML("")

        judge_view = gr.HTML(_judge_placeholder())

        with gr.Accordion("🔍 并排差异高亮（按行对比）", open=False):
            diff_view = gr.HTML("")

        with gr.Accordion("📝 原始 Markdown 文本", open=False):
            with gr.Row():
                left_raw = gr.Textbox(label="SoMark Markdown", lines=18)
                right_raw = gr.Textbox(label="通用大模型视觉转写 Markdown", lines=18)

        run_btn.click(
            fn=run_battle,
            inputs=[file_in],
            outputs=[
                left_status, left_view, right_status, right_view,
                speed_view, diff_view, left_raw, right_raw, judge_view,
            ],
        )

    return demo


if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", "7860"))
    logger.info("启动 Gradio，端口=%d", port)
    build_demo().queue().launch(
        server_name="0.0.0.0", server_port=port, theme=THEME, css=APP_CSS
    )
