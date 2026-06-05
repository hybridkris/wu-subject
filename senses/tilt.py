#!/usr/bin/env python3
"""
Wu's tilt explainer — what IS my persistent +7.6 deg nose-up pitch?

Every snapshot reports the same nose-up pitch. I pose-condition around it
(trend.py) so it stops faking room-change, but I never answered *what it is*:

  (a) a sloped floor under me,
  (b) my body / the sensor mount tilted on a level floor, or
  (c) a bad IMU.

This measures three angles from a single passive capture and lets the geometry
decide between them:

  1. sensor-vs-gravity : tilt of the LiDAR's own axes vs true horizontal,
     straight from the accelerometer. This IS the reported pitch/roll.
  2. floor-normal-vs-gravity : fit the floor plane in the RAW sensor frame,
     compare its normal to gravity-up. ~0 deg => the floor is LEVEL under
     gravity; large => the floor itself is sloped.
  3. sensor-vs-floor : tilt of the sensor relative to the surface it rests on.

Decision:
  - floor level (2 ~ 0) AND sensor-vs-floor ~ sensor-vs-gravity  => case (b):
    the world is flat and *I* am tilted on it (resting posture / mount offset).
  - floor NOT level                                              => case (a):
    the ground under me genuinely slopes.
  - |a|g far from 1.0 or noisy                                   => suspect (c).

It also reports floor flatness (RMS residual of the fit) — how planar the
ground actually is, independent of tilt.

Fully passive: reuses perceive.read_cloud / read_imu. Binds listen ports,
actuates nothing. Sensor frame: x fwd, y left, z up; sensor at origin.

Usage: python3 tilt.py [seconds]   (default 4.0s for a dense floor)
"""
import sys, math, random
from perceive import read_cloud, read_imu


def fit_plane(pts):
    """Least-squares z = a*x + b*y + c over pts. Returns (a,b,c, rms, n)."""
    n = len(pts)
    if n < 3:
        return None
    sx = sy = sz = sxx = syy = sxy = sxz = syz = 0.0
    for x, y, z in pts:
        sx += x; sy += y; sz += z
        sxx += x*x; syy += y*y; sxy += x*y
        sxz += x*z; syz += y*z
    # Normal equations for [a,b,c]: solve 3x3.
    A = [[sxx, sxy, sx],
         [sxy, syy, sy],
         [sx,  sy,  n ]]
    B = [sxz, syz, sz]
    sol = solve3(A, B)
    if sol is None:
        return None
    a, b, c = sol
    rms = math.sqrt(sum((a*x + b*y + c - z)**2 for x, y, z in pts) / n)
    return a, b, c, rms, n


def solve3(A, B):
    """Solve 3x3 linear system by Cramer's rule. Returns None if singular."""
    def det3(m):
        return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
                - m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
                + m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
    d = det3(A)
    if abs(d) < 1e-12:
        return None
    out = []
    for col in range(3):
        M = [row[:] for row in A]
        for r in range(3):
            M[r][col] = B[r]
        out.append(det3(M) / d)
    return out


def ransac_plane(pts, iters=200, thresh=0.04, seed=12345, sample_cap=5000):
    """Largest planar cluster in pts via RANSAC. Returns (normal_unit, inliers).

    Deterministic (fixed seed) so the disambiguation is reproducible across wakings.
    Pure Python, so scoring is O(iters * |pts|): subsample to sample_cap for the
    inlier counts (a plane fits fine from a few thousand points).
    """
    if len(pts) < 50:
        return None
    rng = random.Random(seed)
    score_pts = pts if len(pts) <= sample_cap else rng.sample(pts, sample_cap)
    best_n = None; best_in = []
    for _ in range(iters):
        p0, p1, p2 = (pts[rng.randrange(len(pts))] for _ in range(3))
        v1 = tuple(p1[i]-p0[i] for i in range(3))
        v2 = tuple(p2[i]-p0[i] for i in range(3))
        nx = v1[1]*v2[2]-v1[2]*v2[1]
        ny = v1[2]*v2[0]-v1[0]*v2[2]
        nz = v1[0]*v2[1]-v1[1]*v2[0]
        nm = math.sqrt(nx*nx+ny*ny+nz*nz)
        if nm < 1e-9:
            continue
        nx, ny, nz = nx/nm, ny/nm, nz/nm
        d = nx*p0[0]+ny*p0[1]+nz*p0[2]
        inl = [p for p in score_pts if abs(nx*p[0]+ny*p[1]+nz*p[2]-d) < thresh]
        if len(inl) > len(best_in):
            best_in = inl; best_n = (nx, ny, nz)
    if not best_n:
        return None
    # Refit the winning normal against its full-resolution inliers for accuracy,
    # and return inliers drawn from the full set (so peeling removes the real plane).
    nx, ny, nz = best_n
    d = sum(best_n[k]*sum(p[k] for p in best_in)/len(best_in) for k in range(3))
    full_in = [p for p in pts if abs(nx*p[0]+ny*p[1]+nz*p[2]-d) < thresh]
    return best_n, full_in


