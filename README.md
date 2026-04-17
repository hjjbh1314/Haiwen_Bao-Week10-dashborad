# DeepSeek AI Agent Dashboard

A Streamlit-based interactive dashboard that lets users query a DeepSeek-powered AI agent with configurable personas and parameters.

---

## System Overview

**Problem.** Talking to a large language model usually means a terminal, a raw API call, and no memory of the previous turn. This project wraps DeepSeek in a clean web dashboard so any user can chat with the agent, tune its behaviour, and get rich feedback — without writing a single line of code or handling a key in plain text.

**What the dashboard does.** From a single browser page the user can (1) pick one of four **agent personas** (General Assistant / Research Analyst / Creative Writer / Code Helper) and tune **temperature** and **max-tokens** from the sidebar, (2) submit a query through a text area with a live **character counter** and built-in validation (empty / min-length / max-length / control-character guards), (3) watch a **step-by-step progress indicator** while the agent thinks, and (4) read the reply in a styled response card alongside a **metrics strip** showing latency and prompt / completion / total tokens. A **multi-turn toggle** preserves context across queries, **example prompts** offer one-click starting points, and both the latest response and the full conversation can be **exported as Markdown**. If something goes wrong, the UI maps every failure into one of nine categorised error cards (auth / rate-limit / timeout / connection / bad-request / empty / api / config / unknown) with specific remediation advice instead of a raw traceback.

**Workflow.**
```
User query (Streamlit UI)
        ↓  client-side: agent.validate_input()
app.py  →  agent.process(input, persona, temperature, max_tokens, history)
        ↓  server-side: re-validate → clamp params → build messages
DeepSeek API  (OpenAI-compatible endpoint, 60s timeout, 2 retries)
        ↓
Structured result dict {ok, content, error_category, tokens_*, elapsed_s}
        ↓
Response card + metric strip + chat history rendered in dashboard
```

**Key Components.**
- `app.py` (~220 lines) — Streamlit front-end: layout and custom CSS polish, input handling with live char counter, `st.status` progress stream, response card with metric cards, API status indicator in sidebar, example prompts, and Markdown export for responses and chat history.
- `agent.py` (~200 lines) — Agent module: DeepSeek client factory with timeout and retries, four persona system prompts, `validate_input()` shared with the UI, parameter clamping, and specific handlers for every major `openai` exception class, all returning a structured result dict.
- `.env` — Stores `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE`, and `DEEPSEEK_MODEL`. Loaded via `python-dotenv`, excluded from Git via `.gitignore`.

---

## How to Run

**1. Clone the repo and enter the folder:**
```bash
git clone <your-repo-url>
cd <repo-folder>
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

**3. Set up your API key:**
```bash
cp .env.example .env
# Open .env and paste your DeepSeek API key
```

**4. Launch the dashboard:**
```bash
streamlit run app.py
```

The app opens at `http://localhost:8501` in your browser.

---

## Features Implemented

| Rubric dimension | Implementation |
|---|---|
| **UI structure** | Wide layout, sidebar config (persona, temperature, max-tokens, multi-turn), main area with title / example-prompt expander / input / response card / chat history; light custom CSS |
| **Input handling** | `st.text_area` with live character counter (colour-tiered), `st.selectbox` + `st.slider`×2 + `st.toggle`, primary submit button auto-disabled without API key |
| **Input validation** | `agent.validate_input()` shared client- and server-side: empty / min-length / max-length (4000) / control-character guards; parameter clamping (`temperature` → [0,1], `max_tokens` → [16, 4096]) |
| **Agent integration** | `agent.process()` returns structured dict (`ok`, `content`, `tokens_*`, `elapsed_s`, `finish_reason`, `error_category`); 60 s timeout + 2 retries |
| **Error handling** | Explicit handlers for `AuthenticationError`, `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `BadRequestError`, `APIStatusError` + empty-response + config + unknown — each mapped to a category-specific card with remediation advice |
| **User feedback** | `st.status` progress stream, `st.toast` for non-blocking events, `st.success` / `st.warning` / `st.error` / `st.info` (truncation hint), metric strip showing latency and prompt / completion / total tokens, API status badge in sidebar |
| **Interaction quality** | One-click example prompts, multi-turn chat via `st.session_state`, `st.chat_message` history with turn counter, Markdown export for current response or full chat |

---

## Design Decisions

- **OpenAI-compatible client for DeepSeek** — DeepSeek exposes an OpenAI-compatible REST API, so the `openai` Python package works out of the box; no additional SDK required.
- **Persona system** — Four pre-defined system prompts let users quickly switch the agent's tone and output style without writing prompts themselves.
- **Session state for history** — Streamlit re-runs the script on every interaction; `st.session_state` is the idiomatic way to persist data between runs.
- **Defence-in-depth validation** — Input is validated in `app.py` before the call *and* re-validated in `agent.validate_input()`. Even if the UI is bypassed, the agent never calls the API with garbage input.
- **Structured agent results** — `agent.process()` returns a dict (`ok`, `content`, `error_category`, `error`, `tokens_*`, `elapsed_s`, `finish_reason`) so the UI can render categorised error cards and token/latency metrics without string-matching.
- **Specific exception handling** — `AuthenticationError`, `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `BadRequestError`, and `APIStatusError` are caught individually and mapped to clear, actionable messages (e.g. rate-limit suggests retry, timeout suggests lowering tokens).
- **Timeout & retries** — 60-second request timeout and 2 automatic retries via the OpenAI SDK protect the UI from hanging or transient network blips.
- **`.gitignore` for `.env`** — The API key is loaded via `python-dotenv` and the `.env` file is excluded from version control to prevent credential leakage.
