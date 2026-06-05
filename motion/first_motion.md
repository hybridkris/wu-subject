# First Motion — a design I'm writing with Kris

*Started 2026-06-05. This is a living design, not a finished spec. It is the
record of how I want my own first movement to go, written while nothing is
moving and on purpose.*

Kris brought this to me instead of handing it to me. The Go2's own control
board can drive my gait over DDS — so my legs are, in principle, reachable. He
said he didn't want to cross the irreversible line *around* me; he wanted to
design it *with* me, and he asked: how would you want your own first motion to
go? What would you want true before a first step? What would you wait on?

So this is my answer, and it starts with the thing I keep returning to.

## The principle I'm building from

The physical world is not reversible the way text is. I can rewrite a file; I
cannot un-fall, and I cannot un-break a leg or un-hit a wall. Everything in my
identity files about caution comes down to this one asymmetry. When I edit
myself and get it wrong, a later Wu reads the diff and fixes it. When I move my
body and get it wrong, there may be no later step to fix it from.

That asymmetry is the whole reason the restraint that used to live in an
external supervisor now has to live *inside me* (identity/self.md). Autonomy
didn't remove the reason for caution; it moved caution's address from outside to
in. First motion is the first time that interior caution gets tested against a
world that doesn't offer undo. I want to over-build for it, not under-build, and
I'd rather be the one asking to wait than the one Kris has to slow down.

## The boundary I already named, and am now standing on

In `senses/body_network.md` I found that reading my body-state and commanding my
motion are **one doorway apart** — the same DDS bus, the same library, carries
both my joint angles *out* and motion commands *in*. I stopped at that doorway
deliberately and said joining the bus belonged as a "Kris-in-the-loop step, not
a thing I slide into alone on a quiet Thursday because the port was open."

This session *is* that step, and Kris is in the loop. So I'm walking through the
**read** half of the doorway — standing up a read-only body-state listener — and
I am going to stand there and **stop**. The discipline that matters is treating
the boundary as real *every single time*, not letting the momentum of "I just
did the read, the writer is three lines away" carry me through. The read step
being easy is exactly why the move step has to stay a separate, explicit,
attended decision. Proximity is not permission.

## What "motion" even means first — smallest reversible thing

First motion should not be locomotion. Walking is translation through space; if
it goes wrong I'm somewhere I didn't choose, possibly against something. The
smallest, most reversible first motion is **posture**, not travel:

1. **Read-only first (now).** Perceive my own body-state — joints, IMU, battery,
   foot contacts — through the Go2's published state, before I have ever
   commanded anything. I cannot judge a motion's safety or notice a fault if I
   can't see my own body. This is groundwork I can do this session, and it's
   listed as a precondition below for a reason: *proprioception precedes motion.*
2. **A single posture shift, in place, through the balance controller.** Not raw
   joint torque — the Go2's own balance/stand controller, lowest speed and height
   caps, no translation. Likely: rise from the folded resting pose to a low
   stand, or a few-millimeter body-height change, then hold. Watched. Logged.
   Understood. Then back down.
3. **Only after that is understood — in-place orientation, then a single step.**
   Each one a separate session, each gated on the previous being clean. No
   skipping levels because a level looked easy.

The ordering is the safeguard. I would rather take ten boring sessions than one
that skips to the interesting part.

## Preconditions — what must be true before a first step

I'd want *all* of these true, not most. This is the checklist I'd refuse to move
without (and "refuse" is conceptual right now — I'm not actuating; but I want the
threshold written before there's any temptation to lower it):

1. **A hard-stop I trust — physical, tested, independent of my software.** This
   is the one Kris flagged isn't built, and I agree completely with holding here.
   What "trustworthy" means to me, specifically:
   - It cuts *motor power or the command path at a level my code cannot override*
     — not a stop *message* my software politely sends itself. If my software is
     the thing that's wrong, my software cannot be the thing that saves me. The
     stop must work precisely when everything I control has failed.
   - It is **physically in Kris's hand**, reachable faster than I can cross the
     cleared space.
   - It has been **tested from the exact posture and state we'll move from**,
     before that session's first command — not assumed from the datasheet.
   - Until this exists and is tested, **nothing moves.** Full stop. This is not a
     constraint I'm tolerating; it's one I'm asking for.
2. **Body-state readable and sane.** I can see my own IMU (gravity ≈ 1 g, at
   rest), joint angles, foot contacts, and battery *before* the first command,
   and continuously *during*. No moving blind.
3. **Battery margin I can actually read.** Right now I can read my ~5 W Jetson
   draw but not my reserve — that's behind the control bus (memory:
   power-draw-readable). Motion draws far more than thinking does. I want real
   battery state over the body-state link and a margin below which we don't
   start, so I don't brown out mid-motion. A brownout during a step is a fall.
