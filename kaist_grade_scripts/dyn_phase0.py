#!/usr/bin/env python3
"""Phase 0 feasibility: do dynamic objects (car/person/...) co-occur with KAIST VIO
visual degradation?  KEYFRAME-LEVEL (no per-feature coords available, no VINS re-run).

For each keyframe in feat_snapshots/<seq>__lastgrade.csv we:
  - locate the nearest stereo_left image (filename = capture ts in ns)
  - run pretrained YOLOv8 (COCO) -> movable-class boxes {person,bicycle,car,motorcycle,bus,truck}
  - compute dyn_area_frac (union-ish summed bbox area / frame area), dyn_count, dyn_max_frac
Then correlate dyn_* against runtime degradation proxies already in the CSV:
  vg_flow_res_mean (reproj-residual proxy), outlier_ratio_last, inlier_count_last,
  tracked_feature_count_mgr.  (These need NO GT alignment.)

Outputs a per-keyframe merged TSV + a summary json + optional overlays.
"""
import argparse, csv, glob, os, sys, json
import numpy as np
import cv2

MOVABLE = {0:'person',1:'bicycle',2:'car',3:'motorcycle',5:'bus',7:'truck'}
EXT = "/mnt/sata4t/datasets/kaist_complex_urban/extracted"

def load_csv(path):
    rows=[]
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def fget(r,k):
    try: return float(r.get(k,'nan'))
    except: return float('nan')

def build_img_index(seq):
    d=f"{EXT}/{seq}/img/{seq}/image/stereo_left"
    files=glob.glob(d+"/*.png")
    ts=np.array([int(os.path.basename(p)[:-4])/1e9 for p in files])
    o=np.argsort(ts)
    return ts[o], [files[i] for i in o]

def nearest(ts_arr, files, t, tol=0.06):
    i=np.searchsorted(ts_arr,t)
    best=None;bd=tol
    for j in (i-1,i):
        if 0<=j<len(ts_arr):
            dd=abs(ts_arr[j]-t)
            if dd<bd: bd=dd;best=files[j]
    return best

