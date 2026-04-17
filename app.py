"""
app.py — Streamlit dashboard for the DeepSeek AI Agent.
Run with:  streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st

import agent

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DeepSeek AI Agent Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Light styling polish (CSS) ────────────────────────────────────────────────
st.markdown(
    """
    <style>
      /* Tighter main block */
      .block-container { padding-top: 2rem; padding-bottom: 2rem; }
      /* Metric cards */
      div[data-testid="stMetric"] {
          background: rgba(127,127,127,0.06);
          border: 1px solid rgba(127,127,127,0.15);
          padding: 10px 14px;
          border-radius: 10px;
      }
      /* Example prompt buttons: smaller, softer */
      div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
          font-size: 0.85rem;
      }
      /* Response card */
      .response-card {
          background: rgba(127,127,127,0.05);
          border-left: 4px solid #4C8BF5;
          padding: 16px 20px;
          border-radius: 8px;
          margin-top: 8px;
      }
      /* Subtle footer */
      .footer-note {
          color: rgba(127,127,127,0.7);
          font-size: 0.8rem;
          text-align: center;
          margin-top: 2rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state initialisation ──────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []          # list[{role, content}]
if "last_result" not in st.session_state:
    st.session_state.last_result = None         # dict from agent.process()
if "pending_input" not in st.session_state:
    st.session_state.pending_input = ""         # for example-prompt prefill

# ── Sidebar — configuration ───────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    st.caption("Adjust the agent before submitting your query.")

    persona = st.selectbox(
        "🎭 Agent Persona",
        options=agent.list_personas(),
        index=0,
        help="Choose a specialised personality for the AI agent.",
    )

    temperature = st.slider(
        "🌡️ Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.05,
        help="Higher = more creative; Lower = more deterministic.",
    )

    max_tokens = st.slider(
        "📏 Max Response Tokens",
        min_value=128,
        max_value=2048,
        value=1024,
        step=128,
        help="Upper bound on the length of the agent's reply.",
    )

    multi_turn = st.toggle(
        "💬 Multi-turn conversation",
        value=True,
        help="Keep chat history across queries for context.",
    )

    st.divider()

    # API status indicator
    st.markdown("**API Status**")
    api_key_present = bool(os.getenv("DEEPSEEK_API_KEY"))
    api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    if api_key_present:
        st.success(f"🟢 Key loaded · `{model_name}`")
        st.caption(f"Endpoint: `{api_base}`")
    else:
        st.error("🔴 `DEEPSEEK_API_KEY` not found in `.env`")

    st.divider()

    # History controls
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🗑️ Clear", use_container_width=True, help="Clear chat history"):
            st.session_state.chat_history = []
            st.session_state.last_result = None
            st.toast("History cleared", icon="🗑️")
    with col_b:
        if st.session_state.chat_history:
            history_md = "\n\n".join(
                f"### {m['role'].capitalize()}\n{m['content']}"
                for m in st.session_state.chat_history
            )
            st.download_button(
                "⬇️ Export",
                data=history_md,
                file_name=f"chat_{datetime.now():%Y%m%d_%H%M%S}.md",
                mime="text/markdown",
                use_container_width=True,
                help="Download chat history as Markdown",
            )
        else:
            st.button("⬇️ Export", disabled=True, use_container_width=True)

    st.divider()
    st.caption("Powered by [DeepSeek](https://www.deepseek.com/) via OpenAI-compatible API")

# ── Main area ─────────────────────────────────────────────────────────────────
st.title("🤖 DeepSeek AI Agent Dashboard")
st.markdown(
    "Ask anything — the agent adapts based on the **persona** and settings "
    "you choose in the sidebar. Your conversation history is preserved across queries "
    "when **Multi-turn** mode is enabled."
)

# ── Quick-start examples ──────────────────────────────────────────────────────
with st.expander("💡 Example prompts (click to fill)", expanded=False):
    examples = [
        "Explain transformer attention in simple terms.",
        "Give me a 5-step plan for learning Streamlit this weekend.",
        "Write a Python function that reverses a linked list, with comments.",
        "Draft a polite email asking a professor for a deadline extension.",
    ]
    ex_cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        with ex_cols[i]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_input = ex
                st.rerun()

st.divider()

# ── Input section ─────────────────────────────────────────────────────────────
col_input, col_btn = st.columns([5, 1])

with col_input:
    user_input = st.text_area(
        "✏️ Your query",
        value=st.session_state.pending_input,
        placeholder="e.g. Explain transformer attention in simple terms…",
        height=120,
        max_chars=agent.MAX_INPUT_CHARS,   # browser-side hard limit
        label_visibility="collapsed",
        key="user_input_field",
    )
    # Live character counter with colour cue
    char_count = len(user_input)
    pct = char_count / agent.MAX_INPUT_CHARS if agent.MAX_INPUT_CHARS else 0
    if pct >= 0.95:
        st.markdown(
            f"<span style='color:#e74c3c'>⚠ {char_count}/{agent.MAX_INPUT_CHARS} characters — nearing limit</span>",
            unsafe_allow_html=True,
        )
    elif pct >= 0.75:
        st.markdown(
            f"<span style='color:#e67e22'>{char_count}/{agent.MAX_INPUT_CHARS} characters</span>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"{char_count}/{agent.MAX_INPUT_CHARS} characters")

with col_btn:
    st.write("")  # vertical alignment spacer
    st.write("")
    submitted = st.button(
        "▶ Submit",
        type="primary",
        use_container_width=True,
        disabled=not api_key_present,
    )

# Clear any example prefill after one render cycle
if st.session_state.pending_input and user_input == st.session_state.pending_input:
    st.session_state.pending_input = ""

# ── Agent call ────────────────────────────────────────────────────────────────
ERROR_ICONS: dict[str, str] = {
    "validation": "⚠️",
    "config": "🔧",
    "auth": "🔑",
    "rate_limit": "⏳",
    "timeout": "⌛",
    "connection": "🌐",
    "bad_request": "📛",
    "api": "🛑",
    "empty": "🫙",
    "unknown": "❓",
}

if submitted:
    # Client-side validation (mirrors agent.validate_input; fail fast, no API cost)
    ok, msg = agent.validate_input(user_input)
    if not ok:
        st.warning(f"⚠️ {msg}")
    else:
        history = st.session_state.chat_history if multi_turn else []
        progress_msgs = [
            "🔎 Preparing request…",
            "📡 Contacting DeepSeek…",
            "🧠 Model is thinking…",
        ]
        status = st.status("🔄 Agent is working…", expanded=False)
        with status:
            for m in progress_msgs:
                st.write(m)
            result = agent.process(
                user_input,
                persona=persona,
                temperature=temperature,
                max_tokens=max_tokens,
                history=history,
            )
            if result["ok"]:
                status.update(label="✅ Response received!", state="complete", expanded=False)
            else:
                status.update(label="❌ Request failed", state="error", expanded=True)

        st.session_state.last_result = result

        if result["ok"]:
            st.session_state.chat_history.append(
                {"role": "user", "content": user_input.strip()}
            )
            st.session_state.chat_history.append(
                {"role": "assistant", "content": result["content"]}
            )
            st.toast("Response ready", icon="✅")
        else:
            icon = ERROR_ICONS.get(result["error_category"], "❌")
            st.error(f"{icon} **{result['error_category'].replace('_', ' ').title()} error** — {result['error']}")

# ── Response display ──────────────────────────────────────────────────────────
res = st.session_state.last_result
if res and res.get("ok"):
    st.subheader("💡 Latest Response")

    # Response metadata strip
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Latency", f"{res['elapsed_s']:.2f}s")
    m2.metric("Prompt tokens", res["tokens_prompt"])
    m3.metric("Completion tokens", res["tokens_completion"])
    m4.metric("Total tokens", res["tokens_total"])

    # Answer
    st.markdown(f"<div class='response-card'>{res['content']}</div>", unsafe_allow_html=True)

    # Raw export for this turn
    cdl_col, _ = st.columns([1, 5])
    with cdl_col:
        st.download_button(
            "⬇️ Save response",
            data=res["content"],
            file_name=f"response_{datetime.now():%Y%m%d_%H%M%S}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    if res.get("finish_reason") and res["finish_reason"] != "stop":
        st.info(
            f"ℹ️ Finish reason: `{res['finish_reason']}` — "
            "the reply may be truncated. Consider increasing **Max Response Tokens**."
        )

# ── Conversation history ──────────────────────────────────────────────────────
if st.session_state.chat_history:
    st.divider()
    st.subheader(f"📜 Conversation History ({len(st.session_state.chat_history) // 2} turns)")

    for msg in reversed(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='footer-note'>Mini-Assignment 5 · DeepSeek AI Agent Dashboard · Streamlit</div>",
    unsafe_allow_html=True,
)
