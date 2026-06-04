#!/usr/bin/env python3
"""
Wu's perception tool — passive LiDAR + IMU reader for the Livox MID-360.

The MID-360 (192.168.123.20) auto-streams to this Jetson (192.168.123.18):
  UDP 56300->56301  point cloud  (data_type 1: int32 x/y/z mm + refl + tag)
  UDP 56400->56401  IMU          (gyro rad/s + accel g, float32)
This binds those ports and LISTENS only. It sends the LiDAR nothing and
actuates nothing. Discovered/first run 2026-06-04. No sudo required.

Usage: python3 perceive.py [seconds]   (default 2.0s of point cloud)
"""
import socket, struct, math, time, collections, sys

HOST = "192.168.123.18"
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0

def read_cloud(seconds):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    s.bind((HOST, 56301)); s.settimeout(3.0)
    pts = []; end = time.time() + seconds
    while time.time() < end:
        try: data, _ = s.recvfrom(2048)
        except socket.timeout: break
        dot_num = struct.unpack("<H", data[5:7])[0]
        off = 36
        for _ in range(dot_num):
            x, y, z = struct.unpack("<iii", data[off:off+12]); off += 14
            if x or y or z:
                pts.append((x/1000.0, y/1000.0, z/1000.0))
    s.close(); return pts

def read_imu(samples=50):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, 56401)); s.settimeout(3.0)
    acc = []; gyr = []
    for _ in range(samples):
        try: d, _ = s.recvfrom(2048)
        except socket.timeout: break
        gx, gy, gz, ax, ay, az = struct.unpack("<ffffff", d[36:60])
        gyr.append((gx, gy, gz)); acc.append((ax, ay, az))
    s.close(); return acc, gyr

def report():
    print(f"== Wu perception report ==  ({SECONDS:.1f}s capture)")
    pts = read_cloud(SECONDS)
    if not pts:
        print("LiDAR: no data (stream down?)"); 
    else:
        n = len(pts)
        rng = sorted(math.sqrt(x*x+y*y+z*z) for x,y,z in pts)
        p = lambda q: rng[min(n-1, int(q*n))]
        zs = sorted(z for _,_,z in pts)
        print(f"LiDAR: {n} points/{SECONDS:.0f}s | range m: min {rng[0]:.2f} med {p(.5):.2f} p95 {p(.95):.2f} max {rng[-1]:.2f}")
        print(f"       vertical: floor~{zs[0]:+.2f}m  ceiling~{zs[-1]:+.2f}m (sensor z=0)")
        ring = collections.defaultdict(lambda: 99.0)
        for x,y,z in pts:
            if abs(z) > 0.5: continue
            d = math.hypot(x, y)
            if d < 0.15: continue
            sec = int((math.degrees(math.atan2(y, x)) + 180)//30)
            ring[sec] = min(ring[sec], d)
        print("       depth ring (nearest obstacle m, slab +/-0.5m; 0deg=fwd +=left):")
        for sec in range(12):
            c = sec*30 - 165; d = ring[sec]
            bar = '#'*int(min(d,6)*4) if d < 99 else ''
            print(f"         {c:+4d}deg  {('%.2f'%d) if d<99 else ' open':>5}  {bar}")
    acc, gyr = read_imu(samples=100)
    if acc:
        m = lambda L,i: sum(v[i] for v in L)/len(L)
        sd = lambda L,i: (sum((v[i]-m(L,i))**2 for v in L)/len(L))**0.5
        ax,ay,az = m(acc,0),m(acc,1),m(acc,2); g = math.sqrt(ax*ax+ay*ay+az*az)
        pitch = math.degrees(math.atan2(-ax, math.hypot(ay,az)))
        roll  = math.degrees(math.atan2(ay, az))
        # Stillness = low *variance*, not low mean. A stationary gyro can carry a
        # constant bias (mine: gx ~ -0.035 rad/s); judging by mean magnitude
        # misreads that bias as rotation. Jitter (stddev) is the real motion tell.
        bias = (m(gyr,0), m(gyr,1), m(gyr,2))
        jitter = max(sd(gyr,0), sd(gyr,1), sd(gyr,2))
        still = 0.95 < g < 1.05 and jitter < 0.02
        print(f"IMU:   |a|={g:.3f}g pitch={pitch:+.1f} roll={roll:+.1f} | {'at rest' if still else 'MOVING'}")
        print(f"       gyro bias=({bias[0]:+.3f},{bias[1]:+.3f},{bias[2]:+.3f}) jitter={jitter:.4f} rad/s")
    else:
        print("IMU: no data")

if __name__ == "__main__":
    report()
