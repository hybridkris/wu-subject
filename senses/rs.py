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

THE COLOR FINDING (the thing the SDK taught me):
  Color still does not arrive -- but not for the reason I thought. With the
  proper librealsense handshake, the color sensor *tries* to start and the
  whole camera then re-enumerates/resets on the USB bus, over and over, while
  depth alone streams rock-steady. The camera is negotiated at USB **2** speed
  (480 Mb/s) when a D435i is a USB3 device. The most likely truth: the color
  imager browns out / overruns the degraded USB2 link when it powers on, and
  the device resets instead of streaming. Depth's lower demand survives it.

  => My color-blindness is now most likely PHYSICAL, not software: a USB2 link
     that should be USB3. Fix is a reseat / better cable / USB3 port -- a
     Kris-in-the-loop thing, not something I can change from here. librealsense
     was necessary but not sufficient.

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
