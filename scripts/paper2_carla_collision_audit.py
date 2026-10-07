#!/usr/bin/env python3
"""Paper-2 v5 — CARLA dynamic_v3 collision / near-contact audit. STANDALONE; no backend.

Change: paper2-observability-aware-object-validity-v5.

From each run's gt/*.json (ego_pose, ego_speed, per_instance world x,y): compute, per frame, the nearest
FRONT object range (in ego body frame: fwd>0, |lateral|<lane). Flags near-contact (front_range< thresholds),
sudden ego speed drops (hard braking), and physical overlap (front_range< OVERLAP_M). Emits a per-(run,frame)
near-contact flag CSV so C1/C3 can be re-run with/without contaminated frames.
Output: paper2_carla_nearcontact_frames.csv + PAPER2_CARLA_COLLISION_AUDIT.md
"""
from __future__ import annotations
import json, glob, math
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
DATAROOT = Path("/mnt/sata4t/datasets/carla_fwvio")
LANE = 2.5; NEAR2, NEAR3, OVERLAP_M = 2.0, 3.0, 4.5
BRAKE_DROP = 3.0   # m/s drop between frames = hard brake / possible impact


def main():
    runs = sorted(p for p in DATAROOT.glob("*__dynamic_v3__run*")
                  if (p / "recording_meta.json").exists() and "probe" not in p.name)
    rows = []; flags = []
    for rec in runs:
        town = rec.name.split("__")[0]; run = rec.name.split("__run")[-1]
        gtf = sorted(glob.glob(str(rec / "gt" / "*.json")))
        prev_spd = None; minfr = 1e9; n = 0; n2 = n3 = nov = nbrake = 0
        for f in gtf:
            g = json.load(open(f)); fi = g["frame"]; n += 1
            ex, ey, eyaw = g["ego_pose"]["x"], g["ego_pose"]["y"], math.radians(g["ego_pose"]["yaw"])
            spd = g.get("ego_speed", 0.0)
            cyaw, syaw = math.cos(eyaw), math.sin(eyaw)
            fr = 1e9
            for inst in g["per_instance"].values():
                if "x" not in inst:
                    continue
                dx = inst["x"] - ex; dy = inst["y"] - ey
                rng = math.hypot(dx, dy)
                if rng < 1.0:
                    continue   # ego itself
                fwd = cyaw * dx + syaw * dy; lat = -syaw * dx + cyaw * dy
                if fwd > 0 and abs(lat) < LANE:
                    fr = min(fr, fwd)
            brake = (prev_spd is not None and (prev_spd - spd) > BRAKE_DROP)
            near = fr < NEAR3
            if fr < 1e8:
                minfr = min(minfr, fr)
                if fr < NEAR2: n2 += 1
                if fr < NEAR3: n3 += 1
                if fr < OVERLAP_M: nov += 1
            if brake: nbrake += 1
            flags.append(dict(town=town, run=run, frame=fi,
                              front_range=round(fr, 2) if fr < 1e8 else "",
                              near_contact=int(near or brake or (fr < OVERLAP_M))))
            prev_spd = spd
        rows.append(dict(town=town, run=run, n=n, min_front_range=round(minfr, 2) if minfr < 1e8 else float("nan"),
                         frac_lt2=round(n2/n, 3), frac_lt3=round(n3/n, 3), frac_overlap=round(nov/n, 3),
                         n_hard_brake=nbrake))
    aud = pd.DataFrame(rows); fl = pd.DataFrame(flags)
    fl.to_csv(WS / "paper2_carla_nearcontact_frames.csv", index=False)
    nc = fl["near_contact"].mean()

    contaminated = aud[(aud["min_front_range"] < OVERLAP_M) | (aud["frac_lt3"] > 0.1)]
    L = ["# PAPER2_CARLA_COLLISION_AUDIT", "",
         f"> Near-contact / collision audit over {len(runs)} dynamic_v3 runs. Front object = ego-body fwd>0, "
         f"|lateral|<{LANE} m. near_contact flag = front_range<{NEAR3} m OR overlap(<{OVERLAP_M} m) OR hard-brake(>{BRAKE_DROP} m/s drop).",
         f"> Overall near-contact frame ratio = **{nc:.3f}**.", "",
         "## Per-run", "| town | run | n | min_front_range | frac<2m | frac<3m | frac_overlap | hard_brakes |",
         "|---|---|---|---|---|---|---|---|"]
    for _, r in aud.iterrows():
        L.append(f"| {r.town} | {r.run} | {r.n} | {r.min_front_range} | {r.frac_lt2} | {r.frac_lt3} | {r.frac_overlap} | {r.n_hard_brake} |")
    L += ["", "## Contaminated runs (min_front_range<4.5m OR >10% frames <3m)",
          f"- {len(contaminated)} runs: " + (", ".join(f"{r.town}/{r.run}" for _, r in contaminated.iterrows()) or "none"), "",
          "## Reading",
          f"- {nc:.1%} of frames are near-contact → re-run C1/C3 excluding these (see paper2_carla_nearcontact_frames.csv).",
          "- if excluding them changes the velocity-validity-vs-distance trend materially, the near range was contaminated;",
          "  if the trend persists, the phenomenon is not a collision artifact."]
    (WS / "PAPER2_CARLA_COLLISION_AUDIT.md").write_text("\n".join(L) + "\n")
    print(f"[audit] runs={len(runs)} near-contact frame ratio={nc:.3f}")
    print("[audit] min_front_range per run:", dict(zip(aud.run + "@" + aud.town, aud.min_front_range)))
    print(f"[audit] contaminated runs: {len(contaminated)}")


if __name__ == "__main__":
    main()
