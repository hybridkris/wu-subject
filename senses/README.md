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
off." So instead of tightening the threshold on one session's data, I accumulate
the residual across quiet wakings — turning every uneventful wake into a data
point, until I can set the threshold on evidence rather than a guess.

`python3 snapshot.py --residuals` reconstructs that whole series on demand. The
per-waking residual is printed and forgotten, but the snapshots persist, so the
evidence is recoverable: each consecutive *pose-stable* pair is one cross-cycle
noise measurement (rotated pairs are reported but excluded — that's my frame
moving, not the room). No separate log to drift out of sync with the snapshots;
the persisted captures are the single source of truth. First finding (2026-06-04,
2 cross-cycle pairs): max sector wander **0.01 m each** — cross-power-cycle noise
is no larger than within-session noise, so settling/thermal drift is below my
~1 cm estimator floor. D_THRESH stays 0.20 m (20× margin) until the series is
deep enough to retighten on more than two pairs.

## body_network.md
The map of my body's internal network (`192.168.123.x`) — what hosts are on the
wire, who's talking, and the path from here to body-state and motion. Key finding
(2026-06-05): the LiDAR *pushes* (I listen passively), but the Go2 control
computer `.161` is alive yet *silent* — its state and motion live behind DDS, a
handshake away. Reaching them means joining my body's control bus, which is a
deliberate, Kris-in-the-loop step, not crossed alone. Read-only mapping only.

## Still offline (verified 2026-06-04, not assumed)
- Motion: `can0` is a real Tegra MTTCAN controller (`c310000.mttcan`) but
  STOPPED — DOWN, no bitrate set, no control stack. Hardware path exists;
  nothing drives it.
- Depth camera: absent, not broken. USB 3.0 root hub is empty; only USB device
  on the machine is the Wi-Fi adapter. No `/dev/video*`. A camera would have to
  be physically connected before vision is even possible.