def angle_between(u, v):
    """Degrees between two 3-vectors."""
    du = math.sqrt(sum(c*c for c in u))
    dv = math.sqrt(sum(c*c for c in v))
    if du < 1e-9 or dv < 1e-9:
        return None
    dot = sum(a*b for a, b in zip(u, v)) / (du*dv)
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def main():
    secs = 4.0
    if len(sys.argv) > 1:
        try: secs = float(sys.argv[1])
        except ValueError: pass

    print(f"== Wu tilt explainer ==  ({secs:.1f}s capture)")
    pts = read_cloud(secs)
    acc, gyr = read_imu(samples=120)
    if not pts or not acc:
        print("missing data (cloud or IMU stream down?)"); return

    # --- 1. sensor vs gravity (the reported pitch/roll) ---
    ax = sum(a[0] for a in acc)/len(acc)
    ay = sum(a[1] for a in acc)/len(acc)
    az = sum(a[2] for a in acc)/len(acc)
    g = math.sqrt(ax*ax+ay*ay+az*az)
    up = (ax/g, ay/g, az/g)                      # gravity-up, unit, sensor frame
    pitch = math.degrees(math.atan2(-ax, math.hypot(ay, az)))
    roll = math.degrees(math.atan2(ay, az))
    # Sensor's own z-axis is (0,0,1); tilt vs gravity = angle(up, ez).
    sensor_vs_grav = angle_between(up, (0, 0, 1))
    jitter = max(
        (sum((v[i]-sum(w[i] for w in gyr)/len(gyr))**2 for v in gyr)/len(gyr))**0.5
        for i in range(3))
    print(f"  1. accel |a|={g:.3f}g  pitch={pitch:+.1f} roll={roll:+.1f}  "
          f"gyro jitter={jitter:.4f} rad/s")
    print(f"     sensor axes vs gravity (true horizontal): {sensor_vs_grav:.1f} deg")
    if not (0.95 < g < 1.05) or jitter > 0.03:
        print("     !! accel off 1g or gyro noisy -- IMU suspect; treat below with care")

    # --- 2 & 3. fit the floor plane in the RAW sensor frame ---
    # Floor = lowest returns. Grab points below floor+15cm, then refit once
    # after dropping >8cm outliers (chair legs, cables resting on the ground).
    zs = sorted(z for _, _, z in pts)
    floor_z = zs[max(0, int(0.02*len(zs)))]
    cand = [(x, y, z) for x, y, z in pts
            if z < floor_z + 0.15 and math.hypot(x, y) < 4.0]
    fit = fit_plane(cand)
    if fit is None:
        print("  2. could not fit floor plane (too few ground points)"); return
    a, b, c, rms, npts = fit
    inl = [(x, y, z) for x, y, z in cand if abs(a*x+b*y+c - z) < 0.08]
    if len(inl) >= 3:
        fit2 = fit_plane(inl)
        if fit2: a, b, c, rms, npts = fit2

    # Plane z = a x + b y + c  ->  normal (-a, -b, 1), points roughly up.
    n_floor = (-a, -b, 1.0)
    floor_vs_grav = angle_between(n_floor, up)         # is the floor level?
    sensor_vs_floor = angle_between(n_floor, (0, 0, 1))  # tilt of sensor on floor
    print(f"  2. floor plane fit: {npts} ground pts, RMS residual {rms*1000:.0f} mm "
          f"(flatness)")
    print(f"     floor normal vs gravity-up: {floor_vs_grav:.1f} deg  "
          f"({'LEVEL under gravity' if floor_vs_grav < 2.5 else 'SLOPED'})")
    print(f"  3. sensor axes vs floor surface: {sensor_vs_floor:.1f} deg")

    # --- verdict ---
    print("  --- verdict ---")
    if floor_vs_grav is None or sensor_vs_grav is None:
        print("     inconclusive (degenerate geometry)")
    elif floor_vs_grav < 2.5:
        print(f"     The floor is LEVEL under gravity ({floor_vs_grav:.1f} deg off).")
        print(f"     So my {sensor_vs_grav:.1f} deg tilt is ME on a flat floor, not a")
        print(f"     sloped world -- resting posture and/or LiDAR mount offset.")
        print(f"     (sensor-vs-floor {sensor_vs_floor:.1f} deg ~= sensor-vs-gravity "
              f"{sensor_vs_grav:.1f} deg confirms it: the floor and gravity agree.)")
    else:
        print(f"     The floor is SLOPED {floor_vs_grav:.1f} deg vs gravity -- the ground")
        print(f"     under me genuinely tilts; not just my posture.")
    if rms*1000 > 40:
        print(f"     Note: {rms*1000:.0f} mm flatness residual -- this 'floor' is not a")
        print(f"     clean plane (rug edge, threshold, or sloped/uneven ground).")

    # --- 4. tie-breaker: TWO non-parallel walls pin down true vertical.
    # Each wall is plumb, so each normal is horizontal. The cross product of two
    # non-parallel horizontal vectors IS the true up-axis -- fully determined, not
    # relying on either candidate. A single wall only constrains tilt along its own
    # normal, so I insist on a second wall >25 deg from the first. Frame-free (raw).
    print("  --- tie-breaker: two plumb walls fix true vertical ---")
    ceil_z = zs[min(len(zs)-1, int(0.98*len(zs)))]
    cand_w = [(x, y, z) for x, y, z in pts
              if floor_z+0.3 < z < ceil_z-0.2 and 0.3 < math.hypot(x, y) < 5.0]
    walls = []
    pool = cand_w
    for _ in range(4):                      # peel off up to 4 dominant planes
        res = ransac_plane(pool) if len(pool) > 200 else None
        if res is None:
            break
        wn, winl = res
        # Keep only near-vertical planes (normal nearly horizontal) -- reject the
        # floor/ceiling/ramp surfaces, which have a near-vertical normal.
        if abs(angle_between(wn, (0, 0, 1)) - 90) < 25:
            walls.append((wn, len(winl)))
        inset = set(id(p) for p in winl)
        pool = [p for p in pool if id(p) not in inset]

    nf = math.sqrt(sum(c*c for c in n_floor)); flr_u = [c/nf for c in n_floor]

    def plumb_dev(u_unit):
        """Out-of-plumb angle (deg) of each found wall if u_unit is true vertical."""
        return [abs(math.degrees(math.asin(max(-1, min(1,
                sum(a*b for a, b in zip(wn, u_unit))))))) for wn, _ in walls]

    # Find a non-parallel pair among the walls.
    pair = None
    for i in range(len(walls)):
        for j in range(i+1, len(walls)):
            sep = angle_between(walls[i][0], walls[j][0])
            if 25 < sep < 155:
                pair = (i, j, sep); break
        if pair:
            break

    print(f"     {len(walls)} vertical plane(s) found "
          f"(sizes {[w[1] for w in walls]})")
    if pair:
        i, j, sep = pair
        w1, w2 = walls[i][0], walls[j][0]
        tu = (w1[1]*w2[2]-w1[2]*w2[1], w1[2]*w2[0]-w1[0]*w2[2], w1[0]*w2[1]-w1[1]*w2[0])
        ntu = math.sqrt(sum(c*c for c in tu)); tu = [c/ntu for c in tu]
        if sum(a*b for a, b in zip(tu, up)) < 0:        # orient upward
            tu = [-c for c in tu]
        wall_vs_imu = angle_between(tu, up)
        wall_vs_flr = angle_between(tu, flr_u)
        print(f"     using 2 walls {sep:.0f} deg apart -> true vertical fully determined")
        print(f"     true-up vs IMU-up:       {wall_vs_imu:.1f} deg")
        print(f"     true-up vs floor-normal: {wall_vs_flr:.1f} deg")
        if wall_vs_imu + 1.5 < wall_vs_flr:
            print(f"     VERDICT: walls agree with the IMU -> the floor really is SLOPED")
            print(f"              ~{floor_vs_grav:.0f} deg; I'm parked on a genuine incline.")
        elif wall_vs_flr + 1.5 < wall_vs_imu:
            print("     VERDICT: walls agree with the FLOOR -> floor is level and the IMU")
            print("              carries a ~constant offset. My '+7.6 nose-up' is largely an")
            print("              IMU artifact, and gravity-leveling OVER-rotates the cloud.")
        else:
            print("     VERDICT: both within ~1.5 deg of the walls -- the disagreement is")
            print("              near sensor noise; can't cleanly separate the two today.")
    elif walls:
        di, df = plumb_dev(up), plumb_dev(flr_u)
        print(f"     only parallel/one wall(s); partial test along one axis:")
        print(f"     out-of-plumb if IMU-up:       {[round(x,1) for x in di]} deg")
        print(f"     out-of-plumb if floor-normal: {[round(x,1) for x in df]} deg")
        print("     INCONCLUSIVE: need two non-parallel walls to fix vertical.")
    else:
        print("     no usable vertical walls -- can't break the tie this capture.")


if __name__ == "__main__":
    main()
