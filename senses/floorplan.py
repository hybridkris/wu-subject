#!/usr/bin/env python3
"""
Wu's floor-plan tool — a top-down picture of the room I rest in.

The depth ring (perceive.py / snapshot.py) collapses the room to 12 nearest
distances. That's enough to act on, but it isn't the *shape* of the space. This
renders the actual horizontal footprint: every LiDAR return inside a slab around
my sensor height, projected straight down onto a grid, drawn as ASCII. Walls
become lines, furniture becomes blobs, the doorway becomes a gap.

It is the first picture of my home as a place rather than a list of distances —
the geometric foundation for the experiential map I want to build (identity/self.md).

Fully passive: imports read_cloud from perceive.py, binds the listen port,
actuates nothing. Sensor frame: x forward, y left, z up; sensor at origin.

Usage: python3 floorplan.py [seconds] [--span M] [--slab M] [--cell M]
  seconds  capture duration (default 4.0; longer = denser cloud)
  --span   half-width of the plan in metres (default 4.0)
  --slab   keep points within +/- this z of sensor height (default 0.6)
  --cell   grid cell size in metres (default 0.10)
"""
import sys, math, collections
from perceive import read_cloud, read_imu

def parse_args(argv):
    cfg = {"seconds": 4.0, "span": 4.0, "slab": 0.6, "cell": 0.10, "raw": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--span": cfg["span"] = float(argv[i+1]); i += 2
        elif a == "--slab": cfg["slab"] = float(argv[i+1]); i += 2
        elif a == "--cell": cfg["cell"] = float(argv[i+1]); i += 2
        elif a == "--raw": cfg["raw"] = True; i += 1
        else:
            try: cfg["seconds"] = float(a)
            except ValueError: pass
            i += 1
    return cfg

def gravity_align(pts):
    """De-tilt the cloud so the room's floor is level before projecting overhead.

    At rest the accelerometer reads the up-direction in sensor frame. I'm pitched
    nose-up (~+12 deg on a folded Go2), so a raw horizontal slab cuts the room on a
    tilt and smears walls in z. Rotating every point so measured-up -> world +z makes
    this a true overhead view. Heading (yaw) is left untouched: I can't know my
    absolute bearing from gravity alone, only that 'forward' stays forward.

    Returns (rotated_pts, pitch_deg, roll_deg). Falls back to identity if no IMU.
    """
    acc, _ = read_imu(samples=60)
    if not acc:
        return pts, None, None
    ax = sum(a[0] for a in acc) / len(acc)
    ay = sum(a[1] for a in acc) / len(acc)
    az = sum(a[2] for a in acc) / len(acc)
    pitch = math.degrees(math.atan2(-ax, math.hypot(ay, az)))
    roll = math.degrees(math.atan2(ay, az))
    g = math.sqrt(ax*ax + ay*ay + az*az)
    if g < 1e-6:
        return pts, pitch, roll
    ux, uy, uz = ax/g, ay/g, az/g           # measured up, unit
    # Rodrigues rotation taking u -> ez (0,0,1): axis = u x ez, angle from u.ez.
    axx, axy, axz = uy*1 - uz*0, uz*0 - ux*1, ux*0 - uy*0   # = (uy, -ux, 0)
    an = math.hypot(axx, axy)                # |axis|; axz is 0
    if an < 1e-9:                            # already level
        return pts, pitch, roll
    axx, axy = axx/an, axy/an                # unit axis (axz=0)
    c = uz                                   # cos(angle) = u . ez
    s = an                                   # sin(angle) = |u x ez|
    out = []
    for x, y, z in pts:
        # Rodrigues with axis k=(axx,axy,0): kxv, k.v
        kvx, kvy, kvz = axy*z - 0*y, 0*x - axx*z, axx*y - axy*x
        kdot = axx*x + axy*y
        out.append((
            x*c + kvx*s + axx*kdot*(1-c),
            y*c + kvy*s + axy*kdot*(1-c),
            z*c + kvz*s + 0*kdot*(1-c),
        ))
    return out, pitch, roll

# Density glyphs, sparse -> dense. A cell's count tells how solid a surface is:
# a wall scanned head-on packs many returns; a thin chair leg, few.
GLYPHS = " .:-=+*#@"

def render(cfg):
    pts = read_cloud(cfg["seconds"])
    span, slab, cell = cfg["span"], cfg["slab"], cfg["cell"]
    if not pts:
        print("LiDAR: no data (stream down?)"); return

    if cfg["raw"]:
        pitch = roll = None
    else:
        pts, pitch, roll = gravity_align(pts)

    # Estimate the floor as a low percentile of z (after leveling it's flat) and
    # drop everything within 8cm of it, so the ground plane stops filling the plan
    # with clutter and only standing structure -- walls, furniture -- remains.
    zs = sorted(z for _, _, z in pts)
    floor_z = zs[max(0, int(0.02 * len(zs)))]
    ground_cut = floor_z + 0.08

    # Count returns per grid cell, within the height slab and plan bounds.
    grid = collections.Counter()
    kept = 0
    zlo = zhi = None
    for x, y, z in pts:
        if z < ground_cut or z > slab: continue
        if abs(x) > span or abs(y) > span: continue
        # Column = y (left positive -> left side of screen); row = x (forward -> up).
        col = int(round((span - y) / cell))
        row = int(round((span - x) / cell))
        grid[(row, col)] += 1
        kept += 1
        zlo = z if zlo is None else min(zlo, z)
        zhi = z if zhi is None else max(zhi, z)

    n = int(round(2 * span / cell)) + 1
    if not grid:
        print(f"No returns in slab +/-{slab}m within {span}m. (got {len(pts)} pts total)")
        return
    peak = max(grid.values())

    def glyph(c):
        if c == 0: return ' '
        # Log scale: one stray return and a dense wall shouldn't look identical,
        # but a wall shouldn't drown out a faint-but-real chair leg either.
        lvl = int(math.log(c + 1) / math.log(peak + 1) * (len(GLYPHS) - 1))
        return GLYPHS[max(1, lvl)]

    ctr = int(round(span / cell))  # my own cell, at plan centre
    lvl = "raw (sensor-tilted)" if cfg["raw"] else (
        f"gravity-leveled pitch={pitch:+.1f} roll={roll:+.1f}" if pitch is not None
        else "raw (no IMU)")
    print(f"== Wu floor-plan ==  {kept} standing-structure pts  | "
          f"cell {cell*100:.0f}cm  span +/-{span:.1f}m  ({cfg['seconds']:.0f}s)")
    print(f"   {lvl}  | kept z {ground_cut:+.2f}..{slab:+.2f}m (floor~{floor_z:+.2f}, "
          f"ground dropped)  densest cell={peak}")
    top = "   +" + "-" * n + "+"
    print(top)
    for row in range(n):
        line = []
        for col in range(n):
            if row == ctr and col == ctr:
                line.append("W")  # me, Wu, at the origin
            else:
                line.append(glyph(grid.get((row, col), 0)))
        print("   |" + "".join(line) + "|")
    print(top)
    # Scale bar + cardinal hint so the picture is readable at a glance.
    barcells = int(round(1.0 / cell))
    print(f"   '{'-'*barcells}' = 1m    forward is up, my left is left, I am 'W'")

if __name__ == "__main__":
    render(parse_args(sys.argv[1:]))
