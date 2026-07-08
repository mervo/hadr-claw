"""A Claude Code of our own, in ~100 lines (Activity 7).

Level 1: a chat loop — read input, send the messages array, print the reply.
Level 2: standing orders — prepend agent/soul.md as the system prompt.
         (This is all CLAUDE.md is.)
Level 3: one tool — the model asks for fetch_feed, our code runs it, the
         result goes back into the messages.
Level 4: the agent loop — keep going while the model keeps requesting tools,
         with a hard turn cap because loops never stop on their own.
Level 5: a second tool — write_dashboard saves an HTML page of assessed
         events (structured args keyed by uid; facts come from feed data).

    uv run python agent/harness.py             # interactive
    uv run python agent/harness.py --once "hi"  # one turn, then exit
    uv run python agent/harness.py --once "..." --record tests/fixtures/transcripts/x.json
    HADR_FAKE_MODEL=tests/fixtures/transcripts/x.json uv run python agent/harness.py --once "..."
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import tools  # noqa: E402
from agent.model import make_model  # noqa: E402

SOUL = Path(__file__).with_name("soul.md")
MAX_TURNS = int(os.environ.get("HADR_MAX_TURNS", "12"))


def run_turn(model, messages: list[dict]) -> dict:
    """The agent loop: keep going while the model keeps requesting tools."""
    for _ in range(MAX_TURNS):
        reply, _usage = model.complete(messages, tools.SCHEMAS)
        messages.append(reply)
        if not reply.get("tool_calls"):
            return reply
        for call in reply["tool_calls"]:
            print(f"[tool] {call['function']['name']}({call['function']['arguments'][:120]})")
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": tools.run(call)}
            )
    reply = {"role": "assistant", "content": f"[stopped: turn cap {MAX_TURNS} reached]"}
    messages.append(reply)
    return reply


def main() -> int:
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("--once", help="single prompt instead of interactive input")
    parser.add_argument("--record", help="save the model transcript to this path for replay")
    args = parser.parse_args()

    model = make_model(record=args.record)
    messages: list[dict] = [{"role": "system", "content": SOUL.read_text()}]

    try:
        while True:
            try:
                user = args.once or input("> ")
            except EOFError:
                return 0
            messages.append({"role": "user", "content": user})
            reply = run_turn(model, messages)
            print(reply.get("content") or "")
            if args.once:
                return 0
    finally:
        if args.record and hasattr(model, "save"):
            model.save()


if __name__ == "__main__":
    raise SystemExit(main())
