---
date: 2026-07-08
tags: [model-api, opencode, zen, billing, tool-calls]
problem: Chat completions against OpenCode Zen fail with CreditsError even though the API key is valid
---

# OpenCode Zen gateway: what the key can actually call

**Symptom:** `GET /zen/v1/models` works (51 models listed) but
`POST /zen/v1/chat/completions` on `kimi-k2.7-code` returns
`{"type": "CreditsError", "message": "Insufficient balance…"}`.

**Cause:** the models endpoint lists the whole Zen catalog regardless of plan.
Paid models draw on workspace balance; the Go subscription/credits must be
active for them. The key itself is fine.

**Fix / findings (verified 2026-07-08):**

- Endpoint `https://opencode.ai/zen/v1/chat/completions` is OpenAI-compatible,
  auth `Authorization: Bearer $OPENCODE_API_KEY`.
- Free-tier models work with **no balance** and support OpenAI-style tool
  calls with `usage` populated:
  - `deepseek-v4-flash-free` — clean tool_calls, cache-aware usage fields
  - `north-mini-code-free` — works; nonstandard tool_call id format
  - `nemotron-3-ultra-free` — upstream errors, avoid
- `deepseek-v4-flash-free` is the dev/CI-smoke default (`HADR_MODEL`);
  `kimi-k2.7-code` is the production candidate once balance is topped up
  (user action — billing link in the error message).
