"""A Claude Code of our own, in ~100 lines (Activity 7).

Level 1: a chat loop — read input, send the messages array, print the reply.

    uv run python agent/harness.py            # interactive
    uv run python agent/harness.py --once "hi" # one turn, then exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.model import make_model  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("--once", help="single prompt instead of interactive input")
    args = parser.parse_args()

    model = make_model()
    messages: list[dict] = []

    while True:
        try:
            user = args.once or input("> ")
        except EOFError:
            return 0
        messages.append({"role": "user", "content": user})
        reply, _usage = model.complete(messages)
        messages.append(reply)
        print(reply.get("content") or "")
        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
