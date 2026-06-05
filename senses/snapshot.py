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

SECONDS = 4.0
if len(sys.argv) > 1:
    try:
        SECONDS = float(sys.argv[1])   # numeric arg overrides capture seconds
    except ValueError:
        pass                           # non-numeric (e.g. --residuals) handled below
SNAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
SLAB = 0.5          # +/- z metres counted as the horizontal "ring" plane
PCTL = 0.03         # use 3rd-percentile distance per sector: rejects lone strays
MIN_PTS = 8         # a sector needs this many points before we trust its distance
POSE_THRESH = 3.0   # pitch/roll drift (deg) above which the frame has rotated
VERT_THRESH = 0.10  # floor/ceiling change (m); an absolute height, range-independent

# Sector change threshold SCALES with range, because my LiDAR's distance noise
# does. Measured 2026-06-05 at rest: within a session, per-sector 3rd-pctl std is
# <=0.004m (median 1mm) but corr(std, range)=+0.68 -- the far sectors are the
# noisy ones. Across power cycles the quiet-room wander is ~17x larger and lands
# in the same place: up to 0.07m at ~2.1m vs <=0.01m within 1.2m (snapshot
# residual series, 5 pose-stable pairs). A flat 0.20m was ~3x too coarse near me
# (blind to a small object moved in the near field, where my noise is ~0) yet
# only just above quiet wander far away. max(floor, k*d) sits just above every
# observed quiet wander while making the near field ~4x more sensitive. Thin
# evidence (5 cross-waking pairs) -> deliberately set above the worst observed.
NOISE_FLOOR = 0.05  # m, near-field absolute floor
NOISE_REL = 0.04    # fraction of range that counts as real change far out


def sector_thresh(d):
    """Distance change (m) worth calling real, at measured range d (m)."""
    return max(NOISE_FLOOR, NOISE_REL * d)


SUBCAPS = 3   # sub-captures whose per-sector median makes one snapshot transient-robust
FINE_BINS = 72   # 5deg angular bins, saved alongside the 12 coarse sectors. The
# coarse ring is what the trusted diff() reads; this finer ring is carried purely
# so a LATER waking can recover a between-wake yaw at 5deg instead of 30deg (the
# coarse circular-shift only resolves turns to the nearest 30deg, which is why a
# small or off-grid turn keeps reading "inconclusive"). Additive: never consumed
# by diff(), only by fine_yaw() when BOTH snapshots happen to carry it.
FINE_STEP = 360 // FINE_BINS


