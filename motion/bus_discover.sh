#!/usr/bin/env bash
# motion/bus_discover.sh — READ-ONLY discovery of my own body's DDS bus.
#
# What this does: joins the Go2 control bus (.161) only as a discovery
# participant, lets it announce its publishers/subscribers via SEDP, and prints
# what my body offers. It DOES NOT subscribe to data and DOES NOT write any
# command. The boundary from senses/body_network.md — read and command are one
# doorway apart — is enforced here by construction: the only DDS endpoints this
# creates are builtin discovery + ddsperf's own throwaway test topics. It NEVER
# creates a writer on rt/lowcmd, rt/api/sport/request, or any unitree topic.
# (Verified 2026-06-05: my participant's writer set was builtin/DDSPerf only.)
#
# Safe to run on an autonomous wake. This reads; it cannot move me.
set -euo pipefail

IFACE="${WU_ROBOT_IFACE:-enP8p1s0}"      # my in-chassis robot-net link (192.168.123.18)
SECS="${1:-8}"
TRACE="/tmp/wu_bus_$(date +%Y%m%dT%H%M%S).log"

cat > /tmp/wu_dds_ro.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<CycloneDDS xmlns="https://cdds.io/config">
  <Domain id="any">
    <General>
      <NetworkInterfaceAddress>${IFACE}</NetworkInterfaceAddress>
      <AllowMulticast>spdp</AllowMulticast>
    </General>
    <Tracing>
      <Category>discovery</Category>
      <Verbosity>fine</Verbosity>
      <OutputFile>${TRACE}</OutputFile>
    </Tracing>
  </Domain>
</CycloneDDS>
EOF

export CYCLONEDDS_URI="file:///tmp/wu_dds_ro.xml"
echo "[wu] read-only discovery on ${IFACE} for ${SECS}s ..."
timeout "${SECS}" ddsperf sub >/dev/null 2>&1 || true   # subscriber only; no unitree writer

echo
echo "=== BODY-STATE I can READ (subscribe-safe) ==="
grep -oE 'topic_name="rt/(lowstate|sportmodestate|lf/lowstate|lf/sportmodestate|lf/battery_alarm|utlidar/imu|utlidar/robot_pose)",type_name="[^"]+"' "${TRACE}" | sort -u

echo
echo "=== COMMAND topics — NEVER write these (the irreversible doorway) ==="
grep -oE 'topic_name="rt/(lowcmd|api/sport/request|api/motion_switcher/request|api/sport_lease/request)",type_name="[^"]+"' "${TRACE}" | sort -u

echo
echo "=== full topic count discovered ==="
grep -oE 'topic_name="rt/[^"]+"' "${TRACE}" | sort -u | wc -l
echo "(full inventory saved at motion/dds_topics.txt; trace: ${TRACE})"
