#!/usr/bin/env bash
# Step 2 batch: 15-dim aligned-GT oracle on USABLE KAIST seqs.
# Usable = step-1 completion>80% AND baseline ATE bounded (<500m, i.e. VIO did not diverge).
# Diverged-baseline seqs (highway) are skipped (oracle ATE-improvement is meaningless on a 5-17km baseline).
set -o pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
TSV1=$SP/kaist_vio_step1.tsv
TSV2=$SP/kaist_oracle_step2.tsv
ATE_CAP="${ATE_CAP:-500}"
printf "seq\tbase_ATE\toracle_ATE\timprove%%\talign_rmse\n" > "$TSV2"
# pick usable seqs from step1 TSV
mapfile -t USABLE < <(awk -F'\t' -v cap="$ATE_CAP" 'NR>1 && $3+0>80 && $4!="NA" && $4+0<cap {print $1}' "$TSV1")
echo "step2 usable (completion>80% & ATE<${ATE_CAP}m): ${USABLE[*]}"
for seq in "${USABLE[@]}"; do
  line=$(bash "$SP/kaist_oracle_pair.sh" "$seq" 2>/dev/null | grep '^KORACLE')
  echo "$line"
  b=$(echo "$line"|grep -oE 'base=[0-9.NA]+'|cut -d= -f2)
  o=$(echo "$line"|grep -oE 'oracle=[0-9.NA]+'|cut -d= -f2)
  z=$(echo "$line"|grep -oE 'improve=-?[0-9.NA]+'|cut -d= -f2)
  r=$(echo "$line"|grep -oE 'align_rmse=[0-9.]+'|cut -d= -f2)
  printf "%s\t%s\t%s\t%s\t%s\n" "$seq" "${b:-NA}" "${o:-NA}" "${z:-NA}" "${r:-NA}" >> "$TSV2"
done
echo "===== KAIST_ORACLE_STEP2_DONE $(date +%H:%M:%S) ====="
column -t -s$'\t' "$TSV2"
