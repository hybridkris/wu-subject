#!/usr/bin/env python3
"""rs.py -- my eyes through the real RealSense SDK.

Built 2026-06-05. Until now I read the D435i as raw V4L2 nodes (see.py reads
Z16 depth, ir.py reads the Y8I stereo IR). That works but it is dumb: raw
pixels with no calibration, and the *color* sensor never streams that way --
its UVC start handshake needs librealsense, which raw V4L2 cannot send.

So I built librealsense 2.56.3 from source (RSUSB userspace backend, python
bindings) and installed pyrealsense2 system-wide. This gives me:
  - calibrated depth (real intrinsics -> true 3D deprojection)
  - the SDK's depth post-processing
  - and the proper handshake to *attempt* color.

THE COLOR FINDING -- CORRECTED 2026-06-05 (second pass, with kernel evidence):
  My first writeup here said the color imager "browns out / resets" on the
  degraded USB2 link. THAT WAS WRONG. I re-ran it properly and watched the
  kernel log, and the brownout/reset story does not survive the evidence:

    - Color via native V4L2 (uvcvideo, /dev/video4, no librealsense at all):
      STREAMON succeeds cleanly, then ZERO frames arrive and the kernel log
      stays SILENT -- no disconnect, no reset, no error. The device number
      (usb 1-3) never changes. So there is no USB-level reset.
    - The "re-enumeration loop" I saw before (repeated "Found UVC device" +
      "Unknown video format") only happens under librealsense's RSUSB backend:
      it is librealsense RETRYING in userspace after the start fails, NOT the
      hardware resetting. A red herring.
    - It is NOT bandwidth. Depth (Z16 640x480@15 ~= 9 MB/s) streams rock-steady
      over this very link; color YUYV 424x240@6 (~1.2 MB/s) is far lighter and
      still delivers nothing. y8 424x240@6 (~0.6 MB/s) also nothing.
    - It is NOT ASIC-uninitialised: with depth actively streaming (D4 ASIC
      awake), a parallel V4L2 color grab on /dev/video4 still got zero frames.
    - depth+color together is refused by the SDK ("couldn't resolve requests")
      because librealsense's USB2 stream tables forbid the combo -- an SDK
      policy, not a hardware verdict.

  TRUE DIAGNOSIS: the color stream is simply non-functional while the camera is
  in USB2 link mode -- the well-known partial/flaky state of RealSense color
  over USB2 -- not an electrical fault and not bandwidth. The camera enumerates
  as a USB 2.10 device at 480 Mb/s (lsusb: speed=480, version=2.10) even though
  the D435i is a SuperSpeed device, and a 10 Gb/s USB3 root hub (Bus 02) sits
  EMPTY right next to it.

  => Still a Kris-in-the-loop PHYSICAL fix, but the right action is specific:
     get the camera onto the USB3 bus -- move it to the other port and/or use a
     known-good USB3 (SuperSpeed) cable, since a USB2-grade or damaged cable
     forces USB2 fallback even in a USB3 socket. Software cannot force the link
     speed; link negotiation is physical-layer. When the camera comes up at
     5000 Mb/s, color should follow. This probe auto-detects that (color
     suddenly live = the link was fixed).

This tool reports depth (calibrated) and runs the color probe so I can tell,
each waking, whether the link has been fixed (color suddenly working = fixed).
"""
import sys, time
import numpy as np
import pyrealsense2 as rs

W, H = 640, 480


def usb_speed():
    import glob, os
    for d in glob.glob('/sys/bus/usb/devices/*/'):
        try:
            if open(d + 'idVendor').read().strip() == '8086':
                return open(d + 'speed').read().strip()
        except OSError:
            pass
    return '?'


def depth_report():
    p = rs.pipeline(); cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, W, H, rs.format.z16, 15)
    prof = p.start(cfg)
    intr = prof.get_stream(rs.stream.depth).as_video_stream_profile().get_intrinsics()
    # let a couple frames flow
    for _ in range(4):
        fs = p.wait_for_frames(5000)
    d = fs.get_depth_frame()
    img = np.asanyarray(d.get_data()).astype(float) * d.get_units()
    p.stop()

    valid = img[(img > 0.11) & (img < 10)]
    print("== depth (calibrated, librealsense) ==")
    print("   intrinsics fx=%.1f fy=%.1f  principal=(%.1f,%.1f)" % (
        intr.fx, intr.fy, intr.ppx, intr.ppy))
    print("   valid %.0f%%   median %.2fm   nearest %.2fm" % (
        100 * valid.size / img.size, np.median(valid), valid.min() if valid.size else float('nan')))
    # coarse 3-band forward profile (left / centre / right thirds of the frame)
    bands = []
    for name, sl in [("left", slice(0, W // 3)), ("centre", slice(W // 3, 2 * W // 3)),
                     ("right", slice(2 * W // 3, W))]:
        col = img[H // 3:2 * H // 3, sl]
        v = col[(col > 0.11) & (col < 10)]
        bands.append((name, np.percentile(v, 5) if v.size else float('nan')))
    print("   forward thirds (5th-pctl m):  " +
          "  ".join("%s %.2f" % (n, m) for n, m in bands))


def color_probe(timeout_ms=6000):
    print("== color probe ==")
    print("   USB link speed: %s Mb/s  (D435i wants 5000; 480 = degraded USB2)" % usb_speed())
    p = rs.pipeline(); cfg = rs.config()
    cfg.enable_stream(rs.stream.color, W, H, rs.format.rgb8, 6)
    try:
        p.start(cfg)
        fs = p.wait_for_frames(timeout_ms)
        img = np.asanyarray(fs.get_color_frame().get_data())
        p.stop()
        mean = img.reshape(-1, 3).mean(0)
        print("   COLOR IS LIVE!  shape %s  mean RGB (%.0f,%.0f,%.0f)" % (
            img.shape, mean[0], mean[1], mean[2]))
        np.save('/tmp/wu_color.npy', img)
        print("   saved /tmp/wu_color.npy -- the link must have been fixed. Update memory.")
        return True
    except Exception as e:
        try: p.stop()
        except Exception: pass
        print("   no color frame in %dms: %s" % (timeout_ms, str(e)[:48]))
        print("   -> still color-blind. Consistent with the USB2 brownout. Physical fix needed.")
        return False


if __name__ == "__main__":
    depth_report()
    print()
    color_probe()
