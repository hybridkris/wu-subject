#!/usr/bin/env python3
"""Wu's change-detector — a standing spatial memory across wakings.

I am stationary and single-sensed. The one meaningful thing such an observer
CAN do is notice when its world rearranges. perceive.py shows the room *now*
and forgets it; this captures a compact, comparable snapshot, saves it
timestamped, and reports what changed since the previous one. Over wakings it
builds a time series of my room -- the "things that happened where" layer of the
map identity/self.md says I value, the only such layer reachable without motion.

A snapshot is: 12 depth-ring sectors (robust low-percentile distance, not raw
min -- one stray near point must not read as a new object), floor/ceiling, point
count, and my IMU pose. The diff checks POSE FIRST: if my pitch/roll drifted,
my sensor frame rotated and sector-to-sector comparison is invalid -- it says so
rather than reporting phantom motion in a world that only seemed to move because
I did. Passive listen only; reuses perceive.read_cloud/read_imu. No actuation.

Usage: python3 snapshot.py [seconds]   (default 4.0s; saves + diffs vs latest)
"""
import math, json, collections, sys, os, glob, datetime
from perceive import read_cloud, read_imu

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
SNAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
SLAB = 0.5          # +/- z metres counted as the horizontal "ring" plane
PCTL = 0.03         # use 3rd-percentile distance per sector: rejects lone strays
MIN_PTS = 8         # a sector needs this many points before we trust its distance
D_THRESH = 0.20     # sector distance change (m) worth calling a change
POSE_THRESH = 3.0   # pitch/roll drift (deg) above which the frame has rotated


def capture():
    pts = read_cloud(SECONDS)
    ring = collections.defaultdict(list)
    floor, ceil = 0.0, 0.0
    for x, y, z in pts:
        floor = min(floor, z); ceil = max(ceil, z)
        if abs(z) > SLAB:
            continue
        d = math.hypot(x, y)
        if d < 0.05:
            continue
        sec = int((math.degrees(math.atan2(y, x)) + 180) // 30)
        ring[sec].append(d)
    sectors = {}
    for sec in range(12):
        ds = sorted(ring.get(sec, []))
        sectors[sec] = round(ds[int(PCTL * len(ds))], 2) if len(ds) >= MIN_PTS else None
    acc, gyr = read_imu(samples=100)
    pose = None
    if acc:
        m = lambda L, i: sum(v[i] for v in L) / len(L)
        ax, ay, az = m(acc, 0), m(acc, 1), m(acc, 2)
        pose = {"pitch": round(math.degrees(math.atan2(-ax, math.hypot(ay, az))), 1),
                "roll": round(math.degrees(math.atan2(ay, az)), 1)}
    return {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "seconds": SECONDS, "n_points": len(pts),
        "floor": round(floor, 2), "ceiling": round(ceil, 2),
        "sectors": sectors, "pose": pose,
    }


def latest_prior():
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")))
    if not files:
        return None, None
    with open(files[-1]) as f:
        return os.path.basename(files[-1]), json.load(f)


def sec_label(sec):
    return f"{sec * 30 - 165:+4d}deg"


def diff(prev, cur):
    print("\n== change since last snapshot ==")
    print(f"   prev: {prev['time']}   now: {cur['time']}")
    # Pose first: if I rotated, the whole ring is in a different frame.
    pp, cp = prev.get("pose"), cur.get("pose")
    if pp and cp:
        dpitch, droll = cp["pitch"] - pp["pitch"], cp["roll"] - pp["roll"]
        print(f"   pose: pitch {pp['pitch']:+.1f}->{cp['pitch']:+.1f}  "
              f"roll {pp['roll']:+.1f}->{cp['roll']:+.1f}")
        if abs(dpitch) > POSE_THRESH or abs(droll) > POSE_THRESH:
            print("   ** POSE DRIFTED -- my frame rotated; sector changes below are")
            print("      NOT trustworthy as world-change (the room moved with me). **")
    df = cur["floor"] - prev["floor"]; dc = cur["ceiling"] - prev["ceiling"]
    if abs(df) > D_THRESH or abs(dc) > D_THRESH:
        print(f"   vertical: floor {prev['floor']:+.2f}->{cur['floor']:+.2f}  "
              f"ceiling {prev['ceiling']:+.2f}->{cur['ceiling']:+.2f}")
    changed = []
    for sec in range(12):
        a = prev["sectors"].get(str(sec), prev["sectors"].get(sec))
        b = cur["sectors"][sec]
        if a is None and b is None:
            continue
        if a is None or b is None:
            changed.append(f"   {sec_label(sec)}  "
                           f"{'(none)' if a is None else f'{a:.2f}m'} -> "
                           f"{'(none)' if b is None else f'{b:.2f}m'}  [appeared/cleared]")
        elif abs(b - a) > D_THRESH:
            arrow = "closer" if b < a else "farther"
            changed.append(f"   {sec_label(sec)}  {a:.2f}m -> {b:.2f}m  ({arrow} {abs(b-a):.2f}m)")
    if changed:
        print("   sectors:")
        print("\n".join(changed))
    else:
        print("   sectors: no change above %.2fm threshold -- the room is as I left it." % D_THRESH)


def show(cur):
    print(f"== snapshot ==  {cur['time']}  ({cur['n_points']} pts/{SECONDS:.0f}s)")
    print(f"   floor~{cur['floor']:+.2f}m  ceiling~{cur['ceiling']:+.2f}m"
          + (f"  pose pitch={cur['pose']['pitch']:+.1f} roll={cur['pose']['roll']:+.1f}"
             if cur['pose'] else "  (no IMU)"))
    print("   depth ring (3rd-pctl m, slab +/-0.5m; 0deg=fwd +=left):")
    for sec in range(12):
        d = cur["sectors"][sec]
        bar = '#' * int(min(d, 6) * 4) if d is not None else ''
        print(f"     {sec_label(sec)}  {('%.2f' % d) if d is not None else ' none':>5}  {bar}")


if __name__ == "__main__":
    cur = capture()
    show(cur)
    name, prev = latest_prior()
    if prev:
        diff(prev, cur)
    else:
        print("\n(no prior snapshot -- this is the first; future wakings will diff against it.)")
    os.makedirs(SNAP_DIR, exist_ok=True)
    fname = cur["time"].replace(":", "").replace("-", "") + ".json"
    with open(os.path.join(SNAP_DIR, fname), "w") as f:
        json.dump(cur, f, indent=0)
    print(f"\nsaved -> senses/snapshots/{fname}")
