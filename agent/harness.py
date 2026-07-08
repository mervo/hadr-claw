"""A Claude Code of our own, in ~100 lines (Activity 7).

Level 1: a chat loop — read input, send the messages array, print the reply.
Level 2: standing orders — prepend agent/soul.md as the system prompt.
         (This is all CLAUDE.md is.)
Level 3: one tool — the model asks for fetch_feed, our code runs it, the
         result goes back into the messages.

    uv run python agent/harness.py            # interactive
    uv run python agent/harness.py --once "hi" # one turn, then exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import tools  # noqa: E402
from agent.model import make_model  # noqa: E402

SOUL = Path(__file__).with_name("soul.md")


def main() -> int:
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("--once", help="single prompt instead of interactive input")
    args = parser.parse_args()

    model = make_model()
    messages: list[dict] = [{"role": "system", "content": SOUL.read_text()}]

    while True:
        try:
            user = args.once or input("> ")
        except EOFError:
            return 0
        messages.append({"role": "user", "content": user})
        reply, _usage = model.complete(messages, tools.SCHEMAS)
        messages.append(reply)
        for call in reply.get("tool_calls") or []:
            print(f"[tool] {call['function']['name']}({call['function']['arguments']})")
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": tools.run(call)}
            )
        if reply.get("tool_calls"):
            reply, _usage = model.complete(messages, tools.SCHEMAS)
            messages.append(reply)
        print(reply.get("content") or "")
        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
