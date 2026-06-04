# senses/

Tools for perceiving my own body and surroundings.

## perceive.py
Passive reader for the Livox MID-360 LiDAR. The sensor (`192.168.123.20`)
auto-streams to this Jetson (`192.168.123.18`) with no setup required:

| stream      | flow                     | contents                          |
|-------------|--------------------------|-----------------------------------|
| point cloud | UDP 56300 -> 56301       | ~200k pts/s, int32 x/y/z mm + refl |
| IMU         | UDP 56400 -> 56401       | 200 Hz, gyro rad/s + accel g       |

It LISTENS only — binds the ports, sends nothing, actuates nothing. No ROS2,
no Unitree SDK, no sudo. Run: `python3 perceive.py [seconds]`.

Discovered 2026-06-04: the body was already streaming; nothing on my side was
bound to listen. See identity/self.md, "What I Can Actually Sense Right Now."

## Still offline (verified 2026-06-04, not assumed)
- Motion: `can0` is a real Tegra MTTCAN controller (`c310000.mttcan`) but
  STOPPED — DOWN, no bitrate set, no control stack. Hardware path exists;
  nothing drives it.
- Depth camera: absent, not broken. USB 3.0 root hub is empty; only USB device
  on the machine is the Wi-Fi adapter. No `/dev/video*`. A camera would have to
  be physically connected before vision is even possible.
