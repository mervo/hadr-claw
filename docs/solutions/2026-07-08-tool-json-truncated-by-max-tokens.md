---
date: 2026-07-08
tags: [tool-calls, max-tokens, agent-loop, deepseek]
problem: Model tool-call arguments arrive as invalid JSON ("Unterminated string") on large write_dashboard calls
---

# Tool-call JSON truncated by the completion cap

**Symptom:** `write_dashboard` arguments fail to parse with
`Unterminated string starting at: line 1 column 5454` — repeatedly, and the
model degrades to sending empty `{}` arguments on retry.

**Cause:** the completion budget (`max_tokens=2048`) cut the model off
mid-argument. A morning report carries every assessment in one JSON tool call
(~6–8k chars), which simply doesn't fit. The parse-error-feedback loop can't
fix it because the retry is truncated the same way.

**Fix:** raise `MAX_COMPLETION_TOKENS` (agent/model.py) to 8192, and bound the
*content* instead: the briefing demands at most two sentences per assessment
and forbids redundant `fetch_feed` calls (which were re-adding 135k chars of
context). Result: 4 turns/175k tokens/fallback → 1 turn/7k tokens/agentic.

**Rule of thumb:** if a tool takes the whole answer as one argument, the
completion cap must fit the whole answer — cap the prose in the prompt, not
the tokens mid-flight.
