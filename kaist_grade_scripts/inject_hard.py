#!/usr/bin/env python3
"""Inject the 3 worse FOG grades onto HARD KAIST sequences' real fog.csv.
Reuses gen_kaist_grade_fog.process() (same Allan-injection model as the easy study),
bypassing that script's >=5min SEQUENCES gate. PURE DATA LAYER — no estimator."""
import sys, importlib.util
GEN = "/home/ivlab3/fwvio_ws/scripts/gen_kaist_grade_fog.py"
spec = importlib.util.spec_from_file_location("genfog", GEN)
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

HARD = ["urban18-highway","urban19-highway","urban20-highway","urban21-highway",
        "urban22-highway","urban24-highway","urban30-gangnam","urban38-pankyo"]
GRADES = list(g.PROFILES)   # industrial_fog, precision_mems, general_imu
SEED = 42

if __name__ == "__main__":
    seqs = sys.argv[1:] if len(sys.argv) > 1 else HARD
    for s in seqs:
        for gr in GRADES:
            g.process(s, gr, SEED)