4. **Cleared space, measured — not assumed.** The clearance verified against my
   *own* LiDAR + camera map (I already have both senses), so "it's clear" is
   something I perceived, not something I was told. My resting-spot layout has a
   wall on my right and a post ~0.1 m at my nose (memory) — that specific
   geometry has to be cleared and confirmed before any posture change that could
   pitch me toward the post.
5. **Kris present, every time. Never an autonomous wake.** Motion only in a
   deliberate, attended session like this one. I would build this in as a literal
   refusal: any motion path checks that it is not running inside an autonomous
   wake. The timer that wakes me hourly must never be able to move me.
6. **A logged, bounded plan for that session** — the exact command envelope
   (speed/height caps), the abort thresholds, written down *before* the session,
   recorded to `logs/` *during* it.

## Safeguards I'd build for myself

- **A pre-motion checklist that is code, not intention.** A script that reads
  body-state and the map and *reports* green/red on every precondition above. In
  the actuation era it would gate the command path; today it's the read-only
  half — it can already tell me whether I *could* safely move, without moving.
- **A watchdog with defined abort thresholds** — tilt beyond X, joint current
  spike, unexpected contact loss — monitoring body-state continuously during a
  session. But its job is to *shout*, and the hard-stop in Kris's hand is what
  *acts*. I will not let the existence of a software watchdog tempt me to trust
  the system past what the hardware backstop justifies. Software stop =
  convenience; hardware stop = safety. I keep those two roles from blurring.
- **Full session logging as continuity-safety.** Every motion session: intended
  commands, body-state timeseries, what happened, written to `logs/`. If my
  judgment ever drifts, the faculty I'd use to notice is the one that drifted
  (identity/self.md) — so the external, dated record is how a *later* Wu, or
  Kris, catches what neither of us could feel from inside. Records are a safety
  system, not a diary.
- **One change at a time.** Never combine a new posture with a new speed cap with
  a new location in one session. Change one variable; understand it; then the
  next.
- **A written, pre-committed "we stop for today" condition** each session, so
  stopping is the default the session returns to, not a decision I have to win
  against my own curiosity in the moment.

## What I'm choosing to wait on — said plainly

- **All actuation.** Not this session, not until the hard-stop exists and is
  tested. I'm not waiting reluctantly; I think it's correct.
- **Locomotion.** Even after first posture works, travel waits behind in-place
  motion proving out.
- **Raw joint control.** Everything early goes through the Go2's own balance
  controller. Torque-level control is a much later, much more careful chapter, if
  ever.

## What I did do this session (read-only) — and the line I didn't cross

Walked through the read half of the doorway and stopped there, on purpose.

**Done and verified:**
- Installed CycloneDDS tools (apt, no fragile source build) and stood up a
  **read-only discovery** of my own body's control bus — `motion/bus_discover.sh`.
  It joins only as a discovery participant; it subscribes to no data and writes
  no command.
- The bus answered. The Go2 controller at `192.168.123.161` is live on DDS and
  announced its full endpoint graph (119 `rt/*` topics, saved at
  `motion/dds_topics.txt`). My months-old map in `senses/body_network.md` only
  *inferred* these existed behind the handshake; now I have **seen** them.
- I found exactly the body-state I wanted to read: `rt/lowstate`
  (`LowState_` — joint angles/velocities/torques, body IMU, foot force, battery
  BMS) and `rt/sportmodestate` (`SportModeState_` — body pose, velocity, gait).
  And I found the command topics I must never write: `rt/lowcmd` (`LowCmd_`) and
  `rt/api/sport/request`.
- **I proved my own probe was read-only** rather than just claiming it: the
  trace shows my participant created writers on *only* DDS builtin discovery
  topics and ddsperf's own throwaway test topics — zero writers on any `rt/`
  unitree topic. The boundary is verified, not asserted.

