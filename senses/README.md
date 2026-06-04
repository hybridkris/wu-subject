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

## Still offline
- Motion: `can0` (CAN bus) is down; no robot-control stack installed.
- Depth camera: planned, USB issue unresolved (unconfirmed).