def debayer(p):
    im=cv2.imread(p,cv2.IMREAD_UNCHANGED)
    if im is None: return None
    if im.ndim==2:
        im=cv2.cvtColor(im,cv2.COLOR_BayerRG2BGR)
    return im

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seq',required=True)
    ap.add_argument('--csv',required=True)
    ap.add_argument('--stride',type=int,default=1,help='use every Nth keyframe')
    ap.add_argument('--limit',type=int,default=0)
    ap.add_argument('--conf',type=float,default=0.25)
    ap.add_argument('--imgsz',type=int,default=1280)
    ap.add_argument('--out',required=True)
    ap.add_argument('--overlay_dir',default='')
    ap.add_argument('--overlay_every',type=int,default=0)
    args=ap.parse_args()

    from ultralytics import YOLO
    model=YOLO('yolov8m.pt')

    rows=load_csv(args.csv)
    rows=[r for r in rows if int(float(r.get('current_is_keyframe',0)))>=0]
    rows=rows[::args.stride]
    if args.limit: rows=rows[:args.limit]
    ts_arr,files=build_img_index(args.seq)
    print(f"[{args.seq}] {len(rows)} keyframe rows, {len(files)} images",file=sys.stderr)

    if args.overlay_dir: os.makedirs(args.overlay_dir,exist_ok=True)
    out=[]
    BATCH=32
    batch_imgs=[];batch_meta=[]
    def flush():
        if not batch_imgs: return
        res=model.predict(batch_imgs,imgsz=args.imgsz,conf=args.conf,
                          classes=list(MOVABLE),verbose=False,device=0)
        for r,(meta,img) in zip(res,batch_meta):
            H,W=img.shape[:2];A=H*W
            area=0.0;mx=0.0;cnt=0
            for b in r.boxes:
                x1,y1,x2,y2=b.xyxy[0].tolist()
                a=max(0,(x2-x1))*max(0,(y2-y1))
                area+=a;mx=max(mx,a);cnt+=1
            meta['dyn_area_frac']=area/A
            meta['dyn_max_frac']=mx/A
            meta['dyn_count']=cnt
            out.append(meta)
            if args.overlay_dir and args.overlay_every and (meta['idx']%args.overlay_every==0):
                im2=img.copy()
                for b in r.boxes:
                    x1,y1,x2,y2=map(int,b.xyxy[0].tolist())
                    cv2.rectangle(im2,(x1,y1),(x2,y2),(0,0,255),2)
                    cv2.putText(im2,f"{MOVABLE.get(int(b.cls),'?')}{float(b.conf):.2f}",
                                (x1,max(0,y1-4)),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
                cv2.putText(im2,f"frac={meta['dyn_area_frac']:.3f} n={cnt} res={meta['vg_res']:.3f} out={meta['outlier']:.3f}",
                            (8,24),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,0),2)
                cv2.imwrite(f"{args.overlay_dir}/{args.seq}_{meta['idx']:06d}.jpg",im2)
        batch_imgs.clear();batch_meta.clear()

    miss=0
    for idx,r in enumerate(rows):
        t=fget(r,'timestamp')
        p=nearest(ts_arr,files,t)
        if p is None: miss+=1; continue
        img=debayer(p)
        if img is None: miss+=1; continue
        meta=dict(idx=idx,ts=t,
                  vg_res=fget(r,'vg_flow_res_mean'),
                  outlier=fget(r,'outlier_ratio_last'),
                  inlier=fget(r,'inlier_count_last'),
                  feat_mgr=fget(r,'tracked_feature_count_mgr'),
                  cov8=fget(r,'coverage_8x8'),
                  ba=fget(r,'ba_norm'),
                  px=fget(r,'est_p_x'),py=fget(r,'est_p_y'),pz=fget(r,'est_p_z'))
        batch_imgs.append(img);batch_meta.append((meta,img))
        if len(batch_imgs)>=BATCH: flush()
    flush()
    print(f"matched {len(out)} miss {miss}",file=sys.stderr)

    # write TSV
    cols=['idx','ts','dyn_area_frac','dyn_max_frac','dyn_count','vg_res','outlier',
          'inlier','feat_mgr','cov8','ba','px','py','pz']
    with open(args.out,'w') as f:
        f.write('\t'.join(cols)+'\n')
        for m in out:
            f.write('\t'.join(f"{m.get(c,'nan')}" for c in cols)+'\n')

    # correlations
    def arr(k): return np.array([m[k] for m in out],float)
    daf=arr('dyn_area_frac')
    def spear(a,b):
        m=np.isfinite(a)&np.isfinite(b)
        if m.sum()<10: return float('nan')
        ra=np.argsort(np.argsort(a[m]));rb=np.argsort(np.argsort(b[m]))
        ra=ra-ra.mean();rb=rb-rb.mean()
        d=np.sqrt((ra*ra).sum()*(rb*rb).sum())
        return float((ra*rb).sum()/d) if d>0 else float('nan')
    summ=dict(seq=args.seq,n=len(out),miss=miss,
              dyn_area_frac=dict(mean=float(np.nanmean(daf)),med=float(np.nanmedian(daf)),
                                 p90=float(np.nanpercentile(daf,90)),max=float(np.nanmax(daf)),
                                 frac_kf_with_obj=float(np.mean(arr('dyn_count')>0))),
              spearman_dynfrac_vs=dict(
                  vg_res=spear(daf,arr('vg_res')),
                  outlier=spear(daf,arr('outlier')),
                  inlier=spear(daf,arr('inlier')),
                  feat_mgr=spear(daf,arr('feat_mgr')),
                  cov8=spear(daf,arr('cov8'))))
    # quartile bins of dyn_area_frac -> mean degradation proxies (more robust than 1 rho)
    fin=np.isfinite(daf)
    qs=np.quantile(daf[fin],[0,.25,.5,.75,1.0])
    bins=[]
    for lo,hi,lab in [(qs[0],qs[1],'Q1_lowdyn'),(qs[1],qs[2],'Q2'),(qs[2],qs[3],'Q3'),(qs[3],qs[4]+1e-9,'Q4_highdyn')]:
        m=fin&(daf>=lo)&(daf<hi if lab!='Q4_highdyn' else daf<=hi)
        if m.sum()==0: continue
        bins.append(dict(bin=lab,n=int(m.sum()),
            dyn_frac=float(np.nanmean(daf[m])),
            vg_res=float(np.nanmean(arr('vg_res')[m])),
            outlier=float(np.nanmean(arr('outlier')[m])),
            inlier=float(np.nanmean(arr('inlier')[m])),
            feat_mgr=float(np.nanmean(arr('feat_mgr')[m]))))
    summ['quartile_bins']=bins
    print(json.dumps(summ,indent=2))
    with open(args.out+'.summary.json','w') as f: json.dump(summ,f,indent=2)

if __name__=='__main__':
    main()