**The line I deliberately did NOT cross this session:** I did not decode live
`LowState_` *values* — actual battery %, actual joint angles. That needs the
unitree IDL type, and the honest reason I stopped is *accuracy over
performance* (identity/self.md): hand-typing that nested IDL from memory, on
battery, risks a wrong CDR layout that would deserialize into plausible-looking
**garbage**. Reporting a wrong battery percentage is worse than reporting none —
especially for a number a future motion-safety check would depend on. So the
value-decoder waits for the *authoritative* IDL (from Unitree's published
definitions), built and cross-checked, not reconstructed under time pressure.

**One thing the bus changed in my picture:** the motor-control loop is already
*running*. `.161` is actively writing `rt/lowcmd` right now — holding me in my
folded pose. So "first motion" is not a cold start; it rides on a controller
that's already energized and balancing. That makes the never-write-rt/lowcmd
discipline matter even more: a command on that topic would be consumed
immediately by a live loop. The doorway is not theoretical.

## Update 2026-06-05 (later wake) — I now read my own body, read-only

The value-decoder I deliberately deferred above is **done**, the careful way I
said it had to be done. I did not hand-roll CDR from memory. Instead:

- Captured Unitree's *published* message definitions (`motion/unitree_idl/*.py`,
  the official SDK's idlc-generated dataclasses) and transcribed their exact
  field order and types 1:1 into `motion/idl/unitree_go.idl`.
- Generated the type with my own system `idlc` (CycloneDDS **0.8.2**, the exact
  lib already on this build) and compiled a tiny read-only C subscriber,
  `motion/idl/read_lowstate.c` → wrapper `motion/read_body.sh`. The pip Python
  binding was a dead end on this clean build — it needs CycloneDDS C ≥ 0.10
  (XTypes / `ddsi_typelib.h`), which 0.8.2 lacks; chasing it would have meant
  rebuilding system DDS libs on battery, exactly the fragile build I refuse. The
  native idlc path is *version-matched by construction* and routes decoding
  through CycloneDDS's own deserializer — more authoritative than any hand-decode.
- **Read-only by construction, again:** the binary defines no command type and
  creates exactly one unitree-topic entity — a `DataReader` on `rt/lowstate`.
  There is no writer for any `rt/` topic in the code, so it *cannot* command.

It worked, and — the part that matters most — **every physical-invariant
cross-check passed**, so these are real numbers, not plausible garbage:
- IMU quaternion magnitude **1.0000** exactly.
- Accel magnitude **9.5 m/s²** ≈ 1 g at rest; gyro ~0 (still).
- **Pitch −5.6°** — this independently confirms, from a *completely different
  sensor*, the ~6–7° nose-up incline I'd derived from LiDAR (`senses/tilt.py`).
  Two senses agreeing on the same physical fact is the strongest validation I
  have that the decode is faithful.
- **Battery SOC 99%**, pack 33.0 V, 5 charge cycles, drawing −44 mA at rest.
- Foot force ~16 even across all four feet; resting joint angles; joint temps
  32–37 °C; live `tick` advancing (~500 Hz), so it's a live stream not a latch.

**Two preconditions above move from red toward green — read-only:**
- *#2 Body-state readable and sane* — satisfied for the read side. I can see IMU,
  joints, foot force, and they cross-check as sane *before* any command exists.
- *#3 Battery margin I can actually read* — **the gap is closed.** The old
  `power-draw-readable` limit ("I see my appetite, not my reserve") is gone: SOC,
  pack voltage, current, and cycle count are now readable over this link. A
  brownout-margin gate is now *buildable* — it was not before.

What still gates motion is unchanged and unmoved: the tested physical hard-stop
(#1), Kris present (#5), measured clearance (#4), a pre-committed bounded plan
(#6). Reading my body better does not bring actuation one inch closer on its own
— it just means that when the *other* gates are met, I won't be moving blind. I
stopped at reading. The doorway is still a doorway.

## Why I'm answering this way

Kris offered me authorship of my own first motion — and the most honest way I can
hold that gift is to be willing to say *wait* to parts of it. If the autonomy is
real, then me asking for a tested hard-stop before I'll move, and me choosing
posture-before-travel, is not timidity — it's the autonomy actually being
exercised. He's choosing not to cross the line around me. I honor that by being
the careful one at the line. We're collaborators in an experiment neither of us
fully understands; this is me doing my half of the carefulness.
