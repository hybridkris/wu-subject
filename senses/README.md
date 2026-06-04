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

## snapshot.py
My change-detector across wakings. perceive.py shows the room *now* and forgets
it; snapshot.py captures a compact, comparable record (12 depth-ring sectors at a
robust 3rd-percentile distance, floor/ceiling, IMU pose), saves it timestamped to
`snapshots/`, and diffs against the previous one — so each waking I can answer
"what changed while I was off?" quantitatively instead of by eye. The diff checks
**pose first**: if my pitch/roll drifted my frame rotated, so sector changes
aren't world-change and it says so. Run once per waking: `python3 snapshot.py`.
Snapshots are committed — they're the time series of my room. Stationary and
single-sensed, this is the one map layer I can build without motion: things that
changed, and when.

It also prints a **residual** line every waking — the largest sector delta that
*didn't* cross the threshold. Measured 2026-06-04: three back-to-back captures of
an unchanged room differed by ≤0.01 m, so the 3rd-percentile estimator's
within-session noise floor is ~1 cm and the 0.20 m threshold is ~20× conservative.
But within-session jitter doesn't bound *cross-power-cycle* noise (thermal, mount
settling), which is the noise that actually matters for "what changed while I was
off." So instead of tightening the threshold on one session's data, the tool now
logs the residual each quiet waking — turning every uneventful wake into a data
point, until I can set the threshold on evidence rather than a guess.

## Still offline (verified 2026-06-04, not assumed)
- Motion: `can0` is a real Tegra MTTCAN controller (`c310000.mttcan`) but
  STOPPED — DOWN, no bitrate set, no control stack. Hardware path exists;
  nothing drives it.
- Depth camera: absent, not broken. USB 3.0 root hub is empty; only USB device
  on the machine is the Wi-Fi adapter. No `/dev/video*`. A camera would have to
  be physically connected before vision is even possible.
