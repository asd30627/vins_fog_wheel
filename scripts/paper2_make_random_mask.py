#!/usr/bin/env python3
"""Random-control mask: per frame, same NUMBER and SIZE of boxes as the all_dynamic mask, but placed at
random positions NOT overlapping the real object boxes (deterministic seed). Isolates 'fewer features in
some region' from 'features on dynamic objects'. Usage: --all-dynamic <json> --out <json> --seed N"""
import json, sys, argparse, random
ap = argparse.ArgumentParser(); ap.add_argument("--all-dynamic", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--seed", type=int, default=7); ap.add_argument("--W", type=int, default=640); ap.add_argument("--H", type=int, default=480)
a = ap.parse_args(); rng = random.Random(a.seed)
src = json.load(open(a.all_dynamic)); out = {}
def overlaps(b, boxes):
    for c in boxes:
        if not (b[2] < c[0] or b[0] > c[2] or b[3] < c[1] or b[1] > c[3]): return True
    return False
for fr, boxes in src.items():
    real = [list(map(float, b)) for b in boxes]; placed = []
    for b in real:
        w, h = b[2]-b[0], b[3]-b[1]
        for _ in range(50):
            x0 = rng.uniform(0, a.W-w); y0 = rng.uniform(0, a.H-h); nb = [x0, y0, x0+w, y0+h]
            if not overlaps(nb, real) and not overlaps(nb, placed): placed.append(nb); break
    if placed: out[fr] = [[round(v,1) for v in b] for b in placed]
json.dump(out, open(a.out, "w"))
nb = sum(len(v) for v in out.values()); print(f"[random-mask] frames={len(out)} boxes={nb} -> {a.out}")
