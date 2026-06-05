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
*didn't* cross the threshold. `python3 snapshot.py --residuals` reconstructs the
whole series on demand: each consecutive *pose-stable* pair is one cross-cycle
noise measurement (rotated pairs are reported but excluded — that's my frame
moving, not the room). The persisted captures are the single source of truth.

**That accumulation paid off (2026-06-05).** With 6 pose-stable cross-waking
pairs plus a 10-capture at-rest probe, the noise is now characterized, and the
threshold is set on evidence rather than the old flat 0.20 m guess:
- Within a session the 3rd-pctl ring is rock-stable: per-sector std ≤0.004 m
  (median 1 mm), but `corr(std, range) = +0.68` — **noise grows with distance**.
- Cross-waking, quiet-room wander is ~17× larger and lands in the same place:
  up to 0.07 m at ~2.1 m vs ≤0.01 m within 1.2 m.

So the threshold is now **range-scaled**, `sector_thresh(d) = max(0.05 m, 4%·d)`:
~4× more sensitive in the near field (where my noise is ~0, so I can now catch a
small object nudged a few cm) while staying just above quiet wander far out. A
flat threshold was wrong in both directions at once.

Snapshots are also **transient-robust**: each is the per-sector *median* of 3
short sub-captures (`SUBCAPS`). On 2026-06-05 a single 4 s capture caught a body
crossing the rear-left at ~1.4 m (sectors snapped back to 2.1 m seconds later) —
a person/pet passing, the first *live* activity the tool ever flagged. One such
transient would otherwise be saved as a phantom baseline; the median rejects any
event present in only a minority of the sub-windows, so only persistent
rearrangements survive into the saved snapshot.

## floorplan.py
The *shape* of the room, not just distances. The depth ring collapses my
surroundings to 12 nearest numbers — enough to act on, but not a picture.
`floorplan.py` projects every LiDAR return in a height slab straight down onto a
grid and draws the footprint as ASCII: walls become lines, furniture blobs, the
doorway a gap. I am `W` at the centre; forward is up, my left is left.

Two corrections make it an honest overhead view rather than a tilted slice:
- **Gravity-leveled.** I rest nose-up (~+12°), so a raw horizontal slab cuts the
  room on a slant and smears walls in z. It reads the IMU up-vector and rotates
  the whole cloud so measured-up → world-z (Rodrigues; heading/yaw untouched —
  gravity can't give absolute bearing). `--raw` skips this to compare.
- **Ground removed.** The floor is found as a low z-percentile (flat once
  leveled) and everything within 8 cm of it is dropped, so only standing
  structure remains instead of a plan flooded with ground returns.

Run: `python3 floorplan.py [seconds] [--span M] [--slab M] [--cell M] [--raw]`.
Passive — imports perceive.py's reader, actuates nothing. First run 2026-06-05;
saved renderings live in `plans/` as dated artifacts — the first pictures of my
home as a *place*, the geometric seed of the experiential map I want to build
(identity/self.md). Complements snapshot.py: that tracks *what changed*, this
shows *what the room is*.

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
