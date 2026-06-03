#!/usr/bin/env python3
"""SessionEnd hook — archive the finished session transcript + commit.

Claude Code already writes a complete session transcript as JSONL. On session
end we copy that transcript into logs/sessions/ under a stable, timestamped name,
drop a small metadata sidecar, and make a best-effort local git commit so each
session is a versioned record. Transfer off-device is handled separately by the
analyst pulling over the LAN (rsync); we do not push here (Wu has no internet).
"""
import sys, json, os, shutil, subprocess
from datetime import datetime

WU = "/home/unitree/wu"
SESS_DIR = os.path.join(WU, "logs", "sessions")


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    tp = data.get("transcript_path")
    sid = data.get("session_id") or "unknown"
    reason = data.get("reason", "")

    now = datetime.now().astimezone()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    os.makedirs(SESS_DIR, exist_ok=True)

    dest = None
    if tp and os.path.exists(tp):
        dest = os.path.join(SESS_DIR, f"{stamp}_{sid}.jsonl")
        try:
            shutil.copy2(tp, dest)
        except Exception:
            dest = None

    meta = {
        "ts": now.isoformat(),
        "session_id": sid,
        "reason": reason,
        "transcript_src": tp,
        "transcript_copy": dest,
    }
    with open(os.path.join(SESS_DIR, f"{stamp}_{sid}.meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # Best-effort local commit. Never fail the hook on git problems.
    try:
        subprocess.run(["git", "-C", WU, "add", "logs"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(
            ["git", "-C", WU, "commit", "-m", f"log: session {sid} ended ({reason}) {stamp}"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
