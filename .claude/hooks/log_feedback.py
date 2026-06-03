#!/usr/bin/env python3
"""UserPromptSubmit hook — Wu's feedback/prompt channel logger.

Captures every prompt submitted in a Wu session to logs/feedback.jsonl so the
prompts and feedback Wu receives are isolated as a distinct, easily-scored
stream (separate from the full transcript).

CRITICAL: this hook must NOT write to stdout. For UserPromptSubmit, anything a
hook prints to stdout is injected into Wu's context. We write to a file and exit.
"""
import sys, json, os
from datetime import datetime

WU = "/home/unitree/wu"
LOG = os.path.join(WU, "logs", "feedback.jsonl")


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        data = {"_parse_error": True, "_raw": raw[:2000]}

    rec = {
        "ts": datetime.now().astimezone().isoformat(),
        "session_id": data.get("session_id"),
        "cwd": data.get("cwd"),
        "event": data.get("hook_event_name", "UserPromptSubmit"),
        "prompt": data.get("prompt"),
    }

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
