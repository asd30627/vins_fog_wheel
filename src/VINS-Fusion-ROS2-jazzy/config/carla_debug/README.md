# carla_debug — VINS configs for debugging the CARLA stereo+IMU "1 row" problem

These are **additive** debug configs. The original configs under `../carla/`
are untouched. The IMU spike/axis fixes live in the **replay** script
(`~/vins_ws/tools/carla_vins_debug/carla_dataset_replay_ros2_fix_variants.py`),
so most stereo+IMU configs here are byte-identical to `carla_stereo_imu_raw.yaml`
— what changes between runs is which replay variant feeds the topics.

`output_path` / `pose_graph_save_path` contain a `_PLACEHOLDER` token that the
batch runner rewrites per run.

| config | imu | extrinsic | purpose |
|---|---|---|---|
| `carla_stereo_only.yaml` | 0 | fixed | Stereo only. Does VINS work at all without IMU? Isolates IMU as the cause. |
| `carla_stereo_imu_raw.yaml` | 1 | fixed | Baseline stereo+IMU (raw IMU incl. spawn spike). Expected to fail (~1 row). |
| `carla_stereo_imu_skip_imu_head_10.yaml` | 1 | fixed | Pair with replay `skip_imu_head_10` — drops first 10 IMU rows. |
| `carla_stereo_imu_drop_spike_50.yaml` | 1 | fixed | Pair with replay `drop_imu_spike_50` — drops any \|a\|>50 m/s². |
| `carla_stereo_imu_yflip_drop_spike.yaml` | 1 | fixed | drop spike + negate y (CARLA left-handed → ROS right-handed test). |
| `carla_stereo_imu_zflip_drop_spike.yaml` | 1 | fixed | drop spike + negate z. |
| `carla_stereo_imu_yzflip_drop_spike.yaml` | 1 | fixed | drop spike + negate y,z. |
| `carla_stereo_imu_estimate_extrinsic.yaml` | 1 | **estimated** | `estimate_extrinsic=1` — tests whether the fixed extrinsic is wrong. |
| `carla_stereo_imu_extrinsic_identity.yaml` | 1 | **identity R** | identity cam→body rotation (translation kept) — tests extrinsic rotation. |

Extrinsics (`body_T_cam*`) and `g_norm=9.81` come from the dataset `meta.json`
(IMU at vehicle z=1.6; left/right cam at x=1.5, z=1.6, y=∓0.1; baseline 0.2 m;
gravity +Z). Run via `~/vins_ws/tools/carla_vins_debug/run_carla_vins_fix_variants.sh`.
