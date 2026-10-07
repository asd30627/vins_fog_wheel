#!/usr/bin/env bash
# Run all 11 EuRoC sequences: baseline vs 15-dim aligned-GT oracle. Accumulates a TSV table.
set -o pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
BAGS=/mnt/sata4t/datasets/EuRoC_full/ros2_bags
TSV=$SP/euroc_oracle_11.tsv
printf "seq\tbase_ATE\toracle_ATE\timprove%%\talign_rmse\n" > "$TSV"
SEQS=(MH_01_easy MH_02_easy MH_03_medium MH_04_difficult MH_05_difficult \
      V1_01_easy V1_02_medium V1_03_difficult V2_01_easy V2_02_medium V2_03_difficult)
for seq in "${SEQS[@]}"; do
  gt="$SP/../../$seq"  # placeholder, overwritten below
  gt="/tmp/claude-1000/-home-ivlab3-fwvio-estimator-ws-wheel/3c414491-a552-45ec-a815-9b8df35ab1e0/scratchpad/euroc_${seq}_gt.tum"
  if [ ! -d "$BAGS/$seq" ]; then echo "SKIP $seq (no bag)"; continue; fi
  if [ ! -f "$gt" ]; then echo "SKIP $seq (no gt)"; continue; fi
  line=$(bash "$SP/euroc_pair.sh" "$BAGS/$seq" "$gt" "$seq" 2>/dev/null | tail -1)
  echo "$line"
  # parse "EUROC seq: base=X oracle_aligned=Y improve=Z% (align align_rmse=R)"
  b=$(echo "$line"|grep -oE 'base=[0-9.]+'|cut -d= -f2)
  o=$(echo "$line"|grep -oE 'oracle_aligned=[0-9.]+'|cut -d= -f2)
  z=$(echo "$line"|grep -oE 'improve=-?[0-9.]+'|cut -d= -f2)
  r=$(echo "$line"|grep -oE 'align_rmse=[0-9.]+'|cut -d= -f2)
  printf "%s\t%s\t%s\t%s\t%s\n" "$seq" "${b:-NA}" "${o:-NA}" "${z:-NA}" "${r:-NA}" >> "$TSV"
done
echo "===== EUROC_ALL11_DONE $(date +%H:%M:%S) ====="
column -t -s$'\t' "$TSV"