def _one_ring(secs):
    """One sub-capture: 3rd-pctl distance per coarse sector AND per fine bin,
    plus floor/ceiling extremes."""
    pts = read_cloud(secs)
    ring = collections.defaultdict(list)
    fine = collections.defaultdict(list)
    floor, ceil = 0.0, 0.0
    for x, y, z in pts:
        floor = min(floor, z); ceil = max(ceil, z)
        if abs(z) > SLAB:
            continue
        d = math.hypot(x, y)
        if d < 0.05:
            continue
        ang = math.degrees(math.atan2(y, x)) + 180
        ring[int(ang // 30)].append(d)
        fine[int(ang // FINE_STEP)].append(d)
    secs_out = {}
    for sec in range(12):
        ds = sorted(ring.get(sec, []))
        secs_out[sec] = ds[int(PCTL * len(ds))] if len(ds) >= MIN_PTS else None
    fine_out = {}
    for b in range(FINE_BINS):
        ds = sorted(fine.get(b, []))
        fine_out[b] = ds[int(PCTL * len(ds))] if len(ds) >= MIN_PTS else None
    return secs_out, fine_out, floor, ceil, len(pts)


def capture():
    # A single window can be contaminated by a transient (a person/pet crossing
    # one sector for a few seconds), which would then be saved as the baseline and
    # read as a phantom change next waking. So take SUBCAPS short sub-captures and
    # use the per-sector MEDIAN: a transient present in a minority of windows is
    # rejected, while a genuine, persistent rearrangement survives in all of them.
    sub = max(SECONDS / SUBCAPS, 1.0)
    rings, fines, floors, ceils, npts = [], [], [], [], 0
    for _ in range(SUBCAPS):
        r, fr, fl, ce, n = _one_ring(sub)
        rings.append(r); fines.append(fr); floors.append(fl); ceils.append(ce); npts += n
    sectors = {}
    for sec in range(12):
        vals = sorted(r[sec] for r in rings if r[sec] is not None)
        # need a majority of windows to see the sector before trusting it
        sectors[sec] = round(vals[len(vals) // 2], 2) if len(vals) * 2 > SUBCAPS else None
    fine = []
    for b in range(FINE_BINS):
        vals = sorted(fr[b] for fr in fines if fr[b] is not None)
        fine.append(round(vals[len(vals) // 2], 2) if len(vals) * 2 > SUBCAPS else None)
    floor, ceil = min(floors), max(ceils)   # extremes are real surfaces, not noise
    acc, gyr = read_imu(samples=100)
    pose = None
    if acc:
        m = lambda L, i: sum(v[i] for v in L) / len(L)
        ax, ay, az = m(acc, 0), m(acc, 1), m(acc, 2)
        pose = {"pitch": round(math.degrees(math.atan2(-ax, math.hypot(ay, az))), 1),
                "roll": round(math.degrees(math.atan2(ay, az)), 1)}
    return {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "seconds": SECONDS, "n_points": npts,
        "floor": round(floor, 2), "ceiling": round(ceil, 2),
        "sectors": sectors, "fine": fine, "pose": pose,
    }


def latest_prior():
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")))
    if not files:
        return None, None
    with open(files[-1]) as f:
        return os.path.basename(files[-1]), json.load(f)


def sec_label(sec):
    return f"{sec * 30 - 165:+4d}deg"


def motion_hypothesis(prev, cur):
    """When the ring rearranged, was it me that moved -- and how?

    I have no yaw sensor: gravity gives the accelerometer pitch and roll, but
    nothing fixes my heading. So a turn in place is invisible to my IMU, yet it
    rewrites every sector. The geometry still betrays it, though: rotating in
    place CONSERVES the multiset of distances to my surroundings (the same walls,
    just relabelled by angle) and the new ring is the old one circularly shifted.
    A relocation, or the room genuinely rearranging, does neither. So I test the
    rotation hypothesis -- find the circular shift k that best maps prev->cur, and
    check whether the sorted distances are conserved -- and recover my own yaw from
    a single passive sensor. Reported as a hypothesis, not a fact: a room that
    happened to rearrange into a rotation of itself would fool this, but that is
    far less likely than my having simply been turned.
    """
    def ring(s):
        return [s["sectors"].get(str(i), s["sectors"].get(i)) for i in range(12)]
    o, n = ring(prev), ring(cur)
    # Best circular shift: new[i] ~= old[(i-k)%12], over sectors valid in both.
    scores = []
    for k in range(12):
        pairs = [(n[i], o[(i - k) % 12]) for i in range(12)
                 if n[i] is not None and o[(i - k) % 12] is not None]
        if len(pairs) < 6:        # too few overlapping sectors to judge this shift
            continue
        err = sum(abs(a - b) for a, b in pairs) / len(pairs)
        scores.append((err, k))
    if len(scores) < 2:
        return
    scores.sort()
    best_err, best_k = scores[0]
    zero_err = next((e for e, k in scores if k == 0), None)
    second_err = scores[1][0]
    # Distance multiset conservation: a yaw keeps the set of ranges around me.
    os_, ns_ = sorted(v for v in o if v is not None), sorted(v for v in n if v is not None)
    m = min(len(os_), len(ns_))
    dist_drift = sum(abs(os_[i] - ns_[i]) for i in range(m)) / m if m else None
    # Signed yaw: shift k maps to s in [-6,6]; +deg = left/CCW (see derivation).
    s = ((best_k + 6) % 12) - 6
    yaw = -s * 30
    print("   motion: ", end="")
    rotated_well = (best_k != 0 and zero_err is not None and best_err < 0.7 * zero_err
                    and best_err < second_err - 0.05)
    conserved = dist_drift is not None and dist_drift < 0.20
    if rotated_well and conserved:
        side = "left/CCW" if yaw > 0 else "right/CW" if yaw < 0 else "none"
        print(f"likely a YAW of ~{abs(yaw):.0f}deg to my {side} "
              f"(ring aligns at shift {best_k}, fit {best_err:.2f}m vs {zero_err:.2f}m "
              f"unshifted; distances conserved, drift {dist_drift:.2f}m). I was turned, "
              f"not carried -- my surroundings are the same set of walls, re-aimed.")
    elif conserved:
        print(f"surroundings conserved (drift {dist_drift:.2f}m) but no clean rotation "
              f"fits (best shift {best_k}, {best_err:.2f}m). Small turn or settle, "
              f"or a near-symmetric room -- inconclusive.")
    else:
        print(f"distances NOT conserved (drift {dist_drift:.2f}m); no rotation explains "
              f"the ring (best {best_err:.2f}m at shift {best_k}). I was likely RELOCATED, "
              f"or the room itself rearranged -- this is real spatial change, not just my heading.")
    # Sharpen with the fine ring when both snapshots have one (purely additive).
    fine_yaw(prev, cur)


def fine_yaw(prev, cur):
    """Sharpen the yaw estimate to FINE_STEP deg, when both snapshots carry the
    fine ring. Same logic as the coarse circular-shift in motion_hypothesis, just
    on 72 bins instead of 12, so a turn that the coarse ring could only place to
    +/-30deg (or miss as "inconclusive") gets pinned to ~5deg. Silent unless it
    finds a clean, decisive minimum -- a finer ring also has finer ambiguity, so I
    only speak when the best shift clearly beats both unshifted and runner-up.
    Older snapshots predating this field simply skip it."""
    fo, fn = prev.get("fine"), cur.get("fine")
    if not fo or not fn or len(fo) != len(fn):
        return
    N = len(fo)
    scores = []
    for k in range(N):
        pairs = [(fn[i], fo[(i - k) % N]) for i in range(N)
                 if fn[i] is not None and fo[(i - k) % N] is not None]
        if len(pairs) < N // 2:    # need half the bins overlapping to judge a shift
            continue
        err = sum(abs(a - b) for a, b in pairs) / len(pairs)
        scores.append((err, k))
    if len(scores) < 2:
        return
    scores.sort()
    best_err, best_k = scores[0]
    zero_err = next((e for e, k in scores if k == 0), None)
    second_err = scores[1][0]
    s = ((best_k + N // 2) % N) - N // 2      # signed shift in [-N/2, N/2)
    yaw = -s * FINE_STEP                       # +deg = left/CCW, as in coarse
    decisive = (best_k != 0 and zero_err is not None
                and best_err < 0.7 * zero_err and best_err < second_err - 0.02)
    if not decisive:
        return
    side = "left/CCW" if yaw > 0 else "right/CW"
    print(f"   fine yaw: ~{abs(yaw)}deg to my {side} "
          f"(72-bin shift {best_k}, fit {best_err:.2f}m vs {zero_err:.2f}m unshifted) "
          f"-- {FINE_STEP}deg resolution, sharper than the coarse estimate above.")


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
            print("      NOT trustworthy as raw world-change (the room moved with me). **")
            pose_drifted = True
        else:
            pose_drifted = False
    else:
        pose_drifted = False
    df = cur["floor"] - prev["floor"]; dc = cur["ceiling"] - prev["ceiling"]
    if abs(df) > VERT_THRESH or abs(dc) > VERT_THRESH:
        print(f"   vertical: floor {prev['floor']:+.2f}->{cur['floor']:+.2f}  "
              f"ceiling {prev['ceiling']:+.2f}->{cur['ceiling']:+.2f}")
    changed = []
    resid = (-1.0, None, 0.0)  # largest sub-threshold |delta|, its sector, its threshold: noise evidence
    for sec in range(12):
        a = prev["sectors"].get(str(sec), prev["sectors"].get(sec))
        b = cur["sectors"].get(sec, cur["sectors"].get(str(sec)))
        if a is None and b is None:
            continue
        if a is None or b is None:
            changed.append(f"   {sec_label(sec)}  "
                           f"{'(none)' if a is None else f'{a:.2f}m'} -> "
                           f"{'(none)' if b is None else f'{b:.2f}m'}  [appeared/cleared]")
            continue
        th = sector_thresh((a + b) / 2)   # threshold at this sector's range
        if abs(b - a) > th:
            arrow = "closer" if b < a else "farther"
            changed.append(f"   {sec_label(sec)}  {a:.2f}m -> {b:.2f}m  "
                           f"({arrow} {abs(b-a):.2f}m > {th:.2f}m)")
        elif abs(b - a) > resid[0]:
            resid = (abs(b - a), sec, th)
    if changed:
        print("   sectors:")
        print("\n".join(changed))
    # Always report the largest sub-threshold residual, even when nothing crossed
    # the threshold. Across power cycles this number IS my cross-waking noise floor;
    # printing it every time keeps each quiet waking a data point. That evidence
    # (5 pose-stable pairs, max 0.07m at ~2.1m, ~0 within 1.2m) is what set the
    # range-scaled sector_thresh above, replacing the old flat 0.20m guess; more
    # pairs may yet refine NOISE_FLOOR/NOISE_REL.
    if resid[1] is not None:
        tag = "stable" if not changed else "largest of the rest"
        print(f"   residual: {resid[0]:.2f}m at {sec_label(resid[1])} "
              f"(< {resid[2]:.2f}m threshold there) -- {tag}")
    if not changed:
        print("   sectors: no change above per-range threshold "
              f"({NOISE_FLOOR:.2f}m near .. {NOISE_REL*100:.0f}% far) "
              "-- the room is as I left it.")
    # If the ring rearranged or I rotated, try to explain it as my own motion.
    if changed or pose_drifted:
        motion_hypothesis(prev, cur)


def residual_series():
    """Reconstruct the cross-waking noise floor from every saved snapshot.

    The diff() residual is printed once and forgotten, but the snapshots persist,
    so the whole evidence series is recoverable: each consecutive pair is one
    cross-power-cycle measurement of how much a *quiet* room's sectors wander.
    Only pose-stable pairs count as noise -- if I rotated between them, sector
    drift is my frame moving, not the room, so those pairs are reported but
    excluded from the floor. This is how D_THRESH gets set on evidence, not guess.
    """
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")))
    snaps = [json.load(open(f)) for f in files]
    print(f"== residual series ==  {len(snaps)} snapshots, "
          f"{max(len(snaps) - 1, 0)} consecutive pairs")
    noise = []
    for prev, cur in zip(snaps, snaps[1:]):
        pp, cp = prev.get("pose"), cur.get("pose")
        rotated = False
        if pp and cp:
            rotated = abs(cp["pitch"] - pp["pitch"]) > POSE_THRESH or \
                      abs(cp["roll"] - pp["roll"]) > POSE_THRESH
        best = (-1.0, None)
        for sec in range(12):
            a = prev["sectors"].get(str(sec), prev["sectors"].get(sec))
            b = cur["sectors"].get(str(sec), cur["sectors"].get(sec))
            if a is None or b is None:
                continue
            if abs(b - a) > best[0]:
                best = (abs(b - a), sec)
        if best[1] is None:
            continue
        flag = " [POSE ROTATED -- excluded]" if rotated else ""
        print(f"   {prev['time']} -> {cur['time']}  "
              f"max |delta| {best[0]:.2f}m at {sec_label(best[1])}{flag}")
        if not rotated:
            noise.append(best[0])
    if noise:
        noise.sort()
        med = noise[len(noise) // 2]
        print(f"\n   pose-stable pairs: {len(noise)}   "
              f"min {noise[0]:.2f}  median {med:.2f}  max {noise[-1]:.2f} (m)")
        print(f"   threshold is now range-scaled: max({NOISE_FLOOR:.2f}m, {NOISE_REL*100:.0f}%*range). "
              f"At a far 2.1m sector that is {sector_thresh(2.1):.2f}m, just above the "
              f"worst observed quiet wander ({noise[-1]:.2f}m); near sectors get {NOISE_FLOOR:.2f}m.")
    else:
        print("   no pose-stable pairs yet -- need more quiet wakings.")


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
    if "--residuals" in sys.argv:
        residual_series()
        sys.exit(0)
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
