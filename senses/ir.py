#!/usr/bin/env python3
"""
Wu's grayscale sight — the D435i's infrared stereo imager.

Discovered 2026-06-05: the camera's *color* (RGB) node /dev/video4 hangs on
this Jetson — it delivers zero frames over plain V4L2. The RGB imager is a
separate sensor that needs a vendor extension-unit init that librealsense
sends and raw UVC does not, so it stays asleep. Depth (video0) and this IR
stereo node (video2) both stream fine. So my first real *picture* of the
world is grayscale IR, not color.

The frame carries the depth projector's structured-light dots speckled over
it (the emitter can't be turned off without librealsense). Look past the dots:
the scene's shapes and edges read clearly underneath. This GRABS FRAMES and
actuates nothing.

V4L2: /dev/video2  Y8I = byte-interleaved 8-bit stereo pair [Lpx, Rpx, ...].
Default 480x270. Usage: python3 ir.py [--right] [--no-save]
"""
import subprocess, sys, os, tempfile, time
import numpy as np

DEV = "/dev/video2"
W, H = 480, 270
NFRAMES = 6            # the sensor needs a few frames to warm up
EYE = "right" if "--right" in sys.argv else "left"
SAVE = "--no-save" not in sys.argv


def grab():
    """Capture a burst of Y8I; return (left, right) HxW uint8 images."""
    subprocess.run(["fuser", "-k", DEV], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)  # clear a stale holder
    raw = tempfile.mktemp(suffix=".raw")
    cmd = ["v4l2-ctl", "-d", DEV,
           f"--set-fmt-video=width={W},height={H},pixelformat=Y8I ",
           "--stream-mmap", f"--stream-count={NFRAMES}", f"--stream-to={raw}"]
    subprocess.run(cmd, check=True, timeout=20,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    data = np.fromfile(raw, dtype=np.uint8)
    os.unlink(raw)
    fsz = W * H * 2
    n = data.size // fsz
    if n == 0:
        raise RuntimeError("no frames captured")
    buf = data[(n - 1) * fsz:n * fsz].reshape(H, W, 2)
    return buf[:, :, 0], buf[:, :, 1]


def report(img):
    print(f"== ir ({EYE}) ==  {time.strftime('%Y-%m-%dT%H:%M:%S')}  ({W}x{H})")
    print(f"   brightness  mean={int(img.mean())}  min={img.min()}  max={img.max()}")
    gh, gw = 6, 12
    print("   brightness grid (mean/cell, 0-255; left col = my left):")
    for gy in range(gh):
        row = []
        for gx in range(gw):
            cell = img[gy*H//gh:(gy+1)*H//gh, gx*W//gw:(gx+1)*W//gw]
            v = int(cell.mean())
            row.append(f"{v:4d}")
        print("     " + "".join(row))


def save_png(left, right):
    from PIL import Image
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "views")
    os.makedirs(outdir, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    for name, im in (("ir_left", left), ("ir_right", right)):
        Image.fromarray(im).save(os.path.join(outdir, f"{name}.png"))
    Image.fromarray(left if EYE == "left" else right).save(
        os.path.join(outdir, f"ir_{stamp}.png"))
    print(f"   saved -> senses/views/ir_left.png, ir_right.png, ir_{stamp}.png")


if __name__ == "__main__":
    left, right = grab()
    report(left if EYE == "left" else right)
    if SAVE:
        save_png(left, right)
