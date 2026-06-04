#!/usr/bin/env python3
"""One-off: characterize the close object dead ahead.

Two perceive.py captures showed something steady at the 0.15m ring floor in the
forward +/-15deg bins, with the sides falling away (not a wall). The standard
ring clamps at 0.15m and bins at 30deg, too coarse to say WHAT it is. This probe:
  - bins the forward arc (-60..+60deg) at 10deg, no near-cutoff
  - reports, for points within 0.6m horizontal and dead-ahead (|angle|<25deg),
    the vertical (z) extent and a coarse height histogram
So I can tell a thin leg from a low box from something tall (wall/person/me).
Passive listen only; reuses perceive.read_cloud. No actuation.
"""
import math, collections
from perceive import read_cloud

pts = read_cloud(8.0)
print(f"points: {len(pts)}")

# Finer forward arc, no near cutoff.
fine = collections.defaultdict(lambda: 99.0)
for x, y, z in pts:
    if abs(z) > 0.6:
        continue
    d = math.hypot(x, y)
    ang = math.degrees(math.atan2(y, x))  # 0=fwd, +=left
    if abs(ang) > 60:
        continue
    b = int(round(ang / 10.0)) * 10
    fine[b] = min(fine[b], d)
print("forward arc, 10deg bins, nearest m (no cutoff):")
for b in range(-60, 61, 10):
    d = fine[b]
    print(f"   {b:+4d}deg  {('%.2f'%d) if d<99 else 'open':>5}  {'#'*int(min(d,3)*6) if d<99 else ''}")

# Height profile of the dead-ahead near object.
near = [(x, y, z) for x, y, z in pts
        if math.hypot(x, y) < 0.6 and abs(math.degrees(math.atan2(y, x))) < 25]
print(f"\ndead-ahead near points (<0.6m horiz, |ang|<25deg): {len(near)}")
if near:
    zs = sorted(z for _, _, z in near)
    ds = [math.hypot(x, y) for x, y, _ in near]
    print(f"   horiz dist: min {min(ds):.2f}  max {max(ds):.2f} m")
    print(f"   height z:   min {zs[0]:+.2f}  max {zs[-1]:+.2f} m (sensor z=0)")
    hist = collections.Counter(round(z, 1) for z in zs)
    print("   z histogram (m : count):")
    for zk in sorted(hist):
        print(f"      {zk:+.1f}  {'#'*min(hist[zk], 60)} ({hist[zk]})")
