#!/usr/bin/env bash
# Convert the 8 remaining EuRoC ASL sequences to ros2 bags (MH_01 + MH_03 + V1_02 already done).
set -o pipefail
source /opt/ros/jazzy/setup.bash 2>/dev/null
K=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
BAGS=/mnt/sata4t/datasets/EuRoC_full/ros2_bags
R=/mnt/sata4t/datasets/EuRoC_full
declare -A MAV=(
 [MH_02_easy]="$R/Machine_Hall_Datasets/machine_hall/MH_02_easy/mav0"
 [MH_04_difficult]="$R/Machine_Hall_Datasets/machine_hall/MH_04_difficult/mav0"
 [MH_05_difficult]="$R/Machine_Hall_Datasets/machine_hall/MH_05_difficult/mav0"
 [V1_01_easy]="$R/Vicon_Room_1_Datasets/vicon_room1/V1_01_easy/mav0"
 [V1_03_difficult]="$R/Vicon_Room_1_Datasets/vicon_room1/V1_03_difficult/mav0"
 [V2_01_easy]="$R/Vicon_Room_2_Datasets/vicon_room2/V2_01_easy/mav0"
 [V2_02_medium]="$R/Vicon_Room_2_Datasets/vicon_room2/V2_02_medium/mav0"
 [V2_03_difficult]="$R/Vicon_Room_2_Datasets/vicon_room2/V2_03_difficult/mav0"
)
for seq in MH_02_easy MH_04_difficult MH_05_difficult V1_01_easy V1_03_difficult V2_01_easy V2_02_medium V2_03_difficult; do
  echo "=== $seq ==="
  if [ -d "$BAGS/$seq" ]; then echo "  exists, skip"; continue; fi
  python3 $K/asl_to_bag.py "${MAV[$seq]}" "$BAGS/$seq" 2>&1 | grep -vE "rosbag2_storage|INFO" | tail -3
done
echo "===== CONVERT_ALL_DONE $(date +%H:%M:%S) ====="
