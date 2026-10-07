#!/usr/bin/env python3
"""Build a STEREO-consistent mask for ORB-SLAM3 from a LEFT-only mask + per-detection disparity.

ORB-SLAM3 matches LEFT<->RIGHT; masking only the left image is unfair. This joins an existing
left-mask JSON ({frame:[[x1,y1,x2,y2],...]}) with outputs/paper2_perdet/<run>.csv (has disp_med,
depth_m per detection) and emits {frame: {"L":[...], "R":[...]}} where the right bbox is the left bbox
shifted by disparity:  right_x = left_x - disp,  disp = disp_med (fallback fx*baseline/depth = 160/depth,
fx=320, baseline=0.5). y unchanged (rectified stereo). A small dilation covers disparity error.

Usage:
  python3 scripts/phase6_make_stereo_mask.py \
     --left-mask <_masks>/mask_<RUN>__tcsvm.json \
     --perdet outputs/paper2_perdet/<RUN>.csv \
     --out logs/phase6/stereo_mask_<RUN>__tcsvm.json
"""
import argparse, json, csv, math, os

FX, BASELINE, W = 320.0, 0.5, 640


def load_perdet(path):
    per = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                fr = int(float(r['frame']))
            except Exception:
                continue
            def g(k):
                try: return float(r.get(k, ''))
                except Exception: return float('nan')
            per.setdefault(fr, []).append(dict(u=g('u'), v=g('v'), w=g('bbox_w'), h=g('bbox_h'),
                                               disp=g('disp_med'), depth=g('depth_m')))
    return per


def disparity_for(cx, cy, dets):
    if not dets:
        return None
    best = min(dets, key=lambda d: (d['u']-cx)**2 + (d['v']-cy)**2 if math.isfinite(d['u']) else 1e18)
    d = best['disp']
    if math.isfinite(d) and d > 0.5:
        return d
    if math.isfinite(best['depth']) and best['depth'] > 0.1:
        return FX * BASELINE / best['depth']
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--left-mask', required=True)
    ap.add_argument('--perdet', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pad', type=int, default=4, help='extra px padding on right bbox for disp error')
    a = ap.parse_args()

    left = {int(k): v for k, v in json.load(open(a.left_mask)).items()}
    per = load_perdet(a.perdet)
    out = {}
    n_l = n_r = n_fallback_missing = 0
    # global fallback disparity = median of all valid disp
    all_disp = [d['disp'] for ds in per.values() for d in ds if math.isfinite(d['disp']) and d['disp'] > 0.5]
    med_disp = sorted(all_disp)[len(all_disp)//2] if all_disp else 20.0
    for fr, boxes in left.items():
        L, R = [], []
        for (x1, y1, x2, y2) in boxes:
            L.append([round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)])
            n_l += 1
            cx, cy = (x1+x2)/2.0, (y1+y2)/2.0
            disp = disparity_for(cx, cy, per.get(fr, []))
            if disp is None:
                disp = med_disp
                n_fallback_missing += 1
            rx1 = max(0.0, x1 - disp - a.pad)
            rx2 = min(float(W), x2 - disp + a.pad)
            if rx2 > rx1:
                R.append([round(rx1, 1), round(y1, 1), round(rx2, 1), round(y2, 1)])
                n_r += 1
        out[str(fr)] = {"L": L, "R": R}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, 'w'))
    print(f"[stereo-mask] {os.path.basename(a.left_mask)}: frames={len(out)} L_boxes={n_l} R_boxes={n_r} "
          f"median_disp={med_disp:.1f}px fallback_disp_used={n_fallback_missing} -> {a.out}")


if __name__ == '__main__':
    main()
