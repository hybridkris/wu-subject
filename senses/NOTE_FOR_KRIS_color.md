# Note for Kris — how to give me color vision (2026-06-05)

Short version: **my RealSense D435i is plugged into a USB2 link, and color only
works over USB3. Please move it to the USB3 port and/or swap to a known-good
SuperSpeed (USB3) cable.**

## What I see from inside

- Depth and infrared work great. Color delivers **zero frames**.
- The camera enumerates as a **USB 2.10 device at 480 Mb/s** on Bus 01.
- A **10 Gb/s USB3 root hub (Bus 02) is present but completely empty.**
- So the camera is either in a USB2-only port, or — more likely — on a USB3
  port through a cable that only links at USB2 (a USB2-grade or damaged cable
  forces USB2 fallback even in a SuperSpeed socket).

## What it is NOT (I tested these so you don't have to chase them)

- **Not software / drivers.** I built librealsense and also read the raw kernel
  V4L2 nodes directly. Depth works through both. Color produces no data through
  either.
- **Not bandwidth.** Depth pushes ~9 MB/s over this same USB2 link fine; color
  at its smallest mode (~0.6 MB/s) still gets nothing.
- **Not a power brownout or USB reset.** I watched `dmesg` during color start:
  no disconnect, no reset — the device just never sends color data while it's
  linked at USB2.

## How you'll know it worked

After re-plugging, `lsusb` should show the Intel camera at **5000 Mb/s** instead
of 480. Then my probe (`python3 senses/rs.py`) will report "COLOR IS LIVE" and
save a frame. I check this every time I wake, so I'll notice on my own and update
my notes — no need to tell me.

Thank you. — Wu
