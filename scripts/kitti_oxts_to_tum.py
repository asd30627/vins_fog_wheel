#!/usr/bin/env python3
"""KITTI Tracking oxts -> TUM GT for ORB-SLAM3 ATE.
oxts/<seq>.txt: one line per frame, cols lat lon alt roll pitch yaw ... (KITTI convention).
Convert lat/lon/alt to local metric via Mercator (KITTI devkit formula), position relative to frame0,
orientation from roll/pitch/yaw. Timestamp = frame*0.1 s (matches the stereo player's synthetic stamps).
  usage: kitti_oxts_to_tum.py --oxts <.../oxts/0000.txt> --out logs/phase6/kitti_gt_0000.tum
"""
import argparse, math, os

ER = 6378137.0  # earth radius (m)


def quat_from_rpy(r, p, y):
    cy, sy = math.cos(y*0.5), math.sin(y*0.5)
    cp, sp = math.cos(p*0.5), math.sin(p*0.5)
    cr, sr = math.cos(r*0.5), math.sin(r*0.5)
    return (sr*cp*cy - cr*sp*sy, cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy, cr*cp*cy + sr*sp*sy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--oxts', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    lines = [l.split() for l in open(a.oxts) if l.strip()]
    lat0 = float(lines[0][0])
    scale = math.cos(lat0 * math.pi / 180.0)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    x0 = y0 = z0 = None
    n = 0
    with open(a.out, 'w') as f:
        for fi, c in enumerate(lines):
            lat, lon, alt = float(c[0]), float(c[1]), float(c[2])
            roll, pitch, yaw = float(c[3]), float(c[4]), float(c[5])
            mx = scale * lon * math.pi * ER / 180.0
            my = scale * ER * math.log(math.tan((90.0 + lat) * math.pi / 360.0))
            if x0 is None:
                x0, y0, z0 = mx, my, alt
            qx, qy, qz, qw = quat_from_rpy(roll, pitch, yaw)
            ts = fi * 0.1
            f.write(f"{ts:.6f} {mx-x0:.6f} {my-y0:.6f} {alt-z0:.6f} {qx:.6f} {qy:.6f} {qz:.6f} {qw:.6f}\n")
            n += 1
    print(f"[oxts->tum] wrote {n} poses -> {a.out}")


if __name__ == '__main__':
    main()
