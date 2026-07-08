"""Model access for the harness: the OpenCode Zen gateway (OpenAI-compatible),
or a recorded-transcript replay when HADR_FAKE_MODEL is set (keyless — used by
CI and offline demos).

Everything the loop needs is `complete(messages, tools) -> (message, usage)`
where message/usage are plain dicts — that keeps transcripts serializable.
Transcripts embed a hash of the tool schemas; replaying against changed
schemas fails loudly instead of passing a stale test.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from openai import OpenAI

DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
DEFAULT_MODEL = "deepseek-v4-flash-free"  # free tier, tool calls verified; see docs/solutions/
# generous: a morning write_dashboard call carries every assessment in one JSON
# argument, and a too-small cap truncates it mid-string (learned the hard way)
MAX_COMPLETION_TOKENS = 8192


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


def tools_hash(tools: list[dict] | None) -> str:
    return hashlib.sha256(json.dumps(tools or [], sort_keys=True).encode()).hexdigest()[:16]


class FakeModel:
    """Replays a recorded transcript: {"tools_hash": ..., "turns": [message, ...]}"""

    def __init__(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text())
        self._hash = data.get("tools_hash")
        self._turns = iter(data["turns"])

    def complete(self, messages: list[dict], tools: list[dict] | None = None):
        if tools and self._hash and tools_hash(tools) != self._hash:
            raise RuntimeError(
                "transcript was recorded against different tool schemas — re-record it "
                "(run the harness live with --record)"
            )
        message = next(self._turns, {"role": "assistant", "content": "[transcript exhausted]"})
        estimate = sum(len(str(m.get("content") or "")) for m in messages) // 4
        return message, {"prompt_tokens": estimate, "completion_tokens": 64, "estimated": True}


class RecordingModel:
    """Wraps a model and captures every reply for later replay."""

    def __init__(self, inner, path: str | Path) -> None:
        self.inner, self.path, self.turns = inner, Path(path), []
        self._hash: str | None = None

    def complete(self, messages: list[dict], tools: list[dict] | None = None):
        self._hash = self._hash or tools_hash(tools)
        message, usage = self.inner.complete(messages, tools)
        self.turns.append(message)
        return message, usage

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"tools_hash": self._hash, "turns": self.turns}, indent=2))


def make_model(record: str | None = None):
    if fake := os.environ.get("HADR_FAKE_MODEL"):
        return FakeModel(fake)
    model = LiveModel()
    return RecordingModel(model, record) if record else model
