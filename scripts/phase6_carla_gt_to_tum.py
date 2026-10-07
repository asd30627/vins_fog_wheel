#!/usr/bin/env python3
"""CARLA GT -> TUM converter for ORB-SLAM3 ATE (repair Task B2).

Reads <recording>/gt/*.json (each has ts_ns + ego_pose{x,y,z,roll,pitch,yaw[deg]}) and writes a
TUM file: "timestamp tx ty tz qx qy qz qw", timestamp in SECONDS matching the image/player stamp
(tImLeft = ts_ns/1e9, the same basis the ORB-SLAM3 pose logger uses).

Frame convention: CARLA world is LEFT-HANDED (x fwd, y right, z up; yaw about z). We output RAW CARLA
world position (x,y,z) and a quaternion from (roll,pitch,yaw). evo_ape -a applies an SE(3) Umeyama
alignment which absorbs a global rotation+translation but NOT a reflection — so a left-vs-right-handed
mismatch can inflate ATE. To make the GT right-handed (matching a right-handed SLAM frame) we also
provide --flip-y (negate y and yaw), which is the common CARLA->ROS convention. Default: raw (document
the number), then compare with --flip-y.
"""
import argparse, glob, json, math, os


def quat_from_euler_deg(roll, pitch, yaw):
    # ZYX intrinsic (yaw about z, then pitch about y, then roll about x). Degrees -> rad.
    r, p, y = math.radians(roll), math.radians(pitch), math.radians(yaw)
    cy, sy = math.cos(y * 0.5), math.sin(y * 0.5)
    cp, sp = math.cos(p * 0.5), math.sin(p * 0.5)
    cr, sr = math.cos(r * 0.5), math.sin(r * 0.5)
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    return qx, qy, qz, qw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True, help="recording dir containing gt/*.json")
    ap.add_argument("--out", required=True, help="output TUM path")
    ap.add_argument("--flip-y", action="store_true", help="negate y and yaw (CARLA left-handed -> right-handed)")
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.rec, "gt", "*.json")))
    if not files:
        raise SystemExit(f"no gt/*.json under {a.rec}")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    n = 0
    with open(a.out, "w") as f:
        for fp in files:
            d = json.load(open(fp))
            ts = d["ts_ns"] / 1e9
            e = d["ego_pose"]
            x, y, z = e["x"], e["y"], e["z"]
            roll, pitch, yaw = e.get("roll", 0.0), e.get("pitch", 0.0), e["yaw"]
            if a.flip_y:
                y = -y
                yaw = -yaw
            qx, qy, qz, qw = quat_from_euler_deg(roll, pitch, yaw)
            f.write(f"{ts:.6f} {x:.6f} {y:.6f} {z:.6f} {qx:.6f} {qy:.6f} {qz:.6f} {qw:.6f}\n")
            n += 1
    print(f"[gt->tum] wrote {n} poses -> {a.out}  (flip_y={a.flip_y})")


if __name__ == "__main__":
    main()
