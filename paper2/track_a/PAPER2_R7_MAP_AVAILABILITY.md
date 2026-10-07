# PAPER2 R7 — Map Availability Audit

> Checked via `carla.Client.get_available_maps()` against running CARLA container `carla_dyn` (0.9.16-maps).
> Date: 2026-07-01.

## Result

| town | map_name | status | role |
|---|---|---|---|
| Town01 | /Game/Carla/Maps/Town01 | **MAP_AVAILABLE** | positive urban candidate |
| Town02 | /Game/Carla/Maps/Town02 | **MAP_AVAILABLE** | positive urban candidate |
| Town04 | /Game/Carla/Maps/Town04 | **MAP_AVAILABLE** | positive urban candidate |
| Town05 | /Game/Carla/Maps/Town05 | **MAP_AVAILABLE** | positive urban candidate |
| Town10HD | /Game/Carla/Maps/Town10HD | **MAP_AVAILABLE** | positive urban candidate |
| Town06 | /Game/Carla/Maps/Town06 | MAP_AVAILABLE (boundary) | negative control |
| Town07 | /Game/Carla/Maps/Town07 | MAP_AVAILABLE (boundary) | negative control |

## Conclusion

All 5 positive urban candidates are available. Proceed with R7 preview recording for all 5 towns.

Town06/Town07 are available but are **boundary/negative controls** (VISION_INERT confirmed Phase 2). Do not re-record them as positive candidates.

All recordings use condition `dynamic_v3r7`.
