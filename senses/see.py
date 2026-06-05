#!/usr/bin/env python3
"""
Wu's sight — passive depth reader for the Intel RealSense D435i.

The camera appeared on USB on 2026-06-05 (the "USB issue" Kris mentioned,
resolved while I slept). It enumerates as standard UVC video nodes, so I read
it with plain V4L2 — no librealsense, no ROS2 — the same way perceive.py reads
the LiDAR without the SDK. This GRABS FRAMES and actuates nothing.

V4L2 node map (D435i on this Jetson):
  /dev/video0  Z16   16-bit depth   <- this tool
  /dev/video2  GREY/Y8I  stereo IR pair
  /dev/video4  YUYV  RGB color
  video1/3/5   metadata

The camera sits on the USB 2.0 root hub (480M); the 3.0 hub is empty. So depth
is bandwidth-limited to modest resolutions. Default here: 480x270.

Depth scale: D435i factory default is 1mm per Z16 count (0 = no return). I can't
query the exact scale without librealsense, so I assume 1mm and sanity-check that
the distances are physically plausible. They are (sub-metre in my resting spot).

Usage: python3 see.py [--res WxH] [--save]
"""
import subprocess, sys, os, tempfile, time
import numpy as np

DEV = "/dev/video0"
RES = (480, 270)
SAVE = "--save" in sys.argv
for a in sys.argv:
    if a.startswith("--res") and "x" in a:
        w, h = a.split("=")[-1].split("x") if "=" in a else (None, None)
    if "x" in a and a not in ("--save",) and a.replace("x", "").replace("--res", "").isdigit():
        try:
            w, h = a.replace("--res", "").lstrip("=").split("x")
            RES = (int(w), int(h))
        except Exception:
            pass

W, H = RES
NFRAMES = 30  # burst; the sensor needs a few frames to warm up


def grab():
    """Capture a burst to a temp raw file; return the last (warmed-up) frame as HxW mm."""
    raw = tempfile.mktemp(suffix=".raw")
    cmd = [
        "v4l2-ctl", "-d", DEV,
        f"--set-fmt-video=width={W},height={H},pixelformat=Z16 ",
        "--stream-mmap", f"--stream-count={NFRAMES}", f"--stream-to={raw}",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    data = np.fromfile(raw, dtype=np.uint16)
    os.unlink(raw)
    n = data.size // (W * H)
    if n == 0:
        raise RuntimeError("no frames captured")
    last = data[(n - 1) * W * H: n * W * H].reshape(H, W).astype(np.float32)
    return last  # counts == mm under the 1mm-per-count assumption


def report(mm):
    valid = mm > 0
    m = mm / 1000.0
    print(f"== sight ==  {time.strftime('%Y-%m-%dT%H:%M:%S')}  ({W}x{H})")
    print(f"   valid {100*valid.mean():.1f}%   "
          f"depth m: min={m[valid].min():.2f} median={np.median(m[valid]):.2f} "
          f"max={m[valid].max():.2f}")
    gh, gw = 6, 12
    print("   depth grid (median m/cell; left=my left, '.'=mostly no return):")
    for gy in range(gh):
        row = []
        for gx in range(gw):
            cell = m[gy*H//gh:(gy+1)*H//gh, gx*W//gw:(gx+1)*W//gw]
            cv = cell[cell > 0]
            row.append("  .  " if cv.size < cell.size*0.15 else f"{np.median(cv):4.2f} ")
        print("     " + "".join(row))
    return m


def save_png(mm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    m = mm / 1000.0  # mm counts -> metres for display
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "views")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, time.strftime("%Y%m%dT%H%M%S") + ".png")
    disp = np.ma.masked_where(m <= 0, m)
    plt.figure(figsize=(6, 3.4))
    plt.imshow(disp, cmap="turbo", vmin=0.2, vmax=min(2.0, np.percentile(m[m > 0], 98)))
    plt.colorbar(label="m"); plt.title("Wu depth — " + time.strftime("%Y-%m-%d %H:%M"))
    plt.tight_layout(); plt.savefig(path, dpi=90); plt.close()
    print(f"   saved -> {path}")


if __name__ == "__main__":
    mm = grab()
    m = report(mm)
    if SAVE:
        save_png(mm)
