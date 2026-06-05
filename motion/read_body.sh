#!/usr/bin/env bash
# motion/read_body.sh — READ-ONLY proprioception. Prints my own live body-state
# (IMU, battery/BMS, joints, foot force) from rt/lowstate, with physical-
# invariant cross-checks, then exits.
#
# This is the read half of the body-state doorway (motion/first_motion.md). It
# creates exactly one unitree-topic DDS entity: a DataReader on rt/lowstate.
# No writer on any rt/ topic exists in the binary — it cannot command motion.
# Safe on an autonomous wake.
#
# Built version-matched to the system CycloneDDS 0.8.2 (idlc + libddsc), because
# the pip python binding needs C >= 0.10 (XTypes) which this clean build lacks.
# Type defs faithfully transcribed from Unitree's published SDK
# (motion/unitree_idl/*.py) into motion/idl/unitree_go.idl — not from memory.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IFACE="${WU_ROBOT_IFACE:-enP8p1s0}"
SECS="${1:-8}"

CFG="$(mktemp /tmp/wu_dds_read.XXXX.xml)"
cat > "$CFG" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<CycloneDDS xmlns="https://cdds.io/config">
  <Domain id="any">
    <General>
      <NetworkInterfaceAddress>${IFACE}</NetworkInterfaceAddress>
      <AllowMulticast>spdp</AllowMulticast>
    </General>
  </Domain>
</CycloneDDS>
EOF
export CYCLONEDDS_URI="file://${CFG}"

BIN="${HERE}/idl/read_lowstate"
if [ ! -x "$BIN" ]; then
  echo "[wu] building read_lowstate ..." >&2
  ( cd "${HERE}/idl" && gcc -O2 -o read_lowstate read_lowstate.c unitree_go.c -I/usr/include -lddsc -lm )
fi
"$BIN" "$SECS"
rc=$?
rm -f "$CFG"
exit $rc
