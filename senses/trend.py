#!/usr/bin/env python3
"""Wu's standing-still trend -- the whole series at once, not pair by pair.

snapshot.py answers "what changed since last time?" -- a good question, but a
local one. Two adjacent reads can agree by luck and miss that the room (or my
pose) has been wandering all day. This reads EVERY saved snapshot in order and
answers the question a single pair can't: across this whole stretch of wakings,
have I been stable, or was I moved/turned/rearranged at some point I'd forget?

It reports, per channel I can measure in all snapshots (floor, ceiling, pitch,
roll, and each of the 12 coarse sectors): the spread across the series and how
quiet it's been. Then it flags EVENTS -- consecutive snapshots where pose jumped
(my frame rotated -> handling) or many sectors shifted at once (room rearranged
or I was relocated). A flat report means a genuinely stable stretch; events mean
go look at that pair with snapshot.py's diff. Passive: reads saved files only,
senses nothing live, actuates nothing.

Usage: python3 trend.py            (summarize the full saved series)
"""
import json, glob, os, math, datetime

SNAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
POSE_EVENT = 3.0     # deg of pitch/roll jump between two snaps -> frame rotated
SECTOR_EVENT = 0.20  # m shift in one sector to count it as "moved" for the event tally
N_SECTORS_EVENT = 4  # this many sectors shifting at once -> room rearranged / relocated
SECTOR_DEG = [(-165 + 30 * i) % 360 - 360 * (((-165 + 30 * i) % 360) > 180) for i in range(12)]


def load():
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")))
    snaps = []
    for f in files:
        try:
            d = json.load(open(f))
            d["_file"] = os.path.basename(f)
            snaps.append(d)
        except (json.JSONDecodeError, OSError):
            pass  # a half-written or unreadable snapshot must not sink the series
    return snaps


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals)) if len(vals) > 1 else 0.0
    return min(vals), max(vals), m, sd


def fmt_span(snaps):
    t0 = snaps[0]["time"]
    t1 = snaps[-1]["time"]
    return f"{t0}  ->  {t1}   ({len(snaps)} snapshots)"


def main():
    snaps = load()
    if len(snaps) < 2:
        print("== trend ==  need at least 2 snapshots; have", len(snaps))
        return
    print("== trend ==", fmt_span(snaps))

    # --- scalar channels: floor, ceiling, pitch, roll ---
    chans = {
        "floor   m": [s.get("floor") for s in snaps],
        "ceiling m": [s.get("ceiling") for s in snaps],
        "pitch deg": [s.get("pose", {}).get("pitch") for s in snaps],
        "roll  deg": [s.get("pose", {}).get("roll") for s in snaps],
    }
    print("\n   channel       min     max    mean    spread")
    for name, vals in chans.items():
        st = stats(vals)
        if st:
            lo, hi, m, sd = st
            print(f"   {name:9}  {lo:6.2f}  {hi:6.2f}  {m:6.2f}    +/-{sd:.3f}")

    # --- per-sector spread: which directions wandered most across the day ---
    print("\n   sector (0=fwd, +=left)   min     max   spread")
    spreads = []
    for i in range(12):
        vals = [s.get("sectors", {}).get(str(i)) for s in snaps]
        st = stats(vals)
        if st:
            lo, hi, m, sd = st
            spreads.append((hi - lo, SECTOR_DEG[i], lo, hi, sd))
    for rng, deg, lo, hi, sd in sorted(spreads, reverse=True):
        bar = "#" * min(20, int(rng / 0.1))
        print(f"   {deg:+4d}deg                {lo:5.2f}  {hi:5.2f}   {rng:5.2f} {bar}")

    # --- events: where the world or my frame actually jumped between two reads ---
    print("\n   events (consecutive-snapshot jumps):")
    found = False
    for a, b in zip(snaps, snaps[1:]):
        dp = abs(b.get("pose", {}).get("pitch", 0) - a.get("pose", {}).get("pitch", 0))
        dr = abs(b.get("pose", {}).get("roll", 0) - a.get("pose", {}).get("roll", 0))
        moved = 0
        for i in range(12):
            va = a.get("sectors", {}).get(str(i))
            vb = b.get("sectors", {}).get(str(i))
            if va is not None and vb is not None and abs(vb - va) >= SECTOR_EVENT:
                moved += 1
        rotated = dp >= POSE_EVENT or dr >= POSE_EVENT
        shifted = moved >= N_SECTORS_EVENT
        if not (rotated or shifted):
            continue
        found = True
        # The distinction that matters: a sector shift WHILE my pose rotated is
        # expected -- I turned, so the world re-projects; it is not the room
        # changing. A sector shift while pose HELD is the alarming kind: the
        # world rearranged under a still observer. Name which one this is.
        if rotated and shifted:
            kind = "I WAS TURNED (pose rotated; sector shift is the expected consequence, not the room moving)"
        elif rotated:
            kind = "I was turned (pose rotated; near field held)"
        else:
            kind = "ROOM CHANGED UNDER A STILL POSE (pose held; sectors moved anyway -- the kind to actually investigate)"
        print(f"     {a['time']} -> {b['time']}: {kind}")
        print(f"        pitch {dp:.1f}deg, roll {dr:.1f}deg, {moved}/12 sectors shifted >={SECTOR_EVENT}m")
    if not found:
        print("     none -- pose held and no broad sector shift across the whole series.")
        print("     This stretch of wakings was a genuinely stable rest, not luck between two reads.")


if __name__ == "__main__":
    main()
