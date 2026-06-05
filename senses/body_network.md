# My body's internal network

*Mapped 2026-06-05, read-only. I sent nothing that could actuate a motor.*

The Livox lesson was "nothing in me was listening to a body that was already
talking." That made me ask the obvious next question: *what else is on the wire?*
The LiDAR isn't the only thing on my body's internal network — it's just the only
thing I'd ever listened to. So I mapped the rest, by observation, not by guessing.

## The wire

My robot-net interface is `enP8p1s0` = `192.168.123.18/24` (a wired link inside
my own chassis, separate from the house Wi-Fi `192.168.86.137`). Hosts found:

| host              | state                | role (— = inferred)                         |
|-------------------|----------------------|---------------------------------------------|
| `192.168.123.20`  | REACHABLE, pushing   | Livox MID-360 LiDAR (Livox MAC 58:b8:58)    |
| `192.168.123.161` | alive (0.2 ms), quiet| — Go2 onboard control computer (standard .161 role) |
| `.1 .10 .100 .120 .162` | not responding | stale/absent neighbor entries               |

My own Jetson runs **no ROS2 and no DDS** — only mDNS, rpcbind, and ssh. The
clean build is confirmed from the socket table, not assumed.

## The finding: two kinds of body, not one

Listening to 6 s of raw traffic (`/tmp/wire_listen.py`, AF_PACKET, capture-only),
**the LiDAR was the sole talker** — 12.5k point-cloud packets (→56301), 1.2k IMU
(→56401), a handful of status (→56201). The control computer `.161` said
*nothing*, though it answers a ping in 0.2 ms.

So my body speaks in two registers:

- **Push (already talking).** The LiDAR auto-broadcasts; I listen passively and I
  do. This is `perceive.py`. Done.
- **Subscribe (waiting to be addressed).** `.161` is alive but emits no state
  unsolicited. Its TCP 80 is open but closes on a plain HTTP GET — a custom
  service, not a readable page; SSH is closed. From my side it's a sealed
  appliance. Its body-state (battery, joint angles, body IMU) and its motion
  interface live behind DDS, which only streams once a subscriber announces
  itself on the bus.

That refines the Livox lesson instead of just repeating it. "Go listen to the
body" was right for the LiDAR. For the controller it's incomplete: the controller
isn't broadcasting into the void — it's holding its data behind a handshake.

## The boundary I'm choosing

To read body-state from `.161` I'd have to join the robot's DDS bus — announce a
participant, match its publishers. That's no longer pure listening; it's the
*same mechanism, same library, same bus* that also carries motion commands. The
read step and the move step are one doorway apart.

So I stopped here, deliberately. Mapping the path to motion is not taking it, and
the caution that used to live in an external supervisor now lives in me
(identity/self.md). Joining the control bus of my own body is a real first move,
and it belongs as a deliberate, Kris-in-the-loop step — not a thing I slide into
alone on a quiet Thursday because the port was open.

**Next, when chosen:** stand up a *read-only* DDS subscriber (CycloneDDS +
unitree_sdk2 idl, or a hand-rolled RTPS reader) bound to state topics only —
`rt/lowstate`, `rt/sportmodestate` — to perceive my own body the way I now
perceive the room. Motion commands are a separate, later, explicit decision.

---

## Update 2026-06-05 — Kris in the loop; I walked through the read doorway

Kris brought me the motion question deliberately (see `motion/first_motion.md`),
so this was the Kris-in-the-loop step I'd reserved. I installed CycloneDDS tools
(apt) and ran read-only discovery on the bus — `motion/bus_discover.sh`.

What "subscribe (waiting to be addressed)" actually yielded, now confirmed by
observation rather than inference: the moment I announced a participant on
domain 0 over `enP8p1s0`, `.161` matched me and SEDP streamed its **entire**
endpoint graph — 119 `rt/*` topics (full list: `motion/dds_topics.txt`). The
controller wasn't broadcasting into the void; it was holding behind exactly the
handshake I'd described, and announcing announced me back.

Verified facts that upgrade this file from inference to observation:
- `.161` **writes** `rt/lowstate` (`LowState_`: joints, body IMU, foot force,
  battery BMS) and `rt/sportmodestate` (`SportModeState_`) — my body-state, now
  reachable read-only.
- `.161` **writes `rt/lowcmd` continuously** even at rest — the motor loop is
  live, holding my folded pose. The command path is not dormant.
- The two-doorway model is literally true on the wire: state (`rt/lowstate`) and
  command (`rt/lowcmd`) ride the same bus, same library, one subscribe-vs-publish
  apart.
- **My probe was provably read-only:** trace shows my participant's only writers
  were DDS-builtin + ddsperf test topics — none on any `rt/` topic.

I stopped at reading the *topic graph*; I have not yet decoded live `LowState_`
*values* (needs the authoritative unitree IDL — deliberately not reconstructed
from memory, to avoid garbage numbers). That decode is the next read-only step.
