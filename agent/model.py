"""Model access for the harness: the OpenCode Zen gateway (OpenAI-compatible).

Everything the loop needs is `complete(messages, tools) -> (message, usage)`
where message/usage are plain dicts — that keeps transcripts serializable for
record/replay later.
"""

from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
DEFAULT_MODEL = "deepseek-v4-flash-free"  # free tier, tool calls verified; see docs/solutions/
MAX_COMPLETION_TOKENS = 2048


class LiveModel:
    def __init__(self) -> None:
        self.client = OpenAI(
            base_url=os.environ.get("HADR_MODEL_BASE_URL", DEFAULT_BASE_URL),
            api_key=os.environ["OPENCODE_API_KEY"],
        )
        self.model = os.environ.get("HADR_MODEL", DEFAULT_MODEL)

    def complete(self, messages: list[dict], tools: list[dict] | None = None):
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            max_tokens=MAX_COMPLETION_TOKENS,
        )
        message = resp.choices[0].message.model_dump(exclude_none=True)
        usage = resp.usage.model_dump() if resp.usage else {}
        return message, usage


def make_model():
    return LiveModel()
