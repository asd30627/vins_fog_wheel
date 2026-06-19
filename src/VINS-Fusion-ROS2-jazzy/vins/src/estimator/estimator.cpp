#include <string>
/*******************************************************
 * Copyright (C) 2019, Aerial Robotics Group, Hong Kong University of Science and Technology
 * 
 * This file is part of VINS.
 * 
 * Licensed under the GNU General Public License v3.0;
 * you may not use this file except in compliance with the License.
 *******************************************************/
// Modified in this fork by <lUCAS> on 2026-04-23.
// Summary of changes: ROS 2 Jazzy compatibility, logging, and research-related extensions.
// This file remains part of a GPL-3.0-licensed derivative work.
// See the repository root LICENSE and THIRD_PARTY_NOTICES.md.
#include "estimator.h"
#include "../utility/visualization.h"
#include <onnxruntime_cxx_api.h>   // v11 learned ReliabilityNet (REL_USE_LEARNED_MODEL)

#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>
#include <cstdlib>
#include <sstream>
#include <iomanip>
#include <limits>
#include <set>
#include <map>

namespace
{

double meanOf(const std::vector<double> &v)
{
    if (v.empty())
        return 0.0;

    return std::accumulate(v.begin(), v.end(), 0.0) / static_cast<double>(v.size());
}

double stdOf(const std::vector<double> &v)
{
    if (v.size() <= 1)
        return 0.0;

    const double m = meanOf(v);
    double acc = 0.0;

    for (double x : v)
    {
        const double d = x - m;
        acc += d * d;
    }

    return std::sqrt(acc / static_cast<double>(v.size()));
}

double maxOf(const std::vector<double> &v)
{
    if (v.empty())
        return 0.0;

    return *std::max_element(v.begin(), v.end());
}

double percentileOf(std::vector<double> v, double p)
{
    if (v.empty())
        return 0.0;

    if (p < 0.0)
        p = 0.0;
    if (p > 1.0)
        p = 1.0;

    std::sort(v.begin(), v.end());

    const double idx = p * static_cast<double>(v.size() - 1);
    const size_t i0 = static_cast<size_t>(std::floor(idx));
    const size_t i1 = static_cast<size_t>(std::ceil(idx));

    if (i0 == i1)
        return v[i0];

    const double w = idx - static_cast<double>(i0);
    return v[i0] * (1.0 - w) + v[i1] * w;
}

double medianOf(std::vector<double> v)
{
    return percentileOf(std::move(v), 0.5);
}

double rotationDistanceDeg(const Eigen::Matrix3d &Ra, const Eigen::Matrix3d &Rb)
{
    Eigen::Matrix3d dR = Ra.transpose() * Rb;
    double c = (dR.trace() - 1.0) * 0.5;

    if (c > 1.0)
        c = 1.0;
    if (c < -1.0)
        c = -1.0;

    return std::acos(c) * 180.0 / M_PI;
}

double quatDistanceDeg(const Eigen::Quaterniond &qa, const Eigen::Quaterniond &qb)
{
    Eigen::Quaterniond dq = qa.conjugate() * qb;
    dq.normalize();

    double w = std::abs(dq.w());

    if (w > 1.0)
        w = 1.0;
    if (w < -1.0)
        w = -1.0;

    return 2.0 * std::acos(w) * 180.0 / M_PI;
}

struct GridStats
{
    double coverage = 0.0;
    int occupied_cells = 0;
    double entropy = 0.0;
};

GridStats computeGridStats(
    const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame,
    int image_width,
    int image_height,
    int grid_size)
{
    GridStats stats;

    if (featureFrame.empty() || image_width <= 0 || image_height <= 0 || grid_size <= 0)
        return stats;

    std::vector<int> counts(grid_size * grid_size, 0);
    int total_obs = 0;

    for (const auto &kv : featureFrame)
    {
        for (const auto &obs_pair : kv.second)
        {
            const auto &obs = obs_pair.second;

            const double u = obs(3);
            const double v = obs(4);

            int c = static_cast<int>((u / std::max(1, image_width)) * grid_size);
            int r = static_cast<int>((v / std::max(1, image_height)) * grid_size);

            c = std::max(0, std::min(grid_size - 1, c));
            r = std::max(0, std::min(grid_size - 1, r));

            counts[r * grid_size + c]++;
            total_obs++;
        }
    }

    for (int n : counts)
    {
        if (n > 0)
            stats.occupied_cells++;
    }

    const int total_cells = grid_size * grid_size;
    stats.coverage = static_cast<double>(stats.occupied_cells) / static_cast<double>(total_cells);

    if (total_obs > 0 && total_cells > 1)
    {
        double entropy = 0.0;

        for (int n : counts)
        {
            if (n <= 0)
                continue;

            const double p = static_cast<double>(n) / static_cast<double>(total_obs);
            entropy -= p * std::log(p);
        }

        entropy /= std::log(static_cast<double>(total_cells));
        stats.entropy = entropy;
    }

    return stats;
}

} // namespace

Estimator::Estimator(): f_manager{Rs}
{
    ROS_INFO("init begins");
    initThreadFlag = false;

    // visual admission default config
    enable_visual_admission = false;
    visual_admission_mode = VISUAL_ALWAYS;
    visual_gate_tau = 0.5;

    clearState();
}

Estimator::~Estimator()
{
    if (MULTIPLE_THREAD)
    {
        processThread.join();
        printf("join thread \n");
    }
}

void Estimator::clearState()
{
    mProcess.lock();
    while(!accBuf.empty())
        accBuf.pop();
    while(!gyrBuf.empty())
        gyrBuf.pop();
    while(!featureBuf.empty())
        featureBuf.pop();

    prevTime = -1;
    curTime = 0;
    openExEstimation = 0;
    initP = Eigen::Vector3d(0, 0, 0);
    initR = Eigen::Matrix3d::Identity();
    inputImageCnt = 0;
    initFirstPoseFlag = false;

    for (int i = 0; i < WINDOW_SIZE + 1; i++)
    {
        Rs[i].setIdentity();
        Ps[i].setZero();
        Vs[i].setZero();
        Bas[i].setZero();
        Bgs[i].setZero();
        dt_buf[i].clear();
        linear_acceleration_buf[i].clear();
        angular_velocity_buf[i].clear();

        if (pre_integrations[i] != nullptr)
        {
            delete pre_integrations[i];
            pre_integrations[i] = nullptr;
        }
        pre_integrations[i] = nullptr;
    }

    for (int i = 0; i < NUM_OF_CAM; i++)
    {
        tic[i] = Vector3d::Zero();
        ric[i] = Matrix3d::Identity();
    }

    first_imu = false,
    sum_of_back = 0;
    sum_of_front = 0;
    frame_count = 0;
    solver_flag = INITIAL;
    initial_timestamp = 0;
    all_image_frame.clear();

    if (tmp_pre_integration != nullptr)
    {
        delete tmp_pre_integration;
        tmp_pre_integration = nullptr;
    }
    if (last_marginalization_info != nullptr)
    {
        delete last_marginalization_info;
        last_marginalization_info = nullptr;
    }

    tmp_pre_integration = nullptr;
    last_marginalization_info = nullptr;
    last_marginalization_parameter_blocks.clear();

    f_manager.clearState();

    failure_occur = 0;

    // reset visual admission runtime state
    resetVisualAdmissionState();
    pending_feature_tracker_time_ms = 0.0;
    pending_img_dt_sec = 0.0;

    pending_mean_track_vel_px = 0.0;
    pending_median_track_vel_px = 0.0;
    pending_min_track_vel_px = 0.0;
    pending_max_track_vel_px = 0.0;
    pending_std_track_vel_px = 0.0;
    pending_p90_track_vel_px = 0.0;

    pending_coverage_4x4 = 0.0;
    pending_coverage_8x8 = 0.0;
    pending_occupied_cells_4x4 = 0;
    pending_occupied_cells_8x8 = 0;
    pending_entropy_4x4 = 0.0;
    pending_entropy_8x8 = 0.0;

    pending_imu_sample_count = 0;
    pending_acc_norm_mean = 0.0;
    pending_acc_norm_std = 0.0;
    pending_acc_norm_max = 0.0;
    pending_gyr_norm_mean = 0.0;
    pending_gyr_norm_std = 0.0;
    pending_gyr_norm_max = 0.0;

    // ===== v5 SO(3) gyro integration =====
    pending_gyro_raw_delta_q = Eigen::Quaterniond::Identity();
    pending_gyro_bgcorr_delta_q = Eigen::Quaterniond::Identity();

    pending_gyro_raw_delta_angle_deg = 0.0;
    pending_gyro_raw_rotvec_x_deg = 0.0;
    pending_gyro_raw_rotvec_y_deg = 0.0;
    pending_gyro_raw_rotvec_z_deg = 0.0;

    pending_gyro_bgcorr_delta_angle_deg = 0.0;
    pending_gyro_bgcorr_rotvec_x_deg = 0.0;
    pending_gyro_bgcorr_rotvec_y_deg = 0.0;
    pending_gyro_bgcorr_rotvec_z_deg = 0.0;

    pending_gyro_abs_angle_sum_deg = 0.0;

    pending_gyr_x_mean = 0.0;
    pending_gyr_y_mean = 0.0;
    pending_gyr_z_mean = 0.0;
    pending_gyr_x_std = 0.0;
    pending_gyr_y_std = 0.0;
    pending_gyr_z_std = 0.0;
    pending_gyr_x_max_abs = 0.0;
    pending_gyr_y_max_abs = 0.0;
    pending_gyr_z_max_abs = 0.0;

    pending_gyr_bgcorr_x_mean = 0.0;
    pending_gyr_bgcorr_y_mean = 0.0;
    pending_gyr_bgcorr_z_mean = 0.0;
    pending_gyr_bgcorr_norm_mean = 0.0;

    // ===== v5 IMU timing quality =====
    pending_imu_dt_mean = 0.0;
    pending_imu_dt_std = 0.0;
    pending_imu_dt_min = 0.0;
    pending_imu_dt_max = 0.0;
    pending_imu_dt_gap_max = 0.0;
    pending_imu_total_dt = 0.0;
    pending_imu_image_dt_diff = 0.0;

    // ===== v5 gyro vs VINS consistency =====
    pending_vins_delta_angle_deg = 0.0;
    pending_vins_rotvec_x_deg = 0.0;
    pending_vins_rotvec_y_deg = 0.0;
    pending_vins_rotvec_z_deg = 0.0;

    pending_gyro_vins_so3_diff_deg = 0.0;
    pending_gyro_vins_rotvec_diff_x_deg = 0.0;
    pending_gyro_vins_rotvec_diff_y_deg = 0.0;
    pending_gyro_vins_rotvec_diff_z_deg = 0.0;
    pending_gyro_vins_rotvec_diff_norm_deg = 0.0;
    pending_gyro_vins_angle_ratio = 0.0;

    // ===== v5 visual flow vs gyro rotation consistency =====
    pending_vg_flow_valid_count = 0;

    pending_vg_flow_obs_mean = 0.0;
    pending_vg_flow_obs_std = 0.0;
    pending_vg_flow_obs_p90 = 0.0;

    pending_vg_flow_pred_mean = 0.0;
    pending_vg_flow_pred_std = 0.0;
    pending_vg_flow_pred_p90 = 0.0;

    pending_vg_flow_res_mean = 0.0;
    pending_vg_flow_res_std = 0.0;
    pending_vg_flow_res_p90 = 0.0;

    pending_vg_flow_res_flip_mean = 0.0;
    pending_vg_flow_res_min_mean = 0.0;

    pending_vg_flow_cos_mean = 0.0;
    pending_vg_flow_cos_median = 0.0;

    pending_vg_flow_mag_ratio_median = 0.0;
    pending_vg_flow_mag_ratio_p90 = 0.0;
    
    pending_track_len_min = 0.0;
    pending_track_len_max = 0.0;
    pending_track_len_std = 0.0;
    pending_track_len_p90 = 0.0;

    pending_good_depth_count = 0;
    pending_bad_depth_count = 0;
    pending_depth_mean = 0.0;
    pending_depth_min = 0.0;
    pending_depth_max = 0.0;
    pending_depth_std = 0.0;

    reliability_prev_image_time = -1.0;
    reliability_has_prev_logged_pose = false;
    reliability_prev_logged_P.setZero();
    reliability_prev_logged_Q = Eigen::Quaterniond::Identity();

    mProcess.unlock();
}

void Estimator::setVisualAdmissionConfig(bool enable, VisualAdmissionMode mode, double tau)
{
    enable_visual_admission = enable;
    visual_admission_mode = mode;
    visual_gate_tau = tau;
    if (visual_gate_tau < 0.0)
        visual_gate_tau = 0.0;
    if (visual_gate_tau > 1.0)
        visual_gate_tau = 1.0;

    visual_alpha = selectVisualAlpha();
}

void Estimator::resetVisualAdmissionState()
{
    visual_w_pred = 1.0;
    visual_gate_pass = true;

    visual_alpha = 1.0;
    visual_alpha_target = 1.0;
    visual_sigma_px = 1.5;
    visual_alpha_initialized = false;

    visual_soft_target_proxy = -1.0;
    visual_has_prediction = false;

    visual_internal_alpha_schedule_enable = false;
    visual_internal_alpha_value = 1.0;
    visual_internal_alpha_start_ts = -1.0;
    visual_internal_alpha_end_ts = -1.0;

    tracked_feature_count_raw = 0;
    tracked_feature_count_mgr = 0;
    current_is_keyframe = false;

    outlier_count_last = 0;
    inlier_count_last = 0;
    outlier_ratio_last = 0.0;

    failure_detected_last = false;
    solver_time_ms_last = 0.0;
}

void Estimator::setVisualAdmissionPrediction(double w_pred, double soft_target_proxy)
{
    if (w_pred < 0.0)
        w_pred = 0.0;
    if (w_pred > 1.0)
        w_pred = 1.0;

    visual_w_pred = w_pred;
    visual_soft_target_proxy = soft_target_proxy;
    visual_has_prediction = true;
    visual_gate_pass = (visual_w_pred >= visual_gate_tau);

    // 不要在 callback 階段直接修改 visual_alpha。
    // visual_alpha 現在只代表 backend 最終 information weight，
    // 統一由 applyVisualResidualWeight() 更新。
}

void Estimator::clearVisualAdmissionPrediction()
{
    visual_w_pred = 1.0;
    visual_gate_pass = true;

    visual_alpha = 1.0;
    visual_alpha_target = 1.0;
    visual_sigma_px = 1.5;
    visual_alpha_initialized = false;

    visual_soft_target_proxy = -1.0;
    visual_has_prediction = false;
}

void Estimator::setInternalAlphaSchedule(bool enable, double alpha_value, double start_ts, double end_ts)
{
    visual_internal_alpha_schedule_enable = enable;
    visual_internal_alpha_value = alpha_value;
    visual_internal_alpha_start_ts = start_ts;
    visual_internal_alpha_end_ts = end_ts;
    if (enable)
    {
        ROS_WARN("[internal-alpha] ENABLED alpha=%.3f window=[%.6f, %.6f]",
                 alpha_value, start_ts, end_ts);
    }
}

double Estimator::selectVisualAlpha() const
{
    if (!enable_visual_admission)
        return 1.0;

    if (!visual_has_prediction)
        return 1.0;

    double w = visual_w_pred;
    if (w < 0.0)
        w = 0.0;
    if (w > 1.0)
        w = 1.0;

    switch (visual_admission_mode)
    {
        case VISUAL_ALWAYS:
            return 1.0;

        case HARD_GATE:
            return visual_gate_pass ? 1.0 : 0.0;

        case SOFT_WEIGHT:
            return w;

        case GATE_AND_WEIGHT:
            return visual_gate_pass ? w : 0.0;

        default:
            return 1.0;
    }
}

void Estimator::applyVisualResidualWeight()
{
    // =========================================================
    // INTERNAL ALPHA SCHEDULE MODE
    //
    // Uses the image timestamp (Headers[frame_count]) to decide
    // alpha, completely independent of /clock or external publisher.
    // =========================================================
    if (visual_internal_alpha_schedule_enable)
    {
        const double image_ts = Headers[frame_count];
        const bool in_window = (image_ts >= visual_internal_alpha_start_ts &&
                                image_ts <= visual_internal_alpha_end_ts);
        const double target_alpha = in_window ? visual_internal_alpha_value : 1.0;

        // only log on state transitions
        static bool prev_in_window = false;
        if (in_window != prev_in_window)
        {
            ROS_WARN("[internal-alpha] ts=%.6f in_window=%d alpha=%.3f",
                     image_ts, in_window ? 1 : 0, target_alpha);
            prev_in_window = in_window;
        }

        visual_alpha_target = target_alpha;
        visual_alpha = target_alpha;
        visual_w_pred = target_alpha;
        visual_has_prediction = true;
        visual_alpha_initialized = true;

        const double sigma_base_px = 1.50;
        visual_sigma_px = sigma_base_px / std::sqrt(std::max(visual_alpha, 1e-9));

        const double sqrt_alpha = std::sqrt(visual_alpha);
        const Eigen::Matrix2d weighted_sqrt_info =
            sqrt_alpha * FOCAL_LENGTH / 1.5 * Eigen::Matrix2d::Identity();

        ProjectionTwoFrameOneCamFactor::sqrt_info = weighted_sqrt_info;
        ProjectionTwoFrameTwoCamFactor::sqrt_info = weighted_sqrt_info;
        ProjectionOneFrameTwoCamFactor::sqrt_info = weighted_sqrt_info;

        return;
    }

    // =========================================================
    // PREFIX COUNTERFACTUAL DIRECT-ALPHA MODE
    //
    // Enable only when:
    //   export VINS_PREFIX_DIRECT_ALPHA=1
    //
    // In this mode, /vins_admission/prediction data[2]
    // is treated as the direct backend visual information weight alpha.
    //
    // This is for counterfactual prefix replay only.
    // Normal soft-weight / reliability behavior is preserved when
    // the env var is not enabled.
    // =========================================================
    const char* prefix_direct_alpha_env = std::getenv("VINS_PREFIX_DIRECT_ALPHA");
    const bool prefix_direct_alpha =
        (prefix_direct_alpha_env != nullptr &&
         std::string(prefix_direct_alpha_env) == "1");

    if (prefix_direct_alpha)
    {
        double target_alpha = 1.0;

        if (enable_visual_admission &&
            visual_admission_mode == SOFT_WEIGHT &&
            visual_has_prediction)
        {
            target_alpha = visual_w_pred;
        }
        else
        {
            target_alpha = 1.0;
            visual_alpha_initialized = false;
        }

        // prefix action space: 1.0 / 0.7 / 0.4
        if (target_alpha < 0.40)
            target_alpha = 0.40;
        if (target_alpha > 1.00)
            target_alpha = 1.00;

        visual_alpha_target = target_alpha;
        visual_alpha = target_alpha;
        visual_alpha_initialized = true;

        const double sigma_base_px = 1.50;
        visual_sigma_px = sigma_base_px / std::sqrt(std::max(visual_alpha, 1e-9));

        const double sqrt_alpha = std::sqrt(visual_alpha);

        const Eigen::Matrix2d weighted_sqrt_info =
            sqrt_alpha * FOCAL_LENGTH / 1.5 * Eigen::Matrix2d::Identity();

        ProjectionTwoFrameOneCamFactor::sqrt_info = weighted_sqrt_info;
        ProjectionTwoFrameTwoCamFactor::sqrt_info = weighted_sqrt_info;
        ProjectionOneFrameTwoCamFactor::sqrt_info = weighted_sqrt_info;

        ROS_INFO("[admission-weight] PREFIX_DIRECT_ALPHA raw_w=%.3f alpha_target=%.3f alpha=%.3f has_pred=%d mode=%d",
                 visual_w_pred,
                 visual_alpha_target,
                 visual_alpha,
                 visual_has_prediction ? 1 : 0,
                 static_cast<int>(visual_admission_mode));

        return;
    }


    double raw_w = visual_w_pred;

    if (raw_w < 0.0)
        raw_w = 0.0;
    if (raw_w > 1.0)
        raw_w = 1.0;

    // =========================================================
    // v43 conservative / health-aware visual weighting
    //
    // 目前先只用 w_pred + VINS health，不使用 p_fail。
    //
    // 原因：
    //   1. 先前 offline analysis 顯示 p_fail 校準仍不夠好，
    //      不適合拿來做 hard gate 或主要控制條件。
    //   2. 目前 closed-loop 有改善的 GRU support 結果，
    //      實際上主要是靠 w_pred soft weighting。
    //   3. 因此 v43 先修正「每幀都微幅降權」的問題，
    //      不額外引入 p_fail 造成新變因。
    //
    // policy:
    //   - no prediction              -> alpha = 1.0
    //   - mgr feature too low        -> alpha = 1.0
    //   - w_pred high enough         -> alpha = 1.0
    //   - medium w_pred              -> mild weighting
    //   - low w_pred                 -> stronger weighting
    // =========================================================

    const double sigma_base_px = 1.50;

    // 中間區域：只小幅降權
    const double sigma_mild_max_px = 1.58;

    // 明顯低可靠度時：才較強降權
    const double sigma_strong_max_px = 1.70;

    // temporal smoothing，只在真的降權時使用
    const double beta = 0.95;

    // conservative thresholds
    const double reliable_w_thr = 0.75;
    const double risky_w_thr = 0.60;
    const int min_mgr_feature_count = 60;

    double target_alpha = 1.0;
    double sigma_px = sigma_base_px;
    double min_alpha = 1.0;

    bool force_baseline = false;
    const char *policy_reason = "baseline";

    if (!(enable_visual_admission &&
          visual_admission_mode == SOFT_WEIGHT &&
          visual_has_prediction))
    {
        sigma_px = sigma_base_px;
        target_alpha = 1.0;
        force_baseline = true;
        policy_reason = "disabled_or_no_prediction";
    }
    else if (tracked_feature_count_mgr <= min_mgr_feature_count)
    {
        // feature manager 裡的有效 feature 已經太少時，不要再降權。
        // 否則可能把最後的視覺幾何約束也削弱掉。
        sigma_px = sigma_base_px;
        target_alpha = 1.0;
        force_baseline = true;
        policy_reason = "low_mgr_keep_visual";
    }
    else if (raw_w >= reliable_w_thr)
    {
        // deadband：模型覺得視覺可靠，就完全維持 baseline。
        // 這是為了避免 urban28 / urban39 這類穩定 sequence 被每幀微小干擾。
        sigma_px = sigma_base_px;
        target_alpha = 1.0;
        force_baseline = true;
        policy_reason = "deadband_reliable";
    }
    else if (raw_w >= risky_w_thr)
    {
        // 中間區域：保守小幅降權。
        sigma_px = sigma_base_px +
                   (sigma_mild_max_px - sigma_base_px) *
                   (1.0 - raw_w) / (1.0 - risky_w_thr);

        min_alpha = 0.85;
        policy_reason = "mild_uncertain";
    }
    else
    {
        // 明顯低 w_pred：才使用較強 uncertainty mapping。
        sigma_px = sigma_base_px +
                   (sigma_strong_max_px - sigma_base_px) *
                   (1.0 - raw_w);

        min_alpha = 0.70;
        policy_reason = "strong_low_w";
    }

    if (sigma_px < sigma_base_px)
        sigma_px = sigma_base_px;
    if (sigma_px > sigma_strong_max_px)
        sigma_px = sigma_strong_max_px;

    target_alpha = (sigma_base_px / sigma_px) *
                   (sigma_base_px / sigma_px);

    if (target_alpha < min_alpha)
        target_alpha = min_alpha;
    if (target_alpha > 1.0)
        target_alpha = 1.0;

    visual_alpha_target = target_alpha;
    visual_sigma_px = sigma_px;

    if (force_baseline)
    {
        // 重要：
        // 一旦進入 reliable deadband 或 low-feature guard，
        // 直接回 alpha=1.0，不讓 EMA 殘留前面的低 alpha。
        visual_alpha = 1.0;
        visual_alpha_initialized = false;
    }
    else if (!visual_alpha_initialized)
    {
        visual_alpha = target_alpha;
        visual_alpha_initialized = true;
    }
    else
    {
        visual_alpha = beta * visual_alpha +
                       (1.0 - beta) * target_alpha;
    }

    if (visual_alpha < 0.70)
        visual_alpha = 0.70;
    if (visual_alpha > 1.00)
        visual_alpha = 1.00;

    const double sqrt_alpha = std::sqrt(visual_alpha);

    const Eigen::Matrix2d weighted_sqrt_info =
        sqrt_alpha * FOCAL_LENGTH / 1.5 *
        Eigen::Matrix2d::Identity();

    ProjectionTwoFrameOneCamFactor::sqrt_info = weighted_sqrt_info;
    ProjectionTwoFrameTwoCamFactor::sqrt_info = weighted_sqrt_info;
    ProjectionOneFrameTwoCamFactor::sqrt_info = weighted_sqrt_info;

    ROS_INFO("[admission-weight] v43 policy=%s raw_w=%.3f mgr=%d sigma_px=%.3f alpha_target=%.3f alpha=%.3f has_pred=%d mode=%d",
             policy_reason,
             raw_w,
             tracked_feature_count_mgr,
             visual_sigma_px,
             visual_alpha_target,
             visual_alpha,
             visual_has_prediction ? 1 : 0,
             static_cast<int>(visual_admission_mode));
}

void Estimator::updateVisualDebugPre(const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &image)
{
    tracked_feature_count_raw = static_cast<int>(image.size());
    tracked_feature_count_mgr = f_manager.getFeatureCount();
    current_is_keyframe = (marginalization_flag == MARGIN_OLD);

    outlier_count_last = 0;
    inlier_count_last = 0;
    outlier_ratio_last = 0.0;
    failure_detected_last = false;
    solver_time_ms_last = 0.0;
}

void Estimator::updateVisualDebugPost(const set<int> &removeIndex, bool failure_flag, double solver_ms)
{
    outlier_count_last = static_cast<int>(removeIndex.size());
    inlier_count_last = tracked_feature_count_mgr - outlier_count_last;
    if (inlier_count_last < 0)
        inlier_count_last = 0;

    if (tracked_feature_count_mgr > 0)
        outlier_ratio_last = static_cast<double>(outlier_count_last) / static_cast<double>(tracked_feature_count_mgr);
    else
        outlier_ratio_last = 0.0;

    failure_detected_last = failure_flag;
    solver_time_ms_last = solver_ms;

    if (visual_has_prediction)
    visual_gate_pass = (visual_w_pred >= visual_gate_tau);
    else
        visual_gate_pass = true;

    // 不要在 post-debug 階段覆蓋 visual_alpha。
    // visual_alpha 是 backend 實際使用的 smoothed information weight，
    // 只由 applyVisualResidualWeight() 更新。
}

void Estimator::setParameter()
{
    mProcess.lock();
    for (int i = 0; i < NUM_OF_CAM; i++)
    {
        tic[i] = TIC[i];
        ric[i] = RIC[i];
        cout << " exitrinsic cam " << i << endl  << ric[i] << endl << tic[i].transpose() << endl;
    }
    // ===== record initial extrinsic for this run =====
    // 後面 CSV 會記錄「目前外參」相對「起始外參」漂了多少
    if (!reliability_initial_extrinsic_ready)
    {
        for (int i = 0; i < 2; ++i)
        {
            reliability_initial_ric[i].setIdentity();
            reliability_initial_tic[i].setZero();
        }

        for (int i = 0; i < NUM_OF_CAM && i < 2; ++i)
        {
            reliability_initial_ric[i] = ric[i];
            reliability_initial_tic[i] = tic[i];
        }

        reliability_initial_td = td;
        reliability_initial_extrinsic_ready = true;

        ROS_WARN("[reliability] initial extrinsic snapshot saved.");
    }
    f_manager.setRic(ric);
    ProjectionTwoFrameOneCamFactor::sqrt_info = FOCAL_LENGTH / 1.5 * Matrix2d::Identity();
    ProjectionTwoFrameTwoCamFactor::sqrt_info = FOCAL_LENGTH / 1.5 * Matrix2d::Identity();
    ProjectionOneFrameTwoCamFactor::sqrt_info = FOCAL_LENGTH / 1.5 * Matrix2d::Identity();
    td = TD;
    g = G;
    cout << "set g " << g.transpose() << endl;
    featureTracker.readIntrinsicParameter(CAM_NAMES);

    // ======================================================================
    // 【修正版】：把 VINS_RESULT_PATH 後面的 "/vio.csv" 切掉，還原成純資料夾路徑
    std::string folder_path = VINS_RESULT_PATH;
    size_t last_slash = folder_path.find_last_of('/');
    if (last_slash != std::string::npos) {
        folder_path = folder_path.substr(0, last_slash);
    }
    
    // 把純資料夾路徑，接上我們要的統計檔名
    reliability_feature_csv_path = folder_path + "/reliability_features_vins.csv";
    reliability_logger_ready = false; 
    // ======================================================================

    setupReliabilityLogger();

    // 不在 setParameter 內重置 enable_visual_admission / mode / tau，
    // 這樣 clearState()/reboot 後仍可保留使用者選擇的 baseline / thesis 模式。
    clearVisualAdmissionPrediction();

    std::cout << "MULTIPLE_THREAD is " << MULTIPLE_THREAD << '\n';
    if (MULTIPLE_THREAD && !initThreadFlag)
    {
        initThreadFlag = true;
        processThread = std::thread(&Estimator::processMeasurements, this);
    }
    mProcess.unlock();
}

void Estimator::changeSensorType(int use_imu, int use_stereo)
{
    bool restart = false;
    mProcess.lock();
    if(!use_imu && !use_stereo)
        printf("at least use two sensors! \n");
    else
    {
        if(USE_IMU != use_imu)
        {
            USE_IMU = use_imu;
            if(USE_IMU)
            {
                // reuse imu; restart system
                restart = true;
            }
            else
            {
                if (last_marginalization_info != nullptr)
                    delete last_marginalization_info;

                tmp_pre_integration = nullptr;
                last_marginalization_info = nullptr;
                last_marginalization_parameter_blocks.clear();
            }
        }
        
        STEREO = use_stereo;
        printf("use imu %d use stereo %d\n", USE_IMU, STEREO);
    }
    mProcess.unlock();
    if(restart)
    {
        clearState();
        setParameter();
    }
}

// §2 controlled dynamic injection: add a coherent synthetic moving block to the feature frame (leak-free; the
// estimator/RANSAC sees them as ordinary features; ids>=INJ_ID_BASE are the non-circular labels). Simulates a rigid
// moving object: a block of features at depth Z drifting coherently in the image (inconsistent with ego motion).
void Estimator::injectDynamicFeatures(std::map<int, std::vector<std::pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame, double t)
{
    if (featureFrame.empty()) return;
    // Only contaminate a CONVERGED estimator (realistic: a running vehicle meets dynamic objects). Injecting during
    // bootstrap poisons the SfM/IMU init and just kills the run -> no measurable degradation curve.
    if (solver_flag != NON_LINEAR) { inj_init_ = false; return; }
    // recover intrinsics from REAL features (u = fx*nx + cx)
    double Sx=0,Sxx=0,Su=0,Sxu=0, Sy=0,Syy=0,Sv=0,Syv=0; long N=0;
    for (auto &kv : featureFrame) {
        if (kv.first >= INJ_ID_BASE) continue;
        for (auto &obs : kv.second) if (obs.first==0) {
            double nx=obs.second(0),ny=obs.second(1),u=obs.second(3),v=obs.second(4);
            Sx+=nx;Sxx+=nx*nx;Su+=u;Sxu+=nx*u; Sy+=ny;Syy+=ny*ny;Sv+=v;Syv+=ny*v; N++;
        }
    }
    if (N < 20) return;
    double dxd=N*Sxx-Sx*Sx, dyd=N*Syy-Sy*Sy;
    if (std::abs(dxd)<1e-9||std::abs(dyd)<1e-9) return;
    double fx=(N*Sxu-Sx*Su)/dxd, cx=(Su-fx*Sx)/N, fy=(N*Syv-Sy*Sv)/dyd, cy=(Sv-fy*Sy)/N;
    int K = std::max(1, (int)(REL_INJECT_FRAC * N));
    const double Z=15.0, baseline=0.47, disp=baseline/Z;   // KAIST stereo baseline ~0.47m -> normalized disparity
    // coherent block image-plane drift per frame (moving object); normalized. env REL_INJECT_DRIFT overrides (default ~13px@fx818).
    static double vinj_x = []{ const char* e=std::getenv("REL_INJECT_DRIFT"); return e? atof(e):0.016; }();
    const double vinj_y = 0.2*vinj_x;
    if (!inj_init_ || (int)inj_nxny_.size()!=K) {
        inj_nxny_.clear();
        int cols=std::max(1,(int)std::ceil(std::sqrt((double)K)));
        for (int i=0;i<K;i++) inj_nxny_.push_back({-0.10+0.30*((i%cols)/(double)std::max(cols-1,1)),
                                                   -0.10+0.20*((i/cols)/(double)std::max(cols-1,1))});
        inj_init_=true;
    }
    for (auto &p : inj_nxny_){ p.first+=vinj_x; p.second+=vinj_y; }
    if (inj_nxny_[0].first > 0.5) for (auto &p : inj_nxny_) p.first -= 0.6;   // recycle when off-frame
    bool stereo = STEREO;
    for (int i=0;i<K;i++){
        double nx=inj_nxny_[i].first, ny=inj_nxny_[i].second;
        Eigen::Matrix<double,7,1> f0; f0<<nx,ny,1.0, fx*nx+cx, fy*ny+cy, 0.0,0.0;
        std::vector<std::pair<int,Eigen::Matrix<double,7,1>>> obs; obs.push_back({0,f0});
        if (stereo){ double nxr=nx-disp; Eigen::Matrix<double,7,1> f1; f1<<nxr,ny,1.0, fx*nxr+cx, fy*ny+cy,0.0,0.0; obs.push_back({1,f1}); }
        featureFrame[INJ_ID_BASE+i]=obs;
    }
}

void Estimator::inputImage(double t, const cv::Mat &_img, const cv::Mat &_img1)
{
    inputImageCnt++;
    map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> featureFrame;
    TicToc featureTrackerTime;

    if(_img1.empty())
        featureFrame = featureTracker.trackImage(t, _img);
    else
        featureFrame = featureTracker.trackImage(t, _img, _img1);

    // §2 controlled dynamic injection (leak-free, default OFF): add a coherent synthetic moving block BEFORE the
    // estimator/RANSAC sees it. The estimator is blind to which are injected (ids>=INJ_ID_BASE used only for labels).
    if (REL_INJECT_DYNAMIC)
        injectDynamicFeatures(featureFrame, t);

    double tracker_ms = featureTrackerTime.toc();
    if (SAVE_RELIABILITY_FEATURES)
    {
        computePendingFeatureStats(featureFrame, tracker_ms, t, _img.cols, _img.rows);
    }
    //printf("featureTracker time: %f\n", featureTrackerTime.toc());

    if (SHOW_TRACK)
    {
        cv::Mat imgTrack = featureTracker.getTrackImage();
        pubTrackImage(imgTrack, t);
    }
    
    if(MULTIPLE_THREAD)  
    {     
        if(inputImageCnt % 2 == 0)
        {
            mBuf.lock();
            featureBuf.push(make_pair(t, featureFrame));
            mBuf.unlock();
        }
    }
    else
    {
        mBuf.lock();
        featureBuf.push(make_pair(t, featureFrame));
        mBuf.unlock();
        TicToc processTime;
        processMeasurements();
        printf("process time: %f\n", processTime.toc());
    }
    
}

void Estimator::inputIMU(double t, const Vector3d &linearAcceleration, const Vector3d &angularVelocity)
{
    mBuf.lock();
    accBuf.push(make_pair(t, linearAcceleration));
    gyrBuf.push(make_pair(t, angularVelocity));
    //printf("input imu with time %f \n", t);
    mBuf.unlock();

    if (solver_flag == NON_LINEAR)
    {
        mPropagate.lock();
        fastPredictIMU(t, linearAcceleration, angularVelocity);
        pubLatestOdometry(latest_P, latest_Q, latest_V, t);
        mPropagate.unlock();
    }
}

// P1-Wheel: raw measurements stored by timestamp; prune only what no future interval can need.
void Estimator::inputWheel(double t, double dl, double dr, double df)
{
    mWheel.lock();
    wheel_buffer.push_back({t, dl, dr, df});
    // keep a small margin before the oldest keyframe; drop measurements strictly older than (Headers[0]-1s)
    double oldest_need = (frame_count >= 0) ? (Headers[0] - 1.0) : -1.0;
    while (!wheel_buffer.empty() && wheel_buffer.front().timestamp < oldest_need)
        wheel_buffer.pop_front();
    mWheel.unlock();
}

// (P1-Wheel C4) integrateWheel removed — superseded by immutable WheelPreintegration.

// P1-Wheel v3.3 C2: latest raw wheel stamp reaches t? (coverage-wait predicate; B0 never calls this)
bool Estimator::wheelAvailable(double t)
{
    mWheel.lock();
    bool ok = !wheel_buffer.empty() && wheel_buffer.back().timestamp >= t;
    mWheel.unlock();
    return ok;
}

// Build the immutable SE(2) preintegration for interval (t0, t1] into slot idx. n=0 -> valid=false.
void Estimator::buildWheelPreint(int idx, double t0, double t1)
{
    delete wheel_pre_integrations[idx];
    WheelPreintegration *wp = new WheelPreintegration(wheel_b_, wheel_sigmaL_, wheel_sigmaR_);
    wp->t_start = t0; wp->t_end = t1;
    mWheel.lock();
    for (const auto &w : wheel_buffer)
        if (w.timestamp > t0 && w.timestamp <= t1)
            wp->addSample(w.delta_left, w.delta_right);
    mWheel.unlock();
    wp->valid = (wp->n_samples > 0);
    wheel_pre_integrations[idx] = wp;
}

// P1-FogWheel: FOG yaw raw input + preintegration build (mirror of wheel).
void Estimator::inputFogYaw(double t, double dyaw, double dt)
{
    mFog.lock();
    fog_buffer.push_back({t, dyaw, dt});
    double oldest_need = (frame_count >= 0) ? (Headers[0] - 1.0) : -1.0;
    while (!fog_buffer.empty() && fog_buffer.front().timestamp < oldest_need)
        fog_buffer.pop_front();
    mFog.unlock();
}

bool Estimator::fogYawAvailable(double t)
{
    mFog.lock();
    bool ok = !fog_buffer.empty() && fog_buffer.back().timestamp >= t;
    mFog.unlock();
    return ok;
}

void Estimator::buildFogYawPreint(int idx, double t0, double t1)
{
    delete fog_yaw_preint[idx];
    FogYawPreintegration *fp = new FogYawPreintegration(fog_arw_);
    fp->t_start = t0; fp->t_end = t1;
    mFog.lock();
    for (const auto &f : fog_buffer)
        if (f.timestamp > t0 && f.timestamp <= t1)
            fp->addSample(f.dyaw, f.dt);
    mFog.unlock();
    fp->valid = (fp->n_samples > 0);
    fog_yaw_preint[idx] = fp;
}

void Estimator::inputFeature(double t, const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame)
{
    ROS_ERROR("deprecated at VINS-Fusion");
    assert(0);
    mBuf.lock();
    featureBuf.push(make_pair(t, featureFrame));
    mBuf.unlock();

    if(!MULTIPLE_THREAD)
        processMeasurements();
}


bool Estimator::getIMUInterval(double t0, double t1, vector<pair<double, Eigen::Vector3d>> &accVector, 
                                vector<pair<double, Eigen::Vector3d>> &gyrVector)
{
    if(accBuf.empty())
    {
        printf("not receive imu\n");
        return false;
    }
    // printf("get imu from %f %f\n", t0, t1);
    // printf("imu fornt time %f   imu end time %f\n", accBuf.front().first, accBuf.back().first);
    if(t1 <= accBuf.back().first)
    {
        while (accBuf.front().first <= t0)
        {
            // std::cout << "t_imu: " << std::fixed << accBuf.front().first << "  t_0: " << std::fixed << t0 << "   gyr_buf size: " << gyrBuf.size() << std::endl;
            // std::cout << "1) acc pop" << std::endl;
            accBuf.pop();
            // std::cout << "1) gyr pop" << std::endl;
            gyrBuf.pop();
        }
        while (accBuf.front().first < t1)
        {
            accVector.push_back(accBuf.front());
            // std::cout << "2) acc pop" << std::endl;
            accBuf.pop();
            gyrVector.push_back(gyrBuf.front());
            // std::cout << "2) gyr pop" << std::endl;
            gyrBuf.pop();
        }
        accVector.push_back(accBuf.front());
        gyrVector.push_back(gyrBuf.front());
    }
    else
    {
        printf("wait for imu\n");
        return false;
    }
    return true;
}

bool Estimator::IMUAvailable(double t)
{
    if(!accBuf.empty() && t <= accBuf.back().first)
        return true;
    else
        return false;
}

void Estimator::processMeasurements()
{
    while (1)
    {
        // cout << "[processMeasurements]  loop - start" << endl;

        pair<double, map<int, vector<pair<int, Eigen::Matrix<double, 7, 1> > > > > feature;
        vector<pair<double, Eigen::Vector3d>> accVector, gyrVector;

        if(!featureBuf.empty())
        {
            // ============================================================
            // 1. 取出目前這一幀 featureFrame
            // ============================================================
            feature = featureBuf.front();
            curTime = feature.first + td;

            // ============================================================
            // 2. 等 IMU buffer 裡面有足夠資料可以覆蓋這一幀時間
            // ============================================================
            // P1-Wheel v3.3 C2: coverage-wait incl. wheel (only when WHEEL_FACTOR_ENABLE); 0.5s wall timeout.
            int wheel_wait_ms = 0; bool wheel_timed_out = false;
            while(1)
            {
                bool imu_ok = (!USE_IMU || IMUAvailable(feature.first + td));
                bool wheel_ok = (!WHEEL_FACTOR_ENABLE) || wheelAvailable(feature.first + td) || wheel_timed_out;
                bool fog_ok = (!FOG_YAW_ENABLE) || fogYawAvailable(feature.first + td) || wheel_timed_out;
                if (imu_ok && wheel_ok && fog_ok)
                    break;
                else
                {
                    if (!imu_ok) printf("wait for imu ... \n");
                    if (!MULTIPLE_THREAD)
                        return;
                    std::chrono::milliseconds dura(5);
                    std::this_thread::sleep_for(dura);
                    if (WHEEL_FACTOR_ENABLE && !wheel_ok && imu_ok) {
                        wheel_wait_ms += 5;
                        if (wheel_wait_ms >= 500) { wheel_timed_out = true; printf("[WHEEL] coverage-wait TIMEOUT 0.5s @t=%.4f -> interval invalid\n", feature.first); }
                    }
                }
            }

            // ============================================================
            // 3. 從 IMU buffer 取出 prevTime -> curTime 的 IMU interval
            //
            // 注意：
            // - computePendingImuStats() 會在這裡計算：
            //   acc/gyr norm
            //   SO(3) gyro integration
            //   gyro axis-wise statistics
            //   IMU dt statistics
            // - featureBuf.pop() 只把 queue 裡的資料移除；
            //   feature 這個 local copy 仍然還在，後面可以繼續用。
            // ============================================================
            mBuf.lock();

            if(USE_IMU)
            {
                getIMUInterval(prevTime, curTime, accVector, gyrVector);

                if (SAVE_RELIABILITY_FEATURES)
                {
                    computePendingImuStats(accVector, gyrVector);
                }
            }
            else
            {
                if (SAVE_RELIABILITY_FEATURES)
                {
                    computePendingImuStats(accVector, gyrVector);
                }
            }

            featureBuf.pop();
            mBuf.unlock();

            // ============================================================
            // 4. 新增 v5 visual-gyro consistency feature
            //
            // 為什麼放在這裡：
            // - computePendingImuStats() 已經算完 pending gyro SO(3) / gyro mean
            // - feature.second 還是這一幀的 featureFrame local copy
            // - 這裡不在 mBuf lock 裡面，避免把較重的 feature 統計卡在 buffer lock 中
            //
            // 這個函式會計算：
            // - gyro-predicted rotational optical flow
            // - observed feature flow
            // - flow residual / cos similarity / magnitude ratio
            // ============================================================
            if (SAVE_RELIABILITY_FEATURES)
            {
                computePendingVisionGyroConsistencyStats(feature.second);
            }

            // ============================================================
            // 5. 原本 VINS IMU propagation，不改主流程
            // ============================================================
            if(USE_IMU)
            {
                if(!initFirstPoseFlag)
                    initFirstIMUPose(accVector);

                for(size_t i = 0; i < accVector.size(); i++)
                {
                    double dt;

                    if(i == 0)
                        dt = accVector[i].first - prevTime;
                    else if (i == accVector.size() - 1)
                        dt = curTime - accVector[i - 1].first;
                    else
                        dt = accVector[i].first - accVector[i - 1].first;

                    processIMU(accVector[i].first, dt, accVector[i].second, gyrVector[i].second);
                }
            }

            // ============================================================
            // 6. 原本 VINS image processing / optimization，不改主流程
            //
            // processImage() 裡面會做：
            // - addFeatureCheckParallax
            // - optimization
            // - updateVisualDebugPost
            // - computeManagerFeatureStats
            // - buildReliabilityFeatureJson
            // - writeReliabilityFeatureRow
            //
            // 其中 writeReliabilityFeatureRow() 後面會再把：
            // gyro delta vs VINS delta
            // 這類需要 optimization 後 pose 的 feature 寫進 row。
            // ============================================================
            mProcess.lock();

            processImage(feature.second, feature.first);
            prevTime = curTime;

            printStatistics(*this, 0);

            std_msgs::msg::Header header;
            header.frame_id = "world";

            int sec_ts = (int)feature.first;
            uint nsec_ts = (uint)((feature.first - sec_ts) * 1e9);
            header.stamp.sec = sec_ts;
            header.stamp.nanosec = nsec_ts;

            pubOdometry(*this, header);
            pubKeyPoses(*this, header);
            pubCameraPose(*this, header);
            pubPointCloud(*this, header);
            pubKeyframe(*this);
            pubTF(*this, header);

            mProcess.unlock();
        }

        if (!MULTIPLE_THREAD)
            break;

        std::chrono::milliseconds dura(2);
        std::this_thread::sleep_for(dura);
    }
}


void Estimator::computePendingVisionGyroConsistencyStats(
    const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame)
{
    std::vector<double> obs_mags;
    std::vector<double> pred_mags;
    std::vector<double> res_mags;
    std::vector<double> res_flip_mags;
    std::vector<double> res_min_mags;
    std::vector<double> cos_vals;
    std::vector<double> ratio_vals;

    const int bg_idx = std::max(0, std::min(frame_count, WINDOW_SIZE));
    const Eigen::Vector3d bg = Bgs[bg_idx];

    // 用 bias-corrected mean gyro，轉到 cam0 frame
    Eigen::Vector3d w_imu(
        pending_gyr_bgcorr_x_mean,
        pending_gyr_bgcorr_y_mean,
        pending_gyr_bgcorr_z_mean
    );

    Eigen::Vector3d w_cam = ric[0].transpose() * w_imu;

    const double wx = w_cam.x();
    const double wy = w_cam.y();
    const double wz = w_cam.z();

    for (const auto &kv : featureFrame)
    {
        for (const auto &obs_pair : kv.second)
        {
            if (obs_pair.first != 0)
                continue;

            const auto &obs = obs_pair.second;

            const double x = obs(0);
            const double y = obs(1);
            const double vx = obs(5);
            const double vy = obs(6);

            if (!std::isfinite(x) || !std::isfinite(y) ||
                !std::isfinite(vx) || !std::isfinite(vy))
                continue;

            // normalized image velocity due to camera rotation
            const double pred_vx =
                x * y * wx - (1.0 + x * x) * wy + y * wz;

            const double pred_vy =
                (1.0 + y * y) * wx - x * y * wy - x * wz;

            const Eigen::Vector2d v_obs(vx, vy);
            const Eigen::Vector2d v_pred(pred_vx, pred_vy);

            const double obs_norm = v_obs.norm();
            const double pred_norm = v_pred.norm();

            const double res = (v_obs - v_pred).norm();
            const double res_flip = (v_obs + v_pred).norm();
            const double res_min = std::min(res, res_flip);

            obs_mags.push_back(obs_norm);
            pred_mags.push_back(pred_norm);
            res_mags.push_back(res);
            res_flip_mags.push_back(res_flip);
            res_min_mags.push_back(res_min);

            if (obs_norm > 1e-9 && pred_norm > 1e-9)
            {
                double c = v_obs.dot(v_pred) / (obs_norm * pred_norm);
                c = std::max(-1.0, std::min(1.0, c));
                cos_vals.push_back(c);
                ratio_vals.push_back(obs_norm / std::max(pred_norm, 1e-9));
            }
        }
    }

    pending_vg_flow_valid_count = static_cast<int>(obs_mags.size());

    pending_vg_flow_obs_mean = meanOf(obs_mags);
    pending_vg_flow_obs_std = stdOf(obs_mags);
    pending_vg_flow_obs_p90 = percentileOf(obs_mags, 0.90);

    pending_vg_flow_pred_mean = meanOf(pred_mags);
    pending_vg_flow_pred_std = stdOf(pred_mags);
    pending_vg_flow_pred_p90 = percentileOf(pred_mags, 0.90);

    pending_vg_flow_res_mean = meanOf(res_mags);
    pending_vg_flow_res_std = stdOf(res_mags);
    pending_vg_flow_res_p90 = percentileOf(res_mags, 0.90);

    pending_vg_flow_res_flip_mean = meanOf(res_flip_mags);
    pending_vg_flow_res_min_mean = meanOf(res_min_mags);

    pending_vg_flow_cos_mean = meanOf(cos_vals);
    pending_vg_flow_cos_median = medianOf(cos_vals);

    pending_vg_flow_mag_ratio_median = medianOf(ratio_vals);
    pending_vg_flow_mag_ratio_p90 = percentileOf(ratio_vals, 0.90);
}

void Estimator::initFirstIMUPose(vector<pair<double, Eigen::Vector3d>> &accVector)
{
    printf("init first imu pose\n");
    initFirstPoseFlag = true;
    //return;
    Eigen::Vector3d averAcc(0, 0, 0);
    int n = (int)accVector.size();
    for(size_t i = 0; i < accVector.size(); i++)
    {
        averAcc = averAcc + accVector[i].second;
    }
    averAcc = averAcc / n;
    printf("averge acc %f %f %f\n", averAcc.x(), averAcc.y(), averAcc.z());
    Matrix3d R0 = Utility::g2R(averAcc);
    {
        static const bool DBG_GI = (std::getenv("DEBUG_GRAVITY_INIT") &&
                                    std::string(std::getenv("DEBUG_GRAVITY_INIT")) == "1");
        if (DBG_GI) {
            Eigen::Vector3d rpy = Utility::R2ypr(R0);
            ROS_INFO("[DBG_IMU_CONVENTION] stage=initFirstIMUPose averAcc=%.4f %.4f %.4f acc_norm=%.4f "
                     "G_world=%.4f %.4f %.4f g2R_rpy=%.3f %.3f %.3f det_R0=%.4f n=%d",
                     averAcc.x(), averAcc.y(), averAcc.z(), averAcc.norm(),
                     G.x(), G.y(), G.z(), rpy.x(), rpy.y(), rpy.z(), R0.determinant(), n);
        }
    }
    double yaw = Utility::R2ypr(R0).x();
    R0 = Utility::ypr2R(Eigen::Vector3d{-yaw, 0, 0}) * R0;
    Rs[0] = R0;
    cout << "init R0 " << endl << Rs[0] << endl;
    //Vs[0] = Vector3d(5, 0, 0);
}

void Estimator::initFirstPose(Eigen::Vector3d p, Eigen::Matrix3d r)
{
    Ps[0] = p;
    Rs[0] = r;
    initP = p;
    initR = r;
}


void Estimator::processIMU(double t, double dt, const Vector3d &linear_acceleration, const Vector3d &angular_velocity)
{
    if (!first_imu)
    {
        first_imu = true;
        acc_0 = linear_acceleration;
        gyr_0 = angular_velocity;
    }

    if (!pre_integrations[frame_count])
    {
        pre_integrations[frame_count] = new IntegrationBase{acc_0, gyr_0, Bas[frame_count], Bgs[frame_count]};
    }
    if (frame_count != 0)
    {
        pre_integrations[frame_count]->push_back(dt, linear_acceleration, angular_velocity);
        //if(solver_flag != NON_LINEAR)
            tmp_pre_integration->push_back(dt, linear_acceleration, angular_velocity);

        dt_buf[frame_count].push_back(dt);
        linear_acceleration_buf[frame_count].push_back(linear_acceleration);
        angular_velocity_buf[frame_count].push_back(angular_velocity);

        int j = frame_count;         
        Vector3d un_acc_0 = Rs[j] * (acc_0 - Bas[j]) - g;
        Vector3d un_gyr = 0.5 * (gyr_0 + angular_velocity) - Bgs[j];
        Rs[j] *= Utility::deltaQ(un_gyr * dt).toRotationMatrix();
        Vector3d un_acc_1 = Rs[j] * (linear_acceleration - Bas[j]) - g;
        Vector3d un_acc = 0.5 * (un_acc_0 + un_acc_1);
        Ps[j] += dt * Vs[j] + 0.5 * dt * dt * un_acc;
        Vs[j] += dt * un_acc;
    }
    acc_0 = linear_acceleration;
    gyr_0 = angular_velocity; 
}

void Estimator::processImage(const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &image, const double header)
{


    cout << std::fixed << header << endl;

    ROS_DEBUG("new image coming ------------------------------------------");
    ROS_DEBUG("Adding feature points %lu", image.size());
    f_manager.perfeat_cur_ts = header;   // per-feature ORACLE drop hook (default OFF) needs the frame ts
    if (f_manager.addFeatureCheckParallax(frame_count, image, td))
    {
        marginalization_flag = MARGIN_OLD;
        //printf("keyframe\n");
    }
    else
    {
        marginalization_flag = MARGIN_SECOND_NEW;
        //printf("non-keyframe\n");
    }

    // visual admission debug: pre-optimization
    updateVisualDebugPre(image);

    ROS_DEBUG("%s", marginalization_flag ? "Non-keyframe" : "Keyframe");
    ROS_DEBUG("Solving %d", frame_count);
    ROS_DEBUG("number of feature: %d", f_manager.getFeatureCount());
    Headers[frame_count] = header;
    // P1-Wheel v3.3 C2: freeze the SE(2) wheel preintegration for interval (Headers[fc-1], Headers[fc]].
    if ((WHEEL_FACTOR_ENABLE || WHEEL_REFERENCE_ONLY) && frame_count > 0)
        buildWheelPreint(frame_count, Headers[frame_count - 1], Headers[frame_count]);
    if ((FOG_YAW_ENABLE || FOG_YAW_REFERENCE_ONLY) && frame_count > 0)
        buildFogYawPreint(frame_count, Headers[frame_count - 1], Headers[frame_count]);

    ImageFrame imageframe(image, header);
    imageframe.pre_integration = tmp_pre_integration;
    all_image_frame.insert(make_pair(header, imageframe));
    tmp_pre_integration = new IntegrationBase{acc_0, gyr_0, Bas[frame_count], Bgs[frame_count]};

    if(ESTIMATE_EXTRINSIC == 2)
    {
        ROS_INFO("calibrating extrinsic param, rotation movement is needed");
        if (frame_count != 0)
        {
            vector<pair<Vector3d, Vector3d>> corres = f_manager.getCorresponding(frame_count - 1, frame_count);
            Matrix3d calib_ric;
            if (initial_ex_rotation.CalibrationExRotation(corres, pre_integrations[frame_count]->delta_q, calib_ric))
            {
                ROS_WARN("initial extrinsic rotation calib success");
                // ROS_WARN_STREAM("initial extrinsic rotation: " << endl << calib_ric);
                ric[0] = calib_ric;
                RIC[0] = calib_ric;
                ESTIMATE_EXTRINSIC = 1;
            }
        }
    }


    if (solver_flag == INITIAL)
    {
        // NOTE:
        // visual admission 第一版先不介入初始化流程，
        // 初始化期只做 debug，不改動原本 VINS 行為。
        // monocular + IMU initilization
        if (!STEREO && USE_IMU)
        {
            if (frame_count == WINDOW_SIZE)
            {
                bool result = false;
                if(ESTIMATE_EXTRINSIC != 2 && (header - initial_timestamp) > 0.1)
                {
                    result = initialStructure();
                    initial_timestamp = header;   
                }
                if(result)
                {
                    optimization();
                    updateLatestStates();
                    solver_flag = NON_LINEAR;
                    slideWindow();
                    ROS_INFO("Initialization finish!");
                }
                else
                    slideWindow();
            }
        }

        // stereo + IMU initilization
        if(STEREO && USE_IMU)
        {
            f_manager.initFramePoseByPnP(frame_count, Ps, Rs, tic, ric);
            f_manager.triangulate(frame_count, Ps, Rs, tic, ric);
            if (frame_count == WINDOW_SIZE)
            {
                map<double, ImageFrame>::iterator frame_it;
                int i = 0;
                for (frame_it = all_image_frame.begin(); frame_it != all_image_frame.end(); frame_it++)
                {
                    frame_it->second.R = Rs[i];
                    frame_it->second.T = Ps[i];
                    i++;
                }
                // CARLA fix-bias (experimental, REL_FIX_IMU_BIAS=1, default OFF): skip init gyro-bias estimation
                // (synth IMU has true bias 0) so init cannot mis-estimate gravity-into-bias.
                static int FIX_BIAS_INIT = []{ const char* e=std::getenv("REL_FIX_IMU_BIAS"); return (e && std::string(e)=="1")?1:0; }();
                if (!FIX_BIAS_INIT)
                    solveGyroscopeBias(all_image_frame, Bgs);
                for (int i = 0; i <= WINDOW_SIZE; i++)
                {
                    pre_integrations[i]->repropagate(Vector3d::Zero(), Bgs[i]);
                }
                optimization();
                updateLatestStates();
                solver_flag = NON_LINEAR;
                slideWindow();
                ROS_INFO("Initialization finish!");
            }
        }

        // stereo only initilization
        if(STEREO && !USE_IMU)
        {
            f_manager.initFramePoseByPnP(frame_count, Ps, Rs, tic, ric);
            f_manager.triangulate(frame_count, Ps, Rs, tic, ric);
            optimization();

            if(frame_count == WINDOW_SIZE)
            {
                optimization();
                updateLatestStates();
                solver_flag = NON_LINEAR;
                slideWindow();
                ROS_INFO("Initialization finish!");
            }
        }

        if(frame_count < WINDOW_SIZE)
        {
            frame_count++;
            int prev_frame = frame_count - 1;
            Ps[frame_count] = Ps[prev_frame];
            Vs[frame_count] = Vs[prev_frame];
            Rs[frame_count] = Rs[prev_frame];
            Bas[frame_count] = Bas[prev_frame];
            Bgs[frame_count] = Bgs[prev_frame];
        }

    }
    else
    {
        if(!USE_IMU)
            f_manager.initFramePoseByPnP(frame_count, Ps, Rs, tic, ric);
        f_manager.triangulate(frame_count, Ps, Rs, tic, ric);

        // apply reliability soft weighting before optimization
        applyVisualResidualWeight();

        ROS_INFO("[admission-weight] apply visual residual weight: alpha=%.3f w=%.3f has_pred=%d",
                visual_alpha,
                visual_w_pred,
                visual_has_prediction ? 1 : 0);

        // optimization
        TicToc t_solve;
        optimization();
        double solver_ms = t_solve.toc();
        ROS_INFO("solver costs: %f [ms]", solver_ms);

        set<int> removeIndex;
        outliersRejection(removeIndex);
        f_manager.removeOutlier(removeIndex);
        if (! MULTIPLE_THREAD)
        {
            featureTracker.removeOutliers(removeIndex);
            predictPtsInNextFrame();
        }

        bool failure_flag = failureDetection();

        // visual admission debug: post-optimization
        updateVisualDebugPost(removeIndex, failure_flag, solver_ms);

        if (SAVE_RELIABILITY_FEATURES)
        {
            computeManagerFeatureStats();

            // 先 publish JSON，再寫 CSV。
            // 原因：writeReliabilityFeatureRow() 會更新 reliability_prev_logged_P/Q，
            // 如果先寫 CSV 再 build JSON，delta_p_norm / delta_q_deg 可能會被重置成接近 0。
            if (reliability_feature_json_callback)
            {
                reliability_feature_json_callback(buildReliabilityFeatureJson(header));
            }

            writeReliabilityFeatureRow(header);
        }

        // P1-Reliability R1: per-feature read-only logging (own flag, default OFF; never feeds optimization)
        if (SAVE_PERFEAT_RELIABILITY)
            writePerFeatRows(header);

        ROS_INFO("[admission-debug] raw=%d mgr=%d key=%d outlier=%d inlier=%d ratio=%.4f w=%.3f gate=%d alpha=%.3f fail=%d",
                 tracked_feature_count_raw,
                 tracked_feature_count_mgr,
                 current_is_keyframe ? 1 : 0,
                 outlier_count_last,
                 inlier_count_last,
                 outlier_ratio_last,
                 visual_w_pred,
                 visual_gate_pass ? 1 : 0,
                 visual_alpha,
                 failure_detected_last ? 1 : 0);

        if (failure_flag)
        {
            ROS_WARN("failure detection!");
            failure_occur = 1;
            clearState();
            setParameter();
            ROS_WARN("system reboot!");
            return;
        }
        // if (failure_flag)
        // {
        //     ROS_WARN("[SOFT_FAILURE] failure detection! keep estimator running for data collection.");
        //     failure_occur = 1;

        //     // ============================================================
        //     // SOFT FAILURE MODE for reliability feature collection
        //     //
        //     // 原本 VINS-Fusion 在 failureDetection() 後會：
        //     //   clearState();
        //     //   setParameter();
        //     //   return;
        //     //
        //     // 這會導致 estimator reset，後面資料就不是同一段連續軌跡。
        //     // 為了收集 failure 前後的 reliability feature，
        //     // 這裡先不 reset，只在 CSV 裡保留 failure_detected_last = 1。
        //     // ============================================================

        //     // clearState();
        //     // setParameter();
        //     // ROS_WARN("system reboot!");
        //     // return;
        // }
        slideWindow();
        f_manager.removeFailures();
        // prepare output of VINS
        key_poses.clear();
        for (int i = 0; i <= WINDOW_SIZE; i++)
            key_poses.push_back(Ps[i]);

        last_R = Rs[WINDOW_SIZE];
        last_P = Ps[WINDOW_SIZE];
        last_R0 = Rs[0];
        last_P0 = Ps[0];
        updateLatestStates();
    }  
}

bool Estimator::initialStructure()
{
    TicToc t_sfm;
    //check imu observibility
    {
        map<double, ImageFrame>::iterator frame_it;
        Vector3d sum_g;
        for (frame_it = all_image_frame.begin(), frame_it++; frame_it != all_image_frame.end(); frame_it++)
        {
            double dt = frame_it->second.pre_integration->sum_dt;
            Vector3d tmp_g = frame_it->second.pre_integration->delta_v / dt;
            sum_g += tmp_g;
        }
        Vector3d aver_g;
        aver_g = sum_g * 1.0 / ((int)all_image_frame.size() - 1);
        double var = 0;
        for (frame_it = all_image_frame.begin(), frame_it++; frame_it != all_image_frame.end(); frame_it++)
        {
            double dt = frame_it->second.pre_integration->sum_dt;
            Vector3d tmp_g = frame_it->second.pre_integration->delta_v / dt;
            var += (tmp_g - aver_g).transpose() * (tmp_g - aver_g);
            //cout << "frame g " << tmp_g.transpose() << endl;
        }
        var = sqrt(var / ((int)all_image_frame.size() - 1));
        //ROS_WARN("IMU variation %f!", var);
        if(var < 0.25)
        {
            ROS_INFO("IMU excitation not enouth!");
            //return false;
        }
    }
    // global sfm
    Quaterniond Q[frame_count + 1];
    Vector3d T[frame_count + 1];
    map<int, Vector3d> sfm_tracked_points;
    vector<SFMFeature> sfm_f;
    for (auto &it_per_id : f_manager.feature)
    {
        int imu_j = it_per_id.start_frame - 1;
        SFMFeature tmp_feature;
        tmp_feature.state = false;
        tmp_feature.id = it_per_id.feature_id;
        for (auto &it_per_frame : it_per_id.feature_per_frame)
        {
            imu_j++;
            Vector3d pts_j = it_per_frame.point;
            tmp_feature.observation.push_back(make_pair(imu_j, Eigen::Vector2d{pts_j.x(), pts_j.y()}));
        }
        sfm_f.push_back(tmp_feature);
    } 
    Matrix3d relative_R;
    Vector3d relative_T;
    int l;
    if (!relativePose(relative_R, relative_T, l))
    {
        ROS_INFO("Not enough features or parallax; Move device around");
        return false;
    }
    GlobalSFM sfm;
    if(!sfm.construct(frame_count + 1, Q, T, l,
              relative_R, relative_T,
              sfm_f, sfm_tracked_points))
    {
        ROS_DEBUG("global SFM failed!");
        marginalization_flag = MARGIN_OLD;
        return false;
    }

    //solve pnp for all frame
    map<double, ImageFrame>::iterator frame_it;
    map<int, Vector3d>::iterator it;
    frame_it = all_image_frame.begin( );
    for (int i = 0; frame_it != all_image_frame.end( ); frame_it++)
    {
        // provide initial guess
        cv::Mat r, rvec, t, D, tmp_r;
        if((frame_it->first) == Headers[i])
        {
            frame_it->second.is_key_frame = true;
            frame_it->second.R = Q[i].toRotationMatrix() * RIC[0].transpose();
            frame_it->second.T = T[i];
            i++;
            continue;
        }
        if((frame_it->first) > Headers[i])
        {
            i++;
        }
        Matrix3d R_inital = (Q[i].inverse()).toRotationMatrix();
        Vector3d P_inital = - R_inital * T[i];
        cv::eigen2cv(R_inital, tmp_r);
        cv::Rodrigues(tmp_r, rvec);
        cv::eigen2cv(P_inital, t);

        frame_it->second.is_key_frame = false;
        vector<cv::Point3f> pts_3_vector;
        vector<cv::Point2f> pts_2_vector;
        for (auto &id_pts : frame_it->second.points)
        {
            int feature_id = id_pts.first;
            for (auto &i_p : id_pts.second)
            {
                it = sfm_tracked_points.find(feature_id);
                if(it != sfm_tracked_points.end())
                {
                    Vector3d world_pts = it->second;
                    cv::Point3f pts_3(world_pts(0), world_pts(1), world_pts(2));
                    pts_3_vector.push_back(pts_3);
                    Vector2d img_pts = i_p.second.head<2>();
                    cv::Point2f pts_2(img_pts(0), img_pts(1));
                    pts_2_vector.push_back(pts_2);
                }
            }
        }
        cv::Mat K = (cv::Mat_<double>(3, 3) << 1, 0, 0, 0, 1, 0, 0, 0, 1);     
        if(pts_3_vector.size() < 6)
        {
            cout << "pts_3_vector size " << pts_3_vector.size() << endl;
            ROS_DEBUG("Not enough points for solve pnp !");
            return false;
        }
        if (! cv::solvePnP(pts_3_vector, pts_2_vector, K, D, rvec, t, 1))
        {
            ROS_DEBUG("solve pnp fail!");
            return false;
        }
        cv::Rodrigues(rvec, r);
        MatrixXd R_pnp,tmp_R_pnp;
        cv::cv2eigen(r, tmp_R_pnp);
        R_pnp = tmp_R_pnp.transpose();
        MatrixXd T_pnp;
        cv::cv2eigen(t, T_pnp);
        T_pnp = R_pnp * (-T_pnp);
        frame_it->second.R = R_pnp * RIC[0].transpose();
        frame_it->second.T = T_pnp;
    }
    if (visualInitialAlign())
        return true;
    else
    {
        ROS_INFO("misalign visual structure with IMU");
        return false;
    }

}

bool Estimator::visualInitialAlign()
{
    TicToc t_g;
    VectorXd x;
    //solve scale
    bool result = VisualIMUAlignment(all_image_frame, Bgs, g, x);
    if(!result)
    {
        ROS_DEBUG("solve g failed!");
        return false;
    }

    // change state
    for (int i = 0; i <= frame_count; i++)
    {
        Matrix3d Ri = all_image_frame[Headers[i]].R;
        Vector3d Pi = all_image_frame[Headers[i]].T;
        Ps[i] = Pi;
        Rs[i] = Ri;
        all_image_frame[Headers[i]].is_key_frame = true;
    }

    double s = (x.tail<1>())(0);
    for (int i = 0; i <= WINDOW_SIZE; i++)
    {
        pre_integrations[i]->repropagate(Vector3d::Zero(), Bgs[i]);
    }
    for (int i = frame_count; i >= 0; i--)
        Ps[i] = s * Ps[i] - Rs[i] * TIC[0] - (s * Ps[0] - Rs[0] * TIC[0]);
    int kv = -1;
    map<double, ImageFrame>::iterator frame_i;
    for (frame_i = all_image_frame.begin(); frame_i != all_image_frame.end(); frame_i++)
    {
        if(frame_i->second.is_key_frame)
        {
            kv++;
            Vs[kv] = frame_i->second.R * x.segment<3>(kv * 3);
        }
    }

    Matrix3d R0 = Utility::g2R(g);
    // ---- gravity/init diagnostic (DEBUG ONLY; print-only) ----
    {
        static const bool DBG_GI = (std::getenv("DEBUG_GRAVITY_INIT") &&
                                    std::string(std::getenv("DEBUG_GRAVITY_INIT")) == "1");
        if (DBG_GI) {
            Eigen::Vector3d g_before = g;
            Eigen::Vector3d rpy0 = Utility::R2ypr(R0);
            ROS_INFO("[DBG_INIT_GRAVITY] stage=after_visualInitialAlign g_est=%.4f %.4f %.4f g_norm=%.4f "
                     "G_world=%.4f %.4f %.4f g2R_rpy=%.3f %.3f %.3f det_R0=%.4f",
                     g_before.x(), g_before.y(), g_before.z(), g_before.norm(),
                     G.x(), G.y(), G.z(), rpy0.x(), rpy0.y(), rpy0.z(), R0.determinant());
        }
    }
    double yaw = Utility::R2ypr(R0 * Rs[0]).x();
    R0 = Utility::ypr2R(Eigen::Vector3d{-yaw, 0, 0}) * R0;
    g = R0 * g;
    {
        static const bool DBG_GI = (std::getenv("DEBUG_GRAVITY_INIT") &&
                                    std::string(std::getenv("DEBUG_GRAVITY_INIT")) == "1");
        if (DBG_GI) {
            Eigen::Vector3d rpy_g2R = Utility::R2ypr(R0);
            Eigen::Vector3d rpyR0_state = Utility::R2ypr(Rs[0]);
            ROS_INFO("[DBG_INIT_GRAVITY] stage=after_g2R g_aligned=%.4f %.4f %.4f g_norm=%.4f "
                     "rot_diff_rpy=%.3f %.3f %.3f Rs0_rpy=%.3f %.3f %.3f V0=%.4f Bas0=%.5f Bgs0=%.6f",
                     g.x(), g.y(), g.z(), g.norm(),
                     rpy_g2R.x(), rpy_g2R.y(), rpy_g2R.z(),
                     rpyR0_state.x(), rpyR0_state.y(), rpyR0_state.z(),
                     Vs[0].norm(), Bas[0].norm(), Bgs[0].norm());
        }
    }
    //Matrix3d rot_diff = R0 * Rs[0].transpose();
    Matrix3d rot_diff = R0;
    for (int i = 0; i <= frame_count; i++)
    {
        Ps[i] = rot_diff * Ps[i];
        Rs[i] = rot_diff * Rs[i];
        Vs[i] = rot_diff * Vs[i];
    }
    // ROS_DEBUG_STREAM("g0     " << g.transpose());
    // ROS_DEBUG_STREAM("my R0  " << Utility::R2ypr(Rs[0]).transpose()); 

    f_manager.clearDepth();
    f_manager.triangulate(frame_count, Ps, Rs, tic, ric);

    return true;
}

bool Estimator::relativePose(Matrix3d &relative_R, Vector3d &relative_T, int &l)
{
    // find previous frame which contians enough correspondance and parallex with newest frame
    for (int i = 0; i < WINDOW_SIZE; i++)
    {
        vector<pair<Vector3d, Vector3d>> corres;
        corres = f_manager.getCorresponding(i, WINDOW_SIZE);
        if (corres.size() > 20)
        {
            double sum_parallax = 0;
            double average_parallax;
            for (int j = 0; j < int(corres.size()); j++)
            {
                Vector2d pts_0(corres[j].first(0), corres[j].first(1));
                Vector2d pts_1(corres[j].second(0), corres[j].second(1));
                double parallax = (pts_0 - pts_1).norm();
                sum_parallax = sum_parallax + parallax;

            }
            average_parallax = 1.0 * sum_parallax / int(corres.size());
            if(average_parallax * 460 > 30 && m_estimator.solveRelativeRT(corres, relative_R, relative_T))
            {
                l = i;
                ROS_DEBUG("average_parallax %f choose l %d and newest frame to triangulate the whole structure", average_parallax * 460, l);
                return true;
            }
        }
    }
    return false;
}

void Estimator::vector2double()
{
    for (int i = 0; i <= WINDOW_SIZE; i++)
    {
        // cout << Ps[i].x() << " " << Ps[i].y() << " " << Ps[i].z() << endl;
        // cout << "--------" << endl;

        para_Pose[i][0] = Ps[i].x();
        para_Pose[i][1] = Ps[i].y();
        para_Pose[i][2] = Ps[i].z();
        Quaterniond q{Rs[i]};
        para_Pose[i][3] = q.x();
        para_Pose[i][4] = q.y();
        para_Pose[i][5] = q.z();
        para_Pose[i][6] = q.w();

        if(USE_IMU)
        {
            para_SpeedBias[i][0] = Vs[i].x();
            para_SpeedBias[i][1] = Vs[i].y();
            para_SpeedBias[i][2] = Vs[i].z();

            para_SpeedBias[i][3] = Bas[i].x();
            para_SpeedBias[i][4] = Bas[i].y();
            para_SpeedBias[i][5] = Bas[i].z();

            para_SpeedBias[i][6] = Bgs[i].x();
            para_SpeedBias[i][7] = Bgs[i].y();
            para_SpeedBias[i][8] = Bgs[i].z();
        }
    }

    for (int i = 0; i < NUM_OF_CAM; i++)
    {
        para_Ex_Pose[i][0] = tic[i].x();
        para_Ex_Pose[i][1] = tic[i].y();
        para_Ex_Pose[i][2] = tic[i].z();
        Quaterniond q{ric[i]};
        para_Ex_Pose[i][3] = q.x();
        para_Ex_Pose[i][4] = q.y();
        para_Ex_Pose[i][5] = q.z();
        para_Ex_Pose[i][6] = q.w();
    }


    VectorXd dep = f_manager.getDepthVector();
    for (int i = 0; i < f_manager.getFeatureCount(); i++)
        para_Feature[i][0] = dep(i);

    para_Td[0][0] = td;
}

void Estimator::double2vector()
{
    Vector3d origin_R0 = Utility::R2ypr(Rs[0]);
    Vector3d origin_P0 = Ps[0];

    if (failure_occur)
    {
        origin_R0 = Utility::R2ypr(last_R0);
        origin_P0 = last_P0;
        failure_occur = 0;
    }

    if(USE_IMU)
    {
        Vector3d origin_R00 = Utility::R2ypr(Quaterniond(para_Pose[0][6],
                                                          para_Pose[0][3],
                                                          para_Pose[0][4],
                                                          para_Pose[0][5]).toRotationMatrix());
        double y_diff = origin_R0.x() - origin_R00.x();
        //TODO
        Matrix3d rot_diff = Utility::ypr2R(Vector3d(y_diff, 0, 0));
        if (abs(abs(origin_R0.y()) - 90) < 1.0 || abs(abs(origin_R00.y()) - 90) < 1.0)
        {
            ROS_DEBUG("euler singular point!");
            rot_diff = Rs[0] * Quaterniond(para_Pose[0][6],
                                           para_Pose[0][3],
                                           para_Pose[0][4],
                                           para_Pose[0][5]).toRotationMatrix().transpose();
        }

        for (int i = 0; i <= WINDOW_SIZE; i++)
        {

            Rs[i] = rot_diff * Quaterniond(para_Pose[i][6], para_Pose[i][3], para_Pose[i][4], para_Pose[i][5]).normalized().toRotationMatrix();
            
            Ps[i] = rot_diff * Vector3d(para_Pose[i][0] - para_Pose[0][0],
                                    para_Pose[i][1] - para_Pose[0][1],
                                    para_Pose[i][2] - para_Pose[0][2]) + origin_P0;


                Vs[i] = rot_diff * Vector3d(para_SpeedBias[i][0],
                                            para_SpeedBias[i][1],
                                            para_SpeedBias[i][2]);

                // CARLA fix-bias (experimental, env REL_FIX_IMU_BIAS=1, default OFF): synth IMU from GT has TRUE
                // bias 0 -> pin Bas/Bgs to 0 so VINS init cannot mis-estimate gravity-into-bias (the CARLA failure).
                static int FIX_BIAS = []{ const char* e=std::getenv("REL_FIX_IMU_BIAS"); return (e && std::string(e)=="1")?1:0; }();
                if (FIX_BIAS) { Bas[i].setZero(); Bgs[i].setZero(); }
                else {
                Bas[i] = Vector3d(para_SpeedBias[i][3],
                                  para_SpeedBias[i][4],
                                  para_SpeedBias[i][5]);

                Bgs[i] = Vector3d(para_SpeedBias[i][6],
                                  para_SpeedBias[i][7],
                                  para_SpeedBias[i][8]);
                }
            
        }
    }
    else
    {
        for (int i = 0; i <= WINDOW_SIZE; i++)
        {
            Rs[i] = Quaterniond(para_Pose[i][6], para_Pose[i][3], para_Pose[i][4], para_Pose[i][5]).normalized().toRotationMatrix();
            
            Ps[i] = Vector3d(para_Pose[i][0], para_Pose[i][1], para_Pose[i][2]);
        }
    }

    if(USE_IMU)
    {
        for (int i = 0; i < NUM_OF_CAM; i++)
        {
            tic[i] = Vector3d(para_Ex_Pose[i][0],
                              para_Ex_Pose[i][1],
                              para_Ex_Pose[i][2]);
            ric[i] = Quaterniond(para_Ex_Pose[i][6],
                                 para_Ex_Pose[i][3],
                                 para_Ex_Pose[i][4],
                                 para_Ex_Pose[i][5]).normalized().toRotationMatrix();
        }
    }

    VectorXd dep = f_manager.getDepthVector();
    for (int i = 0; i < f_manager.getFeatureCount(); i++)
        dep(i) = para_Feature[i][0];
    f_manager.setDepth(dep);

    if(USE_IMU)
        td = para_Td[0][0];

}

bool Estimator::failureDetection()
{
    // ---- failure-detection diagnostic (DEBUG ONLY; print-only, no logic change) ----
    // Gated by env DEBUG_FAILDET=1. Prints every candidate trigger + state-norm context so we can
    // see WHICH condition fires and the correction magnitude when adaptive_floor un-freezes the solver.
    {
        static const bool DBG_FAILDET = (std::getenv("DEBUG_FAILDET") &&
                                         std::string(std::getenv("DEBUG_FAILDET")) == "1");
        if (DBG_FAILDET)
        {
            static long fd_call = 0; ++fd_call;
            const Eigen::Vector3d &P = Ps[WINDOW_SIZE];
            const double dP   = (P - last_P).norm();
            const double dz   = std::fabs(P.z() - last_P.z());
            Eigen::Matrix3d dR = Rs[WINDOW_SIZE].transpose() * last_R;
            Eigen::Quaterniond dQ(dR);
            const double dAngle = std::acos(std::min(1.0, std::fabs(dQ.w()))) * 2.0 / 3.14 * 180.0;
            const double bas = Bas[WINDOW_SIZE].norm();
            const double bgs = Bgs[WINDOW_SIZE].norm();
            const bool t_bas  = bas > 2.5;     // ACTIVE trigger
            const bool t_bgs  = bgs > 1.0;     // ACTIVE trigger
            const bool t_dP   = dP > 5.0;      // (commented-out in stock logic)
            const bool t_dz   = dz > 1.0;      // (commented-out)
            const bool t_ang  = dAngle > 50.0; // (commented-out)
            const bool t_feat = f_manager.last_track_num < 2; // (commented-out)
            const bool would_return_true = t_bas || t_bgs;    // matches ACTIVE logic
            ROS_INFO("[DBG_FAILDET] ts=%.6f call=%ld last_track=%d "
                     "Ps=%.4f Vs=%.4f Bas=%.5f Bgs=%.6f dP=%.4f dz=%.4f dAngle=%.3f "
                     "trig_bas=%d trig_bgs=%d trig_dP=%d trig_dz=%d trig_angle=%d trig_feat=%d would_return_true=%d",
                     Headers[WINDOW_SIZE], fd_call, f_manager.last_track_num,
                     P.norm(), Vs[WINDOW_SIZE].norm(), bas, bgs, dP, dz, dAngle,
                     t_bas?1:0, t_bgs?1:0, t_dP?1:0, t_dz?1:0, t_ang?1:0, t_feat?1:0, would_return_true?1:0);
        }
    }

    if (f_manager.last_track_num < 2)
    {
        ROS_INFO(" little feature %d", f_manager.last_track_num);
        //return true;
    }
    if (Bas[WINDOW_SIZE].norm() > 2.5)
    {
        ROS_INFO(" big IMU acc bias estimation %f", Bas[WINDOW_SIZE].norm());
        return true;
    }
    if (Bgs[WINDOW_SIZE].norm() > 1.0)
    {
        ROS_INFO(" big IMU gyr bias estimation %f", Bgs[WINDOW_SIZE].norm());
        return true;
    }
    /*
    if (tic(0) > 1)
    {
        ROS_INFO(" big extri param estimation %d", tic(0) > 1);
        return true;
    }
    */
    Vector3d tmp_P = Ps[WINDOW_SIZE];
    if ((tmp_P - last_P).norm() > 5)
    {
        //ROS_INFO(" big translation");
        //return true;
    }
    if (abs(tmp_P.z() - last_P.z()) > 1)
    {
        //ROS_INFO(" big z translation");
        //return true; 
    }
    Matrix3d tmp_R = Rs[WINDOW_SIZE];
    Matrix3d delta_R = tmp_R.transpose() * last_R;
    Quaterniond delta_Q(delta_R);
    double delta_angle;
    delta_angle = acos(delta_Q.w()) * 2.0 / 3.14 * 180.0;
    if (delta_angle > 50)
    {
        ROS_INFO(" big delta_angle ");
        //return true;
    }
    return false;
}

void Estimator::optimization()
{
    TicToc t_whole, t_prepare;
    vector2double();

    // P1-Reliability R3b: compute per-feature reliability weights (default OFF; no-op when disabled).
    computeFeatureReliability();
    auto applyRel = [&](auto *fac, int fid) {
        if (!FEATURE_RELIABILITY_ENABLE) return;
        auto it = feat_weight_cur_.find(fid);
        if (it != feat_weight_cur_.end()) fac->feat_weight_ = it->second;
    };

    ceres::Problem problem;
    ceres::LossFunction *loss_function;
    //loss_function = NULL;
    loss_function = new ceres::HuberLoss(1.0);
    //loss_function = new ceres::CauchyLoss(1.0 / FOCAL_LENGTH);
    //ceres::LossFunction* loss_function = new ceres::HuberLoss(1.0);

    // ===== env-controlled stereo-backend diagnostics + knobs (DEBUG ONLY) =====
    // VINS_STEREO_DIAG=1                 -> print per-optimization stereo diagnostics
    // VINS_STEREO_SQRT_SCALE=<float>     -> scale ONLY stereo two-cam factor sqrt_info (mono untouched)
    // VINS_STEREO_NO_ROBUST_FIRST_N=<n>  -> first n optimization keyframes: drop Huber on stereo factors only
    // (alpha=1 in these CARLA runs, so the stereo sqrt baseline is FOCAL_LENGTH/1.5.)
    static const bool   STEREO_DIAG = (std::getenv("VINS_STEREO_DIAG") &&
                                       std::string(std::getenv("VINS_STEREO_DIAG")) == "1");
    static const double STEREO_SQRT_SCALE = (std::getenv("VINS_STEREO_SQRT_SCALE") ?
                                             atof(std::getenv("VINS_STEREO_SQRT_SCALE")) : 1.0);
    static const int    STEREO_NOROBUST_N = (std::getenv("VINS_STEREO_NO_ROBUST_FIRST_N") ?
                                             atoi(std::getenv("VINS_STEREO_NO_ROBUST_FIRST_N")) : 0);
    static int stereo_opt_call = 0;
    ++stereo_opt_call;
    if (STEREO_SQRT_SCALE != 1.0) {
        const Eigen::Matrix2d ss = STEREO_SQRT_SCALE * (FOCAL_LENGTH / 1.5) * Eigen::Matrix2d::Identity();
        ProjectionTwoFrameTwoCamFactor::sqrt_info = ss;   // two-frame two-cam stereo
        ProjectionOneFrameTwoCamFactor::sqrt_info = ss;   // one-frame two-cam stereo
    }
    // ----- backend-factor isolation debug flags (DEBUG ONLY; default = stock behavior) -----
    // DEBUG_DISABLE_MARG_PRIOR=1        -> skip the marginalization prior residual block
    // DEBUG_DISABLE_IMU_FACTOR=1        -> skip all IMU pre-integration factors
    // DEBUG_DISABLE_STEREO_ROBUST_LOSS=1-> NULL loss on ALL stereo two-cam factors (no Huber)
    // DEBUG_STEREO_WEIGHT_SCALE=<float> -> scale stereo two-cam sqrt_info (alias of STEREO_SQRT_SCALE)
    // These are diagnostic switches to locate the 1e46/iters=1 degeneracy. NOT a production fix.
    static const bool DBG_DISABLE_MARG = (std::getenv("DEBUG_DISABLE_MARG_PRIOR") &&
                                          std::string(std::getenv("DEBUG_DISABLE_MARG_PRIOR")) == "1");
    static const bool DBG_DISABLE_IMU  = (std::getenv("DEBUG_DISABLE_IMU_FACTOR") &&
                                          std::string(std::getenv("DEBUG_DISABLE_IMU_FACTOR")) == "1");
    static const bool DBG_DISABLE_STEREO_ROBUST = (std::getenv("DEBUG_DISABLE_STEREO_ROBUST_LOSS") &&
                                          std::string(std::getenv("DEBUG_DISABLE_STEREO_ROBUST_LOSS")) == "1");
    static const double DBG_STEREO_WSCALE = (std::getenv("DEBUG_STEREO_WEIGHT_SCALE") ?
                                          atof(std::getenv("DEBUG_STEREO_WEIGHT_SCALE")) : 1.0);
    static const bool DBG_FACTORS = (STEREO_DIAG ||
                                     (std::getenv("DEBUG_FACTORS") && std::string(std::getenv("DEBUG_FACTORS")) == "1"));
    static const bool DBG_IMU_NUMERIC = (std::getenv("DEBUG_IMU_NUMERIC") &&
                                         std::string(std::getenv("DEBUG_IMU_NUMERIC")) == "1");
    static const int  DBG_NUMERIC_EVERY_N = (std::getenv("DEBUG_NUMERIC_EVERY_N") ?
                                             std::max(1, atoi(std::getenv("DEBUG_NUMERIC_EVERY_N"))) : 20);
    const bool dbg_numeric_now = DBG_IMU_NUMERIC &&
                                 (stereo_opt_call <= 5 || stereo_opt_call % DBG_NUMERIC_EVERY_N == 0);
    if (DBG_STEREO_WSCALE != 1.0) {
        const Eigen::Matrix2d ss = DBG_STEREO_WSCALE * (FOCAL_LENGTH / 1.5) * Eigen::Matrix2d::Identity();
        ProjectionTwoFrameTwoCamFactor::sqrt_info = ss;
        ProjectionOneFrameTwoCamFactor::sqrt_info = ss;
    }

    const bool stereo_robust_off = (stereo_opt_call <= STEREO_NOROBUST_N) || DBG_DISABLE_STEREO_ROBUST;
    ceres::LossFunction *stereo_loss = stereo_robust_off ? NULL : loss_function;
    int dbg_mono = 0, dbg_twocam = 0, dbg_onecam2 = 0, dbg_imu = 0, dbg_marg = 0;
    std::vector<ceres::ResidualBlockId> dbg_mono_ids, dbg_stereo_ids;
    std::vector<double> dbg_depths;
    // ==========================================================================

    for (int i = 0; i < frame_count + 1; i++)
    {
        ceres::LocalParameterization *local_parameterization = new PoseLocalParameterization();
        problem.AddParameterBlock(para_Pose[i], SIZE_POSE, local_parameterization);
        if(USE_IMU)
            problem.AddParameterBlock(para_SpeedBias[i], SIZE_SPEEDBIAS);
    }
    if(!USE_IMU)
        problem.SetParameterBlockConstant(para_Pose[0]);

    for (int i = 0; i < NUM_OF_CAM; i++)
    {
        ceres::LocalParameterization *local_parameterization = new PoseLocalParameterization();
        problem.AddParameterBlock(para_Ex_Pose[i], SIZE_POSE, local_parameterization);
        if ((ESTIMATE_EXTRINSIC && frame_count == WINDOW_SIZE && Vs[0].norm() > 0.2) || openExEstimation)
        {
            //ROS_INFO("estimate extinsic param");
            openExEstimation = 1;
        }
        else
        {
            //ROS_INFO("fix extinsic param");
            problem.SetParameterBlockConstant(para_Ex_Pose[i]);
        }
    }
    problem.AddParameterBlock(para_Td[0], 1);

    if (!ESTIMATE_TD || Vs[0].norm() < 0.2)
        problem.SetParameterBlockConstant(para_Td[0]);

    if (last_marginalization_info && last_marginalization_info->valid && !DBG_DISABLE_MARG)
    {
        // construct new marginlization_factor
        MarginalizationFactor *marginalization_factor = new MarginalizationFactor(last_marginalization_info);
        problem.AddResidualBlock(marginalization_factor, NULL,
                                 last_marginalization_parameter_blocks);
        ++dbg_marg;
    }
    if(USE_IMU && !DBG_DISABLE_IMU)
    {
        for (int i = 0; i < frame_count; i++)
        {
            int j = i + 1;
            if (pre_integrations[j]->sum_dt > 10.0)
                continue;
            IMUFactor* imu_factor = new IMUFactor(pre_integrations[j]);
            problem.AddResidualBlock(imu_factor, NULL, para_Pose[i], para_SpeedBias[i], para_Pose[j], para_SpeedBias[j]);
            ++dbg_imu;
            // ---- IMU preintegration numeric diagnostic (DEBUG ONLY, print-only) ----
            if (dbg_numeric_now)
            {
                const Eigen::Matrix<double, 15, 15> &C = pre_integrations[j]->covariance;
                Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double, 15, 15>> es(C, Eigen::EigenvaluesOnly);
                const double ev_min = es.eigenvalues().minCoeff();
                const double ev_max = es.eigenvalues().maxCoeff();
                const double dmin = C.diagonal().minCoeff();
                const double dmax = C.diagonal().maxCoeff();
                const double sqrt_max = (ev_min > 0.0) ? std::sqrt(1.0 / ev_min) : -1.0;   // largest sqrt_info singular value
                const double sqrt_min = (ev_max > 0.0) ? std::sqrt(1.0 / ev_max) : -1.0;
                ROS_INFO("[DBG_IMU_PREINT] ts=%.6f opt_call=%d i=%d j=%d sum_dt=%.4f acc_n=%.4f gyr_n=%.4f acc_w=%.5f gyr_w=%.6f "
                         "cov_min_eig=%.6e cov_max_eig=%.6e cov_cond=%.6e cov_diag_min=%.6e cov_diag_max=%.6e "
                         "sqrt_info_min=%.6e sqrt_info_max=%.6e sqrt_info_cond=%.6e dp=%.4f dv=%.4f dq=%.6f",
                         Headers[WINDOW_SIZE], stereo_opt_call, i, j, pre_integrations[j]->sum_dt,
                         ACC_N, GYR_N, ACC_W, GYR_W,
                         ev_min, ev_max, (ev_min > 0 ? ev_max / ev_min : -1.0), dmin, dmax,
                         sqrt_min, sqrt_max, (sqrt_min > 0 ? sqrt_max / sqrt_min : -1.0),
                         pre_integrations[j]->delta_p.norm(), pre_integrations[j]->delta_v.norm(),
                         2.0 * std::acos(std::min(1.0, std::fabs(pre_integrations[j]->delta_q.w()))));
            }
        }
    }

    // ===== P1 (fwvio) explicit FOG / wheel / soft-NHC factors — DEFAULT OFF =====
    // flags-off (default) => none of this executes => baseline bit-invariance. Data buffers are
    // filled by the player->estimator plumbing (P1 Task 2); empty-buffer guard makes flag-ON a safe
    // no-op until then. Inserted between adjacent keyframes (i, j=i+1), same locus as IMUFactor.
    {
        const double NHC_SIGMA_MS = 0.3;         // pre-registered soft-NHC sigma (0.3 m/s)
        // FOG explicit factor: switch retained but NOT plumbed in this branch (separate brief). No-op when off.
        if (FOG_FACTOR_ENABLE) {
            // FOG plumbing not implemented in the p1-wheel branch (separate brief). No-op.
        }
        if (WHEEL_FACTOR_ENABLE && WHEEL_MODE_SE2) {
            // SE(2) wheel factor on the immutable preintegration (C3). Translation rows primary; yaw inflated loose.
            int wf_cnt = 0, wf_invalid = 0, wf_huber = 0;
            std::vector<double> rx, ry, ryaw, nx, ny;
            for (int i = 0; i < frame_count; i++) {
                int j = i + 1;
                WheelPreintegration *wp = wheel_pre_integrations[j];
                if (!wp || !wp->valid) { wf_invalid++; continue; }
                Eigen::Matrix3d cov = wp->cov;
                cov(2,2) *= (wheel_yaw_scale_ * wheel_yaw_scale_);     // loosen yaw row
                cov += 1e-9 * Eigen::Matrix3d::Identity();             // PD floor
                Eigen::Matrix3d sqrt_info = Eigen::LLT<Eigen::Matrix3d>(cov.inverse()).matrixL().transpose();
                problem.AddResidualBlock(WheelSE2Functor::Create(wp->dx, wp->dy, wp->dtheta, sqrt_info),
                                         new ceres::HuberLoss(wheel_huber_), para_Pose[i], para_Pose[j]);
                wf_cnt++;
                // raw per-axis residual at current state (diagnostic)
                Eigen::Vector3d dp = Rs[i].transpose() * (Ps[j] - Ps[i]);
                double pth = Utility::R2ypr(Rs[i].transpose() * Rs[j]).x() * M_PI / 180.0;
                double cw = std::cos(wp->dtheta), sw = std::sin(wp->dtheta);
                double ex =  cw*(dp.x()-wp->dx) + sw*(dp.y()-wp->dy);
                double ey = -sw*(dp.x()-wp->dx) + cw*(dp.y()-wp->dy);
                rx.push_back(std::fabs(ex)); ry.push_back(std::fabs(ey)); ryaw.push_back(std::fabs(pth-wp->dtheta));
                double n = (sqrt_info * Eigen::Vector3d(ex,ey,pth-wp->dtheta)).norm();
                nx.push_back(n); if (n > wheel_huber_) wf_huber++;
            }
            auto med=[](std::vector<double> v){if(v.empty())return 0.0;std::sort(v.begin(),v.end());return v[v.size()/2];};
            auto p95=[](std::vector<double> v){if(v.empty())return 0.0;std::sort(v.begin(),v.end());return v[(size_t)(0.95*v.size())];};
            ROS_WARN("[WHEEL] se2 factors=%d invalid=%d huber_hit=%d rawx_med=%.4f rawy_med=%.4f rawyaw_med=%.4f norm_med=%.3f norm_p95=%.3f",
                     wf_cnt, wf_invalid, wf_huber, med(rx), med(ry), med(ryaw), med(nx), p95(nx));
        }
        else if (WHEEL_FACTOR_ENABLE) {   // forward_only ablation (1-D), uses preintegration sum
            int wf_cnt=0, wf_invalid=0; std::vector<double> raw_res;
            const double WHEEL_VAR_1D = 1.0e-3;
            for (int i = 0; i < frame_count; i++) {
                int j = i + 1; WheelPreintegration *wp = wheel_pre_integrations[j];
                if (!wp || !wp->valid) { wf_invalid++; continue; }
                double ds = 0.5*(wp->sum_dl + wp->sum_dr);
                problem.AddResidualBlock(WheelForwardFunctor::Create(ds, WHEEL_VAR_1D), NULL, para_Pose[i], para_Pose[j]);
                wf_cnt++;
                raw_res.push_back(std::fabs((Rs[i].transpose()*(Ps[j]-Ps[i])).x() - ds));
            }
            auto med=[](std::vector<double> v){if(v.empty())return 0.0;std::sort(v.begin(),v.end());return v[v.size()/2];};
            ROS_WARN("[WHEEL] fwd_only factors=%d invalid=%d raw_med=%.4f", wf_cnt, wf_invalid, med(raw_res));
        }
        if (FOG_YAW_ENABLE) {   // FOG yaw factor (1-D, tight -> dominates rotation)
            int ff = 0, finv = 0; std::vector<double> fres;
            for (int i = 0; i < frame_count; i++) {
                int j = i + 1; FogYawPreintegration *fp = fog_yaw_preint[j];
                if (!fp || !fp->valid) { finv++; continue; }
                double var = std::max(fp->var, 1.0e-8);          // PD floor (avoids absurd sqrt_info)
                double sqrt_info = (1.0 / std::sqrt(var)) / std::max(fog_yaw_scale_, 1e-9);
                problem.AddResidualBlock(FogYawFunctor::Create(fp->dpsi, sqrt_info), NULL,
                                         para_Pose[i], para_Pose[j]);
                ff++;
                double yaw_pred = Utility::R2ypr(Rs[i].transpose() * Rs[j]).x() * M_PI / 180.0;
                fres.push_back(std::fabs(yaw_pred - fp->dpsi));
            }
            auto medf = [](std::vector<double> v){ if(v.empty())return 0.0; std::sort(v.begin(),v.end()); return v[v.size()/2]; };
            ROS_WARN("[FOG] yaw factors=%d invalid=%d yaw_resid_med_deg=%.4f", ff, finv, medf(fres)*180.0/M_PI);
        }
        if (NHC_ENABLE && USE_IMU) {
            for (int i = 0; i <= frame_count; i++)
                problem.AddResidualBlock(NhcFunctor::Create(NHC_SIGMA_MS), NULL,
                                         para_Pose[i], para_SpeedBias[i]);
        }
    }

    int f_m_cnt = 0;
    int feature_index = -1;
    for (auto &it_per_id : f_manager.feature)
    {
        it_per_id.used_num = it_per_id.feature_per_frame.size();
        if (it_per_id.used_num < 4)
            continue;
 
        ++feature_index;

        int imu_i = it_per_id.start_frame, imu_j = imu_i - 1;

        Vector3d pts_i = it_per_id.feature_per_frame[0].point;

        if (STEREO_DIAG)   // collect per-feature inverse-depth -> depth (one entry per used feature)
            dbg_depths.push_back(para_Feature[feature_index][0] > 1e-9 ?
                                 1.0 / para_Feature[feature_index][0] : -1.0);

        for (auto &it_per_frame : it_per_id.feature_per_frame)
        {
            imu_j++;
            if (imu_i != imu_j)
            {
                Vector3d pts_j = it_per_frame.point;
                ProjectionTwoFrameOneCamFactor *f_td = new ProjectionTwoFrameOneCamFactor(pts_i, pts_j, it_per_id.feature_per_frame[0].velocity, it_per_frame.velocity,
                                                                 it_per_id.feature_per_frame[0].cur_td, it_per_frame.cur_td);
                applyRel(f_td, it_per_id.feature_id);
                ceres::ResidualBlockId rid_m = problem.AddResidualBlock(f_td, loss_function, para_Pose[imu_i], para_Pose[imu_j], para_Ex_Pose[0], para_Feature[feature_index], para_Td[0]);
                if (STEREO_DIAG) { dbg_mono_ids.push_back(rid_m); ++dbg_mono; }
            }

            if(STEREO && it_per_frame.is_stereo)
            {
                Vector3d pts_j_right = it_per_frame.pointRight;
                if(imu_i != imu_j)
                {
                    ProjectionTwoFrameTwoCamFactor *f = new ProjectionTwoFrameTwoCamFactor(pts_i, pts_j_right, it_per_id.feature_per_frame[0].velocity, it_per_frame.velocityRight,
                                                                 it_per_id.feature_per_frame[0].cur_td, it_per_frame.cur_td);
                    applyRel(f, it_per_id.feature_id);
                    ceres::ResidualBlockId rid_s = problem.AddResidualBlock(f, stereo_loss, para_Pose[imu_i], para_Pose[imu_j], para_Ex_Pose[0], para_Ex_Pose[1], para_Feature[feature_index], para_Td[0]);
                    if (STEREO_DIAG) { dbg_stereo_ids.push_back(rid_s); ++dbg_twocam; }
                }
                else
                {
                    ProjectionOneFrameTwoCamFactor *f = new ProjectionOneFrameTwoCamFactor(pts_i, pts_j_right, it_per_id.feature_per_frame[0].velocity, it_per_frame.velocityRight,
                                                                 it_per_id.feature_per_frame[0].cur_td, it_per_frame.cur_td);
                    applyRel(f, it_per_id.feature_id);
                    ceres::ResidualBlockId rid_o = problem.AddResidualBlock(f, stereo_loss, para_Ex_Pose[0], para_Ex_Pose[1], para_Feature[feature_index], para_Td[0]);
                    if (STEREO_DIAG) { dbg_stereo_ids.push_back(rid_o); ++dbg_onecam2; }
                }

            }
            f_m_cnt++;
        }
    }

    ROS_DEBUG("visual measurement count: %d", f_m_cnt);
    //printf("prepare for ceres: %f \n", t_prepare.toc());

    ceres::Solver::Options options;

    if (USE_GPU_CERES)
        // std::cout << "1" << endl;
        options.dense_linear_algebra_library_type = ceres::CUDA;
    else
        // std::cout << "2" << endl;
        options.linear_solver_type = ceres::DENSE_SCHUR;

    //options.num_threads = 2;
    options.trust_region_strategy_type = ceres::DOGLEG;
    options.max_num_iterations = NUM_ITERATIONS;
    //options.use_explicit_schur_complement = true;
    //options.minimizer_progress_to_stdout = true;
    //options.use_nonmonotonic_steps = true;


    if (marginalization_flag == MARGIN_OLD)
        options.max_solver_time_in_seconds = SOLVER_TIME * 4.0 / 5.0;
    else
        options.max_solver_time_in_seconds = SOLVER_TIME;
    TicToc t_solver;
    ceres::Solver::Summary summary;
    ceres::Solve(options, &problem, &summary);
    //cout << summary.BriefReport() << endl;
    ROS_DEBUG("Iterations : %d", static_cast<int>(summary.iterations.size()));

    // ---- integrity logging: latest-pose covariance (newest keyframe) ----
    // DEFAULT OFF. The DENSE_SVD covariance below is expensive (~120-160 ms/keyframe) and was found to
    // throttle VINS below real-time, truncating runs at playback_rate 3.0. It is only needed to build the
    // pose-covariance dataset for Paper-2 (Sigma_A). Enable with POSE_COV_ENABLE (config `pose_cov_enable:1`
    // or env `SAVE_POSE_COVARIANCE=1`); optionally compute only every POSE_COV_EVERY_N keyframes. When OFF:
    // no ceres::Covariance::Compute, no [pose-cov] print, sentinels stay -1, pose optimization UNCHANGED.
    latest_pose_cov_pos_trace = -1.0;
    latest_pose_cov_rot_trace = -1.0;
    static long pose_cov_diag_counter = 0;
    bool pose_cov_do_this_kf = POSE_COV_ENABLE
        && ((POSE_COV_EVERY_N <= 1) || (pose_cov_diag_counter % POSE_COV_EVERY_N == 0));
    if (POSE_COV_ENABLE) pose_cov_diag_counter++;
    if (pose_cov_do_this_kf)
    {
        ceres::Covariance::Options copts;
        copts.algorithm_type = ceres::DENSE_SVD;   // robust to rank deficiency
        copts.null_space_rank = -1;
        ceres::Covariance cov(copts);
        std::vector<std::pair<const double*, const double*>> cov_blocks;
        cov_blocks.push_back(std::make_pair(
            (const double*)para_Pose[WINDOW_SIZE], (const double*)para_Pose[WINDOW_SIZE]));
        // STABILITY GUARD (stereo-only / early frames): the latest-window pose block is only added to the
        // Ceres problem once the window has filled (frame_count==WINDOW_SIZE). In stereo-only (USE_IMU=0) the
        // optimizer runs from early frames before that, so requesting its covariance hits Ceres FindOrDie
        // (map_util.h "Map key not found"). Skip the diagnostic covariance when the block isn't in the problem.
        // Second guard: if the optimizer has diverged to a non-finite state (NaN/Inf pose — can happen in
        // stereo-only on degenerate/static scenes), ceres::Covariance::Compute on the NaN problem segfaults;
        // skip the diagnostic in that case too. Both are STABILITY-only — no change to estimation logic; the
        // [pose-cov] diagnostic just keeps its sentinel -1 on those frames.
        bool pose_block_finite = true;
        {
            const double* pb = (const double*)para_Pose[WINDOW_SIZE];
            for (int _i = 0; _i < 7; ++_i)
                if (!std::isfinite(pb[_i])) { pose_block_finite = false; break; }
        }
        if (problem.HasParameterBlock((double*)para_Pose[WINDOW_SIZE]) && pose_block_finite
            && cov.Compute(cov_blocks, &problem))
        {
            double C[36];   // 6x6 tangent-space (dims 0-2 translation, 3-5 rotation)
            cov.GetCovarianceBlockInTangentSpace(
                para_Pose[WINDOW_SIZE], para_Pose[WINDOW_SIZE], C);
            latest_pose_cov_pos_trace = C[0] + C[7] + C[14];
            latest_pose_cov_rot_trace = C[21] + C[28] + C[35];
        }
        ROS_INFO("[pose-cov] ts=%.6f pos_trace=%.6e rot_trace=%.6e",
                 Headers[WINDOW_SIZE], latest_pose_cov_pos_trace, latest_pose_cov_rot_trace);
    }

    // ---- integrity logging Tier-1: ceres solver cost/iter summary (same keyframe ts) ----
    {
        double init_cost   = summary.initial_cost;
        double final_cost  = summary.final_cost;
        int    iters       = static_cast<int>(summary.iterations.size());
        int    succ_steps  = summary.num_successful_steps;
        int    unsucc_steps= summary.num_unsuccessful_steps;
        int    termtype    = static_cast<int>(summary.termination_type);
        double grad_norm   = summary.iterations.empty() ? -1.0
                              : summary.iterations.back().gradient_max_norm;
        ROS_INFO("[opt-cost] ts=%.6f init=%.6e final=%.6e iters=%d succ=%d unsucc=%d grad=%.3e term=%d",
                 Headers[WINDOW_SIZE], init_cost, final_cost, iters, succ_steps, unsucc_steps,
                 grad_norm, termtype);
    }
    //printf("solver costs: %f \n", t_solver.toc());

    // ---- stereo-backend diagnostics (DEBUG ONLY; gated by VINS_STEREO_DIAG=1 or DEBUG_FACTORS=1) ----
    if (DBG_FACTORS)
    {
        double cost_mono = 0.0, cost_stereo = 0.0;
        if (!dbg_mono_ids.empty()) {
            ceres::Problem::EvaluateOptions eo; eo.residual_blocks = dbg_mono_ids;
            problem.Evaluate(eo, &cost_mono, nullptr, nullptr, nullptr);
        }
        if (!dbg_stereo_ids.empty()) {
            ceres::Problem::EvaluateOptions eo; eo.residual_blocks = dbg_stereo_ids;
            problem.Evaluate(eo, &cost_stereo, nullptr, nullptr, nullptr);
        }
        double dmin = 1e18, dmax = -1e18, dsum = 0.0; int gd = 0, nd = 0;
        for (double d : dbg_depths) { ++nd; if (d > 0) { ++gd; dmin = std::min(dmin, d); dmax = std::max(dmax, d); dsum += d; } }
        const double dmean = gd > 0 ? dsum / gd : -1.0;
        const int n_stereo = dbg_twocam + dbg_onecam2;
        const double rms_mono   = dbg_mono  > 0 ? std::sqrt(2.0 * cost_mono   / dbg_mono)  : -1.0;
        const double rms_stereo = n_stereo > 0 ? std::sqrt(2.0 * cost_stereo / n_stereo) : -1.0;
        ROS_INFO("[stereo-diag] ts=%.6f opt_call=%d mono=%d twocam=%d onecam2=%d good_depth=%d/%d "
                 "depth_mean=%.3f depth_min=%.3f depth_max=%.3f resblocks=%d parblocks=%d "
                 "stereo_sqrt=%.2f stereo_robust=%d cost_mono=%.4e cost_stereo=%.4e rms_mono=%.3e rms_stereo=%.3e",
                 Headers[WINDOW_SIZE], stereo_opt_call, dbg_mono, dbg_twocam, dbg_onecam2, gd, nd,
                 dmean, (gd > 0 ? dmin : -1.0), (gd > 0 ? dmax : -1.0),
                 problem.NumResidualBlocks(), problem.NumParameterBlocks(),
                 ProjectionTwoFrameTwoCamFactor::sqrt_info(0, 0), stereo_robust_off ? 0 : 1,
                 cost_mono, cost_stereo, rms_mono, rms_stereo);
        // grep-friendly factor / solver / depth breakdown
        ROS_INFO("[DBG_FACTORS] ts=%.6f imu=%d marg=%d stereo2cam=%d onecam2cam=%d mono=%d residual_blocks=%d parameter_blocks=%d "
                 "disable_marg=%d disable_imu=%d stereo_robust=%d stereo_wscale=%.3f",
                 Headers[WINDOW_SIZE], dbg_imu, dbg_marg, dbg_twocam, dbg_onecam2, dbg_mono,
                 problem.NumResidualBlocks(), problem.NumParameterBlocks(),
                 DBG_DISABLE_MARG ? 1 : 0, DBG_DISABLE_IMU ? 1 : 0, stereo_robust_off ? 0 : 1, DBG_STEREO_WSCALE);
        ROS_INFO("[DBG_SOLVER] ts=%.6f init_cost=%.6e final_cost=%.6e iters=%d cost_mono=%.4e cost_stereo=%.4e",
                 Headers[WINDOW_SIZE], summary.initial_cost, summary.final_cost,
                 static_cast<int>(summary.iterations.size()), cost_mono, cost_stereo);
        ROS_INFO("[DBG_DEPTH] ts=%.6f n=%d good=%d mean=%.4f min=%.4f max=%.4f",
                 Headers[WINDOW_SIZE], nd, gd, dmean, (gd > 0 ? dmin : -1.0), (gd > 0 ? dmax : -1.0));
    }

    double2vector();
    //printf("frame_count: %d \n", frame_count);

    // ---- estimate_extrinsic diagnostic (DEBUG ONLY; print-only, no logic change) ----
    // ric[i] = camera-i -> IMU/body rotation (3x3, row-major 9 vals); tic[i] = translation (3 vals).
    // Grep with: grep "\[EST_EXT\]" vins.log
    for (int _c = 0; _c < NUM_OF_CAM; ++_c)
    {
        const Eigen::Matrix3d &Rc = ric[_c];
        const Eigen::Vector3d &Tc = tic[_c];
        ROS_INFO("[EST_EXT] ts=%.6f frame=%d est_ext=%d solver_flag=%d cam=%d "
                 "ric=%.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f tic=%.6f %.6f %.6f",
                 Headers[WINDOW_SIZE], frame_count, ESTIMATE_EXTRINSIC,
                 static_cast<int>(solver_flag), _c,
                 Rc(0,0), Rc(0,1), Rc(0,2), Rc(1,0), Rc(1,1), Rc(1,2), Rc(2,0), Rc(2,1), Rc(2,2),
                 Tc(0), Tc(1), Tc(2));
    }

    if(frame_count < WINDOW_SIZE)
        return;
    
    TicToc t_whole_marginalization;
    if (marginalization_flag == MARGIN_OLD)
    {
        MarginalizationInfo *marginalization_info = new MarginalizationInfo();
        vector2double();

        if (last_marginalization_info && last_marginalization_info->valid)
        {
            vector<int> drop_set;
            for (int i = 0; i < static_cast<int>(last_marginalization_parameter_blocks.size()); i++)
            {
                if (last_marginalization_parameter_blocks[i] == para_Pose[0] ||
                    last_marginalization_parameter_blocks[i] == para_SpeedBias[0])
                    drop_set.push_back(i);
            }
            // construct new marginlization_factor
            MarginalizationFactor *marginalization_factor = new MarginalizationFactor(last_marginalization_info);
            ResidualBlockInfo *residual_block_info = new ResidualBlockInfo(marginalization_factor, NULL,
                                                                           last_marginalization_parameter_blocks,
                                                                           drop_set);
            marginalization_info->addResidualBlockInfo(residual_block_info);
        }

        if(USE_IMU)
        {
            if (pre_integrations[1]->sum_dt < 10.0)
            {
                IMUFactor* imu_factor = new IMUFactor(pre_integrations[1]);
                ResidualBlockInfo *residual_block_info = new ResidualBlockInfo(imu_factor, NULL,
                                                                           vector<double *>{para_Pose[0], para_SpeedBias[0], para_Pose[1], para_SpeedBias[1]},
                                                                           vector<int>{0, 1});
                marginalization_info->addResidualBlockInfo(residual_block_info);
            }
        }

        // P1-Wheel: the 0->1 wheel factor touches the marginalized pose0 -> must enter marg (SAME object, loss).
        if (WHEEL_FACTOR_ENABLE && wheel_pre_integrations[1] && wheel_pre_integrations[1]->valid)
        {
            WheelPreintegration *wp = wheel_pre_integrations[1];
            ceres::CostFunction *cf;
            if (WHEEL_MODE_SE2) {
                Eigen::Matrix3d cov = wp->cov; cov(2,2) *= (wheel_yaw_scale_*wheel_yaw_scale_);
                cov += 1e-9*Eigen::Matrix3d::Identity();
                Eigen::Matrix3d sqrt_info = Eigen::LLT<Eigen::Matrix3d>(cov.inverse()).matrixL().transpose();
                cf = WheelSE2Functor::Create(wp->dx, wp->dy, wp->dtheta, sqrt_info);
            } else {
                cf = WheelForwardFunctor::Create(0.5*(wp->sum_dl+wp->sum_dr), 1.0e-3);
            }
            {
                ResidualBlockInfo *rbi = new ResidualBlockInfo(
                    cf, new ceres::HuberLoss(wheel_huber_),
                    vector<double *>{para_Pose[0], para_Pose[1]}, vector<int>{0});  // drop pose0
                marginalization_info->addResidualBlockInfo(rbi);
            }
        }
        // P1-FogWheel: 0->1 FOG yaw factor touches marginalized pose0 -> must enter marg.
        if (FOG_YAW_ENABLE && fog_yaw_preint[1] && fog_yaw_preint[1]->valid)
        {
            FogYawPreintegration *fp = fog_yaw_preint[1];
            double var = std::max(fp->var, 1.0e-8);
            double sqrt_info = (1.0 / std::sqrt(var)) / std::max(fog_yaw_scale_, 1e-9);
            ResidualBlockInfo *rbi = new ResidualBlockInfo(
                FogYawFunctor::Create(fp->dpsi, sqrt_info), NULL,
                vector<double *>{para_Pose[0], para_Pose[1]}, vector<int>{0});  // drop pose0
            marginalization_info->addResidualBlockInfo(rbi);
        }

        {
            int feature_index = -1;
            for (auto &it_per_id : f_manager.feature)
            {
                it_per_id.used_num = it_per_id.feature_per_frame.size();
                if (it_per_id.used_num < 4)
                    continue;

                ++feature_index;

                int imu_i = it_per_id.start_frame, imu_j = imu_i - 1;
                if (imu_i != 0)
                    continue;

                Vector3d pts_i = it_per_id.feature_per_frame[0].point;

                for (auto &it_per_frame : it_per_id.feature_per_frame)
                {
                    imu_j++;
                    if(imu_i != imu_j)
                    {
                        Vector3d pts_j = it_per_frame.point;
                        ProjectionTwoFrameOneCamFactor *f_td = new ProjectionTwoFrameOneCamFactor(pts_i, pts_j, it_per_id.feature_per_frame[0].velocity, it_per_frame.velocity,
                                                                          it_per_id.feature_per_frame[0].cur_td, it_per_frame.cur_td);
                        applyRel(f_td, it_per_id.feature_id);
                        ResidualBlockInfo *residual_block_info = new ResidualBlockInfo(f_td, loss_function,
                                                                                        vector<double *>{para_Pose[imu_i], para_Pose[imu_j], para_Ex_Pose[0], para_Feature[feature_index], para_Td[0]},
                                                                                        vector<int>{0, 3});
                        marginalization_info->addResidualBlockInfo(residual_block_info);
                    }
                    if(STEREO && it_per_frame.is_stereo)
                    {
                        Vector3d pts_j_right = it_per_frame.pointRight;
                        if(imu_i != imu_j)
                        {
                            ProjectionTwoFrameTwoCamFactor *f = new ProjectionTwoFrameTwoCamFactor(pts_i, pts_j_right, it_per_id.feature_per_frame[0].velocity, it_per_frame.velocityRight,
                                                                          it_per_id.feature_per_frame[0].cur_td, it_per_frame.cur_td);
                            applyRel(f, it_per_id.feature_id);
                            ResidualBlockInfo *residual_block_info = new ResidualBlockInfo(f, stereo_loss,
                                                                                           vector<double *>{para_Pose[imu_i], para_Pose[imu_j], para_Ex_Pose[0], para_Ex_Pose[1], para_Feature[feature_index], para_Td[0]},
                                                                                           vector<int>{0, 4});
                            marginalization_info->addResidualBlockInfo(residual_block_info);
                        }
                        else
                        {
                            ProjectionOneFrameTwoCamFactor *f = new ProjectionOneFrameTwoCamFactor(pts_i, pts_j_right, it_per_id.feature_per_frame[0].velocity, it_per_frame.velocityRight,
                                                                          it_per_id.feature_per_frame[0].cur_td, it_per_frame.cur_td);
                            applyRel(f, it_per_id.feature_id);
                            ResidualBlockInfo *residual_block_info = new ResidualBlockInfo(f, stereo_loss,
                                                                                           vector<double *>{para_Ex_Pose[0], para_Ex_Pose[1], para_Feature[feature_index], para_Td[0]},
                                                                                           vector<int>{2});
                            marginalization_info->addResidualBlockInfo(residual_block_info);
                        }
                    }
                }
            }
        }

        TicToc t_pre_margin;
        marginalization_info->preMarginalize();
        ROS_DEBUG("pre marginalization %f ms", t_pre_margin.toc());
        
        TicToc t_margin;
        marginalization_info->marginalize();
        ROS_DEBUG("marginalization %f ms", t_margin.toc());

        std::unordered_map<long, double *> addr_shift;
        for (int i = 1; i <= WINDOW_SIZE; i++)
        {
            addr_shift[reinterpret_cast<long>(para_Pose[i])] = para_Pose[i - 1];
            if(USE_IMU)
                addr_shift[reinterpret_cast<long>(para_SpeedBias[i])] = para_SpeedBias[i - 1];
        }
        for (int i = 0; i < NUM_OF_CAM; i++)
            addr_shift[reinterpret_cast<long>(para_Ex_Pose[i])] = para_Ex_Pose[i];

        addr_shift[reinterpret_cast<long>(para_Td[0])] = para_Td[0];

        vector<double *> parameter_blocks = marginalization_info->getParameterBlocks(addr_shift);

        if (last_marginalization_info)
        {
            delete last_marginalization_info;
            last_marginalization_info = nullptr;
        }
        last_marginalization_info = marginalization_info;
        last_marginalization_parameter_blocks = parameter_blocks;
        
    }
    else
    {
        if (last_marginalization_info &&
            std::count(std::begin(last_marginalization_parameter_blocks), std::end(last_marginalization_parameter_blocks), para_Pose[WINDOW_SIZE - 1]))
        {

            MarginalizationInfo *marginalization_info = new MarginalizationInfo();
            vector2double();
            if (last_marginalization_info && last_marginalization_info->valid)
            {
                vector<int> drop_set;
                for (int i = 0; i < static_cast<int>(last_marginalization_parameter_blocks.size()); i++)
                {
                    assert(last_marginalization_parameter_blocks[i] != para_SpeedBias[WINDOW_SIZE - 1]);
                    if (last_marginalization_parameter_blocks[i] == para_Pose[WINDOW_SIZE - 1])
                        drop_set.push_back(i);
                }
                // construct new marginlization_factor
                MarginalizationFactor *marginalization_factor = new MarginalizationFactor(last_marginalization_info);
                ResidualBlockInfo *residual_block_info = new ResidualBlockInfo(marginalization_factor, NULL,
                                                                               last_marginalization_parameter_blocks,
                                                                               drop_set);

                marginalization_info->addResidualBlockInfo(residual_block_info);
            }

            TicToc t_pre_margin;
            ROS_DEBUG("begin marginalization");
            marginalization_info->preMarginalize();
            ROS_DEBUG("end pre marginalization, %f ms", t_pre_margin.toc());

            TicToc t_margin;
            ROS_DEBUG("begin marginalization");
            marginalization_info->marginalize();
            ROS_DEBUG("end marginalization, %f ms", t_margin.toc());
            
            std::unordered_map<long, double *> addr_shift;
            for (int i = 0; i <= WINDOW_SIZE; i++)
            {
                if (i == WINDOW_SIZE - 1)
                    continue;
                else if (i == WINDOW_SIZE)
                {
                    addr_shift[reinterpret_cast<long>(para_Pose[i])] = para_Pose[i - 1];
                    if(USE_IMU)
                        addr_shift[reinterpret_cast<long>(para_SpeedBias[i])] = para_SpeedBias[i - 1];
                }
                else
                {
                    addr_shift[reinterpret_cast<long>(para_Pose[i])] = para_Pose[i];
                    if(USE_IMU)
                        addr_shift[reinterpret_cast<long>(para_SpeedBias[i])] = para_SpeedBias[i];
                }
            }
            for (int i = 0; i < NUM_OF_CAM; i++)
                addr_shift[reinterpret_cast<long>(para_Ex_Pose[i])] = para_Ex_Pose[i];

            addr_shift[reinterpret_cast<long>(para_Td[0])] = para_Td[0];

            
            vector<double *> parameter_blocks = marginalization_info->getParameterBlocks(addr_shift);
            if (last_marginalization_info)
            {
                delete last_marginalization_info;
                last_marginalization_info = nullptr;
            }
            last_marginalization_info = marginalization_info;
            last_marginalization_parameter_blocks = parameter_blocks;
            
        }
    }
    //printf("whole marginalization costs: %f \n", t_whole_marginalization.toc());
    //printf("whole time for ceres: %f \n", t_whole.toc());
}

void Estimator::slideWindow()
{
    TicToc t_margin;
    if (marginalization_flag == MARGIN_OLD)
    {
        double t_0 = Headers[0];
        back_R0 = Rs[0];
        back_P0 = Ps[0];
        if (frame_count == WINDOW_SIZE)
        {
            for (int i = 0; i < WINDOW_SIZE; i++)
            {
                Headers[i] = Headers[i + 1];
                Rs[i].swap(Rs[i + 1]);
                Ps[i].swap(Ps[i + 1]);
                if(USE_IMU)
                {
                    std::swap(pre_integrations[i], pre_integrations[i + 1]);
                    if (WHEEL_FACTOR_ENABLE || WHEEL_REFERENCE_ONLY) std::swap(wheel_pre_integrations[i], wheel_pre_integrations[i + 1]);  // P1-Wheel
                    if (FOG_YAW_ENABLE || FOG_YAW_REFERENCE_ONLY) std::swap(fog_yaw_preint[i], fog_yaw_preint[i + 1]);  // P1-FogWheel

                    dt_buf[i].swap(dt_buf[i + 1]);
                    linear_acceleration_buf[i].swap(linear_acceleration_buf[i + 1]);
                    angular_velocity_buf[i].swap(angular_velocity_buf[i + 1]);

                    Vs[i].swap(Vs[i + 1]);
                    Bas[i].swap(Bas[i + 1]);
                    Bgs[i].swap(Bgs[i + 1]);
                }
            }
            Headers[WINDOW_SIZE] = Headers[WINDOW_SIZE - 1];
            Ps[WINDOW_SIZE] = Ps[WINDOW_SIZE - 1];
            Rs[WINDOW_SIZE] = Rs[WINDOW_SIZE - 1];

            if(USE_IMU)
            {
                Vs[WINDOW_SIZE] = Vs[WINDOW_SIZE - 1];
                Bas[WINDOW_SIZE] = Bas[WINDOW_SIZE - 1];
                Bgs[WINDOW_SIZE] = Bgs[WINDOW_SIZE - 1];

                delete pre_integrations[WINDOW_SIZE];
                pre_integrations[WINDOW_SIZE] = nullptr;
                pre_integrations[WINDOW_SIZE] = new IntegrationBase{acc_0, gyr_0, Bas[WINDOW_SIZE], Bgs[WINDOW_SIZE]};

                dt_buf[WINDOW_SIZE].clear();
                linear_acceleration_buf[WINDOW_SIZE].clear();
                angular_velocity_buf[WINDOW_SIZE].clear();
            }
            if (WHEEL_FACTOR_ENABLE || WHEEL_REFERENCE_ONLY) { delete wheel_pre_integrations[WINDOW_SIZE]; wheel_pre_integrations[WINDOW_SIZE] = nullptr; }  // P1-Wheel
            if (FOG_YAW_ENABLE || FOG_YAW_REFERENCE_ONLY) { delete fog_yaw_preint[WINDOW_SIZE]; fog_yaw_preint[WINDOW_SIZE] = nullptr; }  // P1-FogWheel

            if (true || solver_flag == INITIAL)
            {
                map<double, ImageFrame>::iterator it_0;
                it_0 = all_image_frame.find(t_0);
                delete it_0->second.pre_integration;
                it_0->second.pre_integration = nullptr;
                all_image_frame.erase(all_image_frame.begin(), it_0);
            }
            slideWindowOld();
        }
    }
    else
    {
        if (frame_count == WINDOW_SIZE)
        {
            Headers[frame_count - 1] = Headers[frame_count];
            Ps[frame_count - 1] = Ps[frame_count];
            Rs[frame_count - 1] = Rs[frame_count];

            // P1-Wheel v3.3 C2: MARGIN_SECOND_NEW two-segment SE(2) composition (mirror of IMU push_back below).
            if ((WHEEL_FACTOR_ENABLE || WHEEL_REFERENCE_ONLY) && wheel_pre_integrations[frame_count - 1] && wheel_pre_integrations[frame_count]) {
                wheel_pre_integrations[frame_count - 1]->merge(*wheel_pre_integrations[frame_count]);
                delete wheel_pre_integrations[frame_count]; wheel_pre_integrations[frame_count] = nullptr;
            }
            if ((FOG_YAW_ENABLE || FOG_YAW_REFERENCE_ONLY) && fog_yaw_preint[frame_count - 1] && fog_yaw_preint[frame_count]) {
                fog_yaw_preint[frame_count - 1]->merge(*fog_yaw_preint[frame_count]);
                delete fog_yaw_preint[frame_count]; fog_yaw_preint[frame_count] = nullptr;
            }

            if(USE_IMU)
            {
                for (unsigned int i = 0; i < dt_buf[frame_count].size(); i++)
                {
                    double tmp_dt = dt_buf[frame_count][i];
                    Vector3d tmp_linear_acceleration = linear_acceleration_buf[frame_count][i];
                    Vector3d tmp_angular_velocity = angular_velocity_buf[frame_count][i];

                    pre_integrations[frame_count - 1]->push_back(tmp_dt, tmp_linear_acceleration, tmp_angular_velocity);

                    dt_buf[frame_count - 1].push_back(tmp_dt);
                    linear_acceleration_buf[frame_count - 1].push_back(tmp_linear_acceleration);
                    angular_velocity_buf[frame_count - 1].push_back(tmp_angular_velocity);
                }

                Vs[frame_count - 1] = Vs[frame_count];
                Bas[frame_count - 1] = Bas[frame_count];
                Bgs[frame_count - 1] = Bgs[frame_count];

                delete pre_integrations[WINDOW_SIZE];
                pre_integrations[WINDOW_SIZE] = nullptr;
                pre_integrations[WINDOW_SIZE] = new IntegrationBase{acc_0, gyr_0, Bas[WINDOW_SIZE], Bgs[WINDOW_SIZE]};

                dt_buf[WINDOW_SIZE].clear();
                linear_acceleration_buf[WINDOW_SIZE].clear();
                angular_velocity_buf[WINDOW_SIZE].clear();
            }
            slideWindowNew();
        }
    }
}

void Estimator::slideWindowNew()
{
    sum_of_front++;
    f_manager.removeFront(frame_count);
}

void Estimator::slideWindowOld()
{
    sum_of_back++;

    bool shift_depth = solver_flag == NON_LINEAR ? true : false;
    if (shift_depth)
    {
        Matrix3d R0, R1;
        Vector3d P0, P1;
        R0 = back_R0 * ric[0];
        R1 = Rs[0] * ric[0];
        P0 = back_P0 + back_R0 * tic[0];
        P1 = Ps[0] + Rs[0] * tic[0];
        f_manager.removeBackShiftDepth(R0, P0, R1, P1);
    }
    else
        f_manager.removeBack();
}


void Estimator::getPoseInWorldFrame(Eigen::Matrix4d &T)
{
    T = Eigen::Matrix4d::Identity();
    T.block<3, 3>(0, 0) = Rs[frame_count];
    T.block<3, 1>(0, 3) = Ps[frame_count];
}

void Estimator::getPoseInWorldFrame(int index, Eigen::Matrix4d &T)
{
    T = Eigen::Matrix4d::Identity();
    T.block<3, 3>(0, 0) = Rs[index];
    T.block<3, 1>(0, 3) = Ps[index];
}

void Estimator::predictPtsInNextFrame()
{
    //printf("predict pts in next frame\n");
    if(frame_count < 2)
        return;
    // predict next pose. Assume constant velocity motion
    Eigen::Matrix4d curT, prevT, nextT;
    getPoseInWorldFrame(curT);
    getPoseInWorldFrame(frame_count - 1, prevT);
    nextT = curT * (prevT.inverse() * curT);
    map<int, Eigen::Vector3d> predictPts;

    for (auto &it_per_id : f_manager.feature)
    {
        if(it_per_id.estimated_depth > 0)
        {
            int firstIndex = it_per_id.start_frame;
            int lastIndex = it_per_id.start_frame + it_per_id.feature_per_frame.size() - 1;
            //printf("cur frame index  %d last frame index %d\n", frame_count, lastIndex);
            if((int)it_per_id.feature_per_frame.size() >= 2 && lastIndex == frame_count)
            {
                double depth = it_per_id.estimated_depth;
                Vector3d pts_j = ric[0] * (depth * it_per_id.feature_per_frame[0].point) + tic[0];
                Vector3d pts_w = Rs[firstIndex] * pts_j + Ps[firstIndex];
                Vector3d pts_local = nextT.block<3, 3>(0, 0).transpose() * (pts_w - nextT.block<3, 1>(0, 3));
                Vector3d pts_cam = ric[0].transpose() * (pts_local - tic[0]);
                int ptsIndex = it_per_id.feature_id;
                predictPts[ptsIndex] = pts_cam;
            }
        }
    }
    featureTracker.setPrediction(predictPts);
    //printf("estimator output %d predict pts\n",(int)predictPts.size());
}

double Estimator::reprojectionError(Matrix3d &Ri, Vector3d &Pi, Matrix3d &rici, Vector3d &tici,
                                 Matrix3d &Rj, Vector3d &Pj, Matrix3d &ricj, Vector3d &ticj, 
                                 double depth, Vector3d &uvi, Vector3d &uvj)
{
    Vector3d pts_w = Ri * (rici * (depth * uvi) + tici) + Pi;
    Vector3d pts_cj = ricj.transpose() * (Rj.transpose() * (pts_w - Pj) - ticj);
    Vector2d residual = (pts_cj / pts_cj.z()).head<2>() - uvj.head<2>();
    double rx = residual.x();
    double ry = residual.y();
    return sqrt(rx * rx + ry * ry);
}

void Estimator::outliersRejection(set<int> &removeIndex)
{
    //return;
    int feature_index = -1;
    for (auto &it_per_id : f_manager.feature)
    {
        double err = 0;
        int errCnt = 0;
        it_per_id.used_num = it_per_id.feature_per_frame.size();
        if (it_per_id.used_num < 4)
            continue;
        feature_index ++;
        int imu_i = it_per_id.start_frame, imu_j = imu_i - 1;
        Vector3d pts_i = it_per_id.feature_per_frame[0].point;
        double depth = it_per_id.estimated_depth;
        for (auto &it_per_frame : it_per_id.feature_per_frame)
        {
            imu_j++;
            if (imu_i != imu_j)
            {
                Vector3d pts_j = it_per_frame.point;             
                double tmp_error = reprojectionError(Rs[imu_i], Ps[imu_i], ric[0], tic[0], 
                                                    Rs[imu_j], Ps[imu_j], ric[0], tic[0],
                                                    depth, pts_i, pts_j);
                err += tmp_error;
                errCnt++;
                //printf("tmp_error %f\n", FOCAL_LENGTH / 1.5 * tmp_error);
            }
            // need to rewrite projecton factor.........
            if(STEREO && it_per_frame.is_stereo)
            {
                
                Vector3d pts_j_right = it_per_frame.pointRight;
                if(imu_i != imu_j)
                {            
                    double tmp_error = reprojectionError(Rs[imu_i], Ps[imu_i], ric[0], tic[0], 
                                                        Rs[imu_j], Ps[imu_j], ric[1], tic[1],
                                                        depth, pts_i, pts_j_right);
                    err += tmp_error;
                    errCnt++;
                    //printf("tmp_error %f\n", FOCAL_LENGTH / 1.5 * tmp_error);
                }
                else
                {
                    double tmp_error = reprojectionError(Rs[imu_i], Ps[imu_i], ric[0], tic[0], 
                                                        Rs[imu_j], Ps[imu_j], ric[1], tic[1],
                                                        depth, pts_i, pts_j_right);
                    err += tmp_error;
                    errCnt++;
                    //printf("tmp_error %f\n", FOCAL_LENGTH / 1.5 * tmp_error);
                }       
            }
        }
        double ave_err = err / errCnt;
        if(ave_err * FOCAL_LENGTH > 3)
            removeIndex.insert(it_per_id.feature_id);

    }
}

void Estimator::setupReliabilityLogger()
{
    if (!SAVE_RELIABILITY_FEATURES)
    {
        reliability_logger_ready = false;
        ROS_WARN("[reliability] save_reliability_features=0, CSV logging disabled.");
        return;
    }

    if (reliability_logger_ready)
        return;

    // ===== runtime env override =====
    const char* env_run_id = std::getenv("REL_RUN_ID");
    const char* env_dataset = std::getenv("REL_DATASET_NAME");
    const char* env_sequence = std::getenv("REL_SEQUENCE_NAME");
    const char* env_feature_csv = std::getenv("REL_FEATURE_CSV_PATH");
    const char* env_save_features = std::getenv("REL_SAVE_FEATURES");

    if (env_save_features && std::string(env_save_features).size() > 0)
    {
        std::string v(env_save_features);
        if (v == "0" || v == "false" || v == "False" || v == "OFF" || v == "off")
        {
            reliability_logger_ready = false;
            ROS_WARN("[reliability] REL_SAVE_FEATURES=0, CSV logging disabled.");
            return;
        }
    }

    if (env_run_id && std::string(env_run_id).size() > 0)
        reliability_run_id = std::string(env_run_id);

    if (env_dataset && std::string(env_dataset).size() > 0)
        reliability_dataset_name = std::string(env_dataset);

    if (env_sequence && std::string(env_sequence).size() > 0)
        reliability_sequence_name = std::string(env_sequence);

    if (env_feature_csv && std::string(env_feature_csv).size() > 0)
        reliability_feature_csv_path = std::string(env_feature_csv);

    try
    {
        reliability_feature_logger.open(reliability_feature_csv_path);
        reliability_logger_ready = true;

        ROS_INFO("reliability CSV logger ready: %s", reliability_feature_csv_path.c_str());
        ROS_INFO("run_id=%s dataset=%s sequence=%s",
                 reliability_run_id.c_str(),
                 reliability_dataset_name.c_str(),
                 reliability_sequence_name.c_str());
    }
    catch (const std::exception &e)
    {
        reliability_logger_ready = false;
        ROS_WARN("failed to open reliability CSV logger: %s", e.what());
    }
}

// ============================================================================
// P1-Reliability R1: per-feature read-only logging (default OFF).
// One row per feature tracked across the latest keyframe interval [i=frame_count-1, j=frame_count].
// Logs the RAW per-feature + per-interval state for OFFLINE d^2 recomputation in R2
// (estimator real relative pose = wheel SE(2) + FOG yaw; stereo/triangulated depth; extrinsics).
// PURE DIAGNOSTIC — never reads back into the optimization, so flag-off is bit-identical.
// ============================================================================
void Estimator::setupPerFeatLogger()
{
    if (!SAVE_PERFEAT_RELIABILITY)
    {
        perfeat_logger_ready = false;
        return;
    }
    if (perfeat_logger_ready)
        return;

    const char* env_on = std::getenv("REL_PERFEAT_LOG");
    if (env_on && std::string(env_on).size() > 0)
    {
        std::string v(env_on);
        if (v == "0" || v == "false" || v == "False" || v == "OFF" || v == "off")
        {
            perfeat_logger_ready = false;
            ROS_WARN("[perfeat] REL_PERFEAT_LOG=0, per-feature logging disabled.");
            return;
        }
    }
    const char* env_csv = std::getenv("REL_PERFEAT_CSV_PATH");
    if (env_csv && std::string(env_csv).size() > 0)
        perfeat_csv_path = std::string(env_csv);

    // reuse run/sequence identity from env (set the same way as the aggregate logger)
    const char* env_run_id = std::getenv("REL_RUN_ID");
    if (env_run_id && std::string(env_run_id).size() > 0)
        reliability_run_id = std::string(env_run_id);
    const char* env_sequence = std::getenv("REL_SEQUENCE_NAME");
    if (env_sequence && std::string(env_sequence).size() > 0)
        reliability_sequence_name = std::string(env_sequence);

    const std::string header =
        "run_id,sequence_name,update_id,frame_count,timestamp,"
        "feature_id,start_frame,used_num,solve_flag,is_stereo_cur,is_stereo_prev,estimated_depth,"
        // observation at frame j = frame_count (cur)
        "nx_j,ny_j,u_j,v_j,nxr_j,nyr_j,"
        // observation at frame i = frame_count-1 (prev)
        "nx_i,ny_i,u_i,v_i,nxr_i,nyr_i,"
        // estimator visual poses (world<-body) frame i and j
        "Pi_x,Pi_y,Pi_z,qi_x,qi_y,qi_z,qi_w,"
        "Pj_x,Pj_y,Pj_z,qj_x,qj_y,qj_z,qj_w,"
        // wheel SE(2) preint for interval [i->j] + 3x3 cov upper-tri
        "w_valid,w_dx,w_dy,w_dtheta,w_t0,w_t1,w_c00,w_c01,w_c02,w_c11,w_c12,w_c22,"
        // FOG yaw preint for interval [i->j]
        "f_valid,f_dpsi,f_var,f_t0,f_t1,"
        // extrinsics cam0/cam1 (body<-cam): tic + ric quat
        "tic0_x,tic0_y,tic0_z,ric0_x,ric0_y,ric0_z,ric0_w,"
        "tic1_x,tic1_y,tic1_z,ric1_x,ric1_y,ric1_z,ric1_w";

    try
    {
        perfeat_logger.open(perfeat_csv_path, header);
        perfeat_logger_ready = true;
        ROS_INFO("[perfeat] per-feature CSV logger ready: %s", perfeat_csv_path.c_str());
    }
    catch (const std::exception &e)
    {
        perfeat_logger_ready = false;
        ROS_WARN("[perfeat] failed to open per-feature CSV: %s", e.what());
    }
}

void Estimator::writePerFeatRows(double header)
{
    if (!SAVE_PERFEAT_RELIABILITY)
        return;
    if (!perfeat_logger_ready)
        setupPerFeatLogger();
    if (!perfeat_logger_ready)
        return;

    const int j = frame_count;        // newest frame index in window
    const int i = frame_count - 1;    // previous frame
    if (i < 0)
        return;

    const long long this_update_id = perfeat_update_id++;

    // ---- per-keyframe context (same for all features this frame) ----
    Eigen::Quaterniond qi(Rs[i]); qi.normalize();
    Eigen::Quaterniond qj(Rs[j]); qj.normalize();

    // wheel / fog preint for the latest interval [i->j] (read-only; FOG factor NOT in graph)
    int w_valid = 0; double w_dx=0, w_dy=0, w_dth=0, w_t0=0, w_t1=0;
    double w_c00=0,w_c01=0,w_c02=0,w_c11=0,w_c12=0,w_c22=0;
    if (wheel_pre_integrations[j] != nullptr)
    {
        WheelPreintegration *wp = wheel_pre_integrations[j];
        w_valid = wp->valid ? 1 : 0;
        w_dx = wp->dx; w_dy = wp->dy; w_dth = wp->dtheta;
        w_t0 = wp->t_start; w_t1 = wp->t_end;
        w_c00 = wp->cov(0,0); w_c01 = wp->cov(0,1); w_c02 = wp->cov(0,2);
        w_c11 = wp->cov(1,1); w_c12 = wp->cov(1,2); w_c22 = wp->cov(2,2);
    }
    int f_valid = 0; double f_dpsi=0, f_var=0, f_t0=0, f_t1=0;
    if (fog_yaw_preint[j] != nullptr)
    {
        FogYawPreintegration *fp = fog_yaw_preint[j];
        f_valid = fp->valid ? 1 : 0;
        f_dpsi = fp->dpsi; f_var = fp->var;
        f_t0 = fp->t_start; f_t1 = fp->t_end;
    }
    Eigen::Quaterniond ric0(ric[0]); ric0.normalize();
    Eigen::Quaterniond ric1(ric[1]); ric1.normalize();

    std::ostringstream ctx;
    ctx.setf(std::ios::fixed); ctx << std::setprecision(10);
    ctx << "," << Ps[i].x() << "," << Ps[i].y() << "," << Ps[i].z()
        << "," << qi.x() << "," << qi.y() << "," << qi.z() << "," << qi.w()
        << "," << Ps[j].x() << "," << Ps[j].y() << "," << Ps[j].z()
        << "," << qj.x() << "," << qj.y() << "," << qj.z() << "," << qj.w()
        << "," << w_valid << "," << w_dx << "," << w_dy << "," << w_dth
        << "," << std::setprecision(9) << w_t0 << "," << w_t1 << std::setprecision(10)
        << "," << w_c00 << "," << w_c01 << "," << w_c02 << "," << w_c11 << "," << w_c12 << "," << w_c22
        << "," << f_valid << "," << f_dpsi << "," << f_var
        << "," << std::setprecision(9) << f_t0 << "," << f_t1 << std::setprecision(10)
        << "," << tic[0].x() << "," << tic[0].y() << "," << tic[0].z()
        << "," << ric0.x() << "," << ric0.y() << "," << ric0.z() << "," << ric0.w()
        << "," << tic[1].x() << "," << tic[1].y() << "," << tic[1].z()
        << "," << ric1.x() << "," << ric1.y() << "," << ric1.z() << "," << ric1.w();
    const std::string ctx_str = ctx.str();

    // ---- per-feature rows: features tracked across the latest interval [i, j] ----
    for (auto &it_per_id : f_manager.feature)
    {
        const int sf = it_per_id.start_frame;
        const int idx_i = i - sf;
        const int idx_j = j - sf;
        const int n = (int)it_per_id.feature_per_frame.size();
        if (idx_i < 0 || idx_j < 0 || idx_j >= n)   // must be observed at BOTH i and j
            continue;

        const FeaturePerFrame &fi = it_per_id.feature_per_frame[idx_i];
        const FeaturePerFrame &fj = it_per_id.feature_per_frame[idx_j];

        auto nanIf = [](bool ok, double v) { return ok ? v : std::numeric_limits<double>::quiet_NaN(); };

        std::ostringstream line;
        line.setf(std::ios::fixed); line << std::setprecision(10);
        line << reliability_run_id << "," << reliability_sequence_name << ","
             << this_update_id << "," << frame_count << ","
             << std::setprecision(9) << header << std::setprecision(10) << ","
             << it_per_id.feature_id << "," << sf << "," << it_per_id.used_num << ","
             << it_per_id.solve_flag << "," << (fj.is_stereo ? 1 : 0) << "," << (fi.is_stereo ? 1 : 0) << ","
             << it_per_id.estimated_depth << ","
             // cur (j)
             << fj.point.x() << "," << fj.point.y() << "," << fj.uv.x() << "," << fj.uv.y() << ","
             << nanIf(fj.is_stereo, fj.pointRight.x()) << "," << nanIf(fj.is_stereo, fj.pointRight.y()) << ","
             // prev (i)
             << fi.point.x() << "," << fi.point.y() << "," << fi.uv.x() << "," << fi.uv.y() << ","
             << nanIf(fi.is_stereo, fi.pointRight.x()) << "," << nanIf(fi.is_stereo, fi.pointRight.y());
        line << ctx_str;
        perfeat_logger.append(line.str());
    }
    perfeat_logger.flush();
}

// ============================================================================
// P1-Reliability R3b: per-feature consistency d^2 -> reliability=exp(-d2/2k) -> per-feature visual weight.
// Direct port of the offline-validated R2 (r2_consistency_d2.py): wheel SE(2) reference (independent of pose;
// WHEEL_REFERENCE_ONLY), full cov budget (wheel 3x3 + depth-from-disparity + Sigma_uv). Temporal memory (EMA
// fast-down/slow-up) + anti-degeneracy (floor + keep-top-N). Fills feat_weight_cur_[feature_id] = sqrt(reliability).
// Bounded by construction: reliability in (0,1], floored -> cannot blow up like the FOG factor.
// ============================================================================
// v11 learned ReliabilityNet: per-feature weight from an ONNX model (PerFeatNet). Features [reproj,ex,ey,log1p(track),
// nx,ny] = the SAME wheel-reprojection geometry the d2 path computes; normalization + logit->weight baked into the ONNX.
// Default OFF (REL_USE_LEARNED_MODEL); any failure -> leave weights at 1.0 (do-no-harm).
void Estimator::computeFeatureReliability_learned()
{
    static Ort::Env* g_env = nullptr; static Ort::Session* g_sess = nullptr;
    static bool g_ready = false, g_tried = false;
    if (!g_tried) {
        g_tried = true;
        try {
            g_env = new Ort::Env(ORT_LOGGING_LEVEL_WARNING, "rel");
            Ort::SessionOptions so; so.SetIntraOpNumThreads(1);
            g_sess = new Ort::Session(*g_env, REL_ONNX_PATH.c_str(), so);
            g_ready = true;
            ROS_WARN("[reliability-learned] ONNX ready: %s", REL_ONNX_PATH.c_str());
        } catch (const std::exception& e) { ROS_ERROR("[reliability-learned] ONNX load FAILED (%s) -> w=1.0", e.what()); }
    }
    if (!g_ready) return;
    const int j = frame_count, i = frame_count - 1;
    if (!reliability_intr_ready_) {
        double Sx=0,Sxx=0,Su=0,Sxu=0, Sy=0,Syy=0,Sv=0,Syv=0; long N=0;
        for (auto &it : f_manager.feature) for (auto &f : it.feature_per_frame) {
            double nx=f.point.x(),ny=f.point.y(),u=f.uv.x(),v=f.uv.y();
            Sx+=nx;Sxx+=nx*nx;Su+=u;Sxu+=nx*u; Sy+=ny;Syy+=ny*ny;Sv+=v;Syv+=ny*v; N++; }
        if (N>50){ double dx=N*Sxx-Sx*Sx,dy=N*Syy-Sy*Sy;
            if (std::abs(dx)>1e-9&&std::abs(dy)>1e-9){ rel_fx_=(N*Sxu-Sx*Su)/dx; rel_cx_=(Su-rel_fx_*Sx)/N;
                rel_fy_=(N*Syv-Sy*Sv)/dy; rel_cy_=(Sv-rel_fy_*Sy)/N; reliability_intr_ready_=(rel_fx_>1.0&&rel_fy_>1.0);} }
        if (!reliability_intr_ready_) return;
    }
    WheelPreintegration *wp = wheel_pre_integrations[j];
    if (wp==nullptr || !wp->valid) return;
    const double fx=rel_fx_,fy=rel_fy_,cx=rel_cx_,cy=rel_cy_;
    double baseline=(tic[0]-tic[1]).norm();
    Eigen::Matrix3d R_bc=ric[0]; Eigen::Vector3d t_bc=tic[0];
    Eigen::Matrix3d R_cb=R_bc.transpose(); Eigen::Vector3d t_cb=-R_cb*t_bc;
    double dx_r=wp->dx,dy_r=wp->dy,dth_r=wp->dtheta;
    auto predict=[&](const Eigen::Vector3d&P_i,double pdx,double pdy,double pdth,bool&ok)->Eigen::Vector2d{
        double c=std::cos(pdth),s=std::sin(pdth); Eigen::Matrix3d Rb; Rb<<c,-s,0,s,c,0,0,0,1;
        Eigen::Vector3d Pb_i=R_bc*P_i+t_bc; Eigen::Vector3d Pb_j=Rb*Pb_i+Eigen::Vector3d(pdx,pdy,0.0);
        Eigen::Vector3d Pc_j=R_cb*Pb_j+t_cb; if(Pc_j.z()<=1e-6){ok=false;return Eigen::Vector2d::Zero();}
        ok=true; return Eigen::Vector2d(fx*Pc_j.x()/Pc_j.z()+cx,fy*Pc_j.y()/Pc_j.z()+cy); };
    std::vector<float> feats; std::vector<int> fids; feats.reserve(2048);
    for (auto &it : f_manager.feature) {
        const int sf=it.start_frame, idx_i=i-sf, idx_j=j-sf;
        const int n=(int)it.feature_per_frame.size();
        if (idx_i<0||idx_j<0||idx_j>=n) continue;
        const FeaturePerFrame &fi=it.feature_per_frame[idx_i], &fj=it.feature_per_frame[idx_j];
        if (!fi.is_stereo) continue;
        double disp=fi.point.x()-fi.pointRight.x(); if(!std::isfinite(disp)||std::abs(disp)<1e-4) continue;
        double Z=baseline/disp; if(!(Z>1.0&&Z<120.0)) continue;
        Eigen::Vector3d P_i=Z*Eigen::Vector3d(fi.point.x(),fi.point.y(),1.0);
        bool ok=false; Eigen::Vector2d uh=predict(P_i,dx_r,dy_r,dth_r,ok); if(!ok) continue;
        Eigen::Vector2d e(fj.uv.x()-uh.x(), fj.uv.y()-uh.y());
        feats.push_back((float)e.norm()); feats.push_back((float)e.x()); feats.push_back((float)e.y());
        feats.push_back((float)std::log1p((double)it.used_num)); feats.push_back((float)fi.point.x()); feats.push_back((float)fi.point.y());
        fids.push_back(it.feature_id);
    }
    if (fids.empty()) return;
    std::vector<float> wout(fids.size(), 1.0f);
    try {
        Ort::MemoryInfo mi = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        std::array<int64_t,2> shape{(int64_t)fids.size(), 6};
        Ort::Value in = Ort::Value::CreateTensor<float>(mi, feats.data(), feats.size(), shape.data(), 2);
        const char* innames[]={"feat"}; const char* outnames[]={"weight"};
        auto out = g_sess->Run(Ort::RunOptions{nullptr}, innames, &in, 1, outnames, 1);
        float* wd = out[0].GetTensorMutableData<float>();
        for (size_t k=0;k<fids.size();++k) wout[k]=wd[k];
    } catch (const std::exception& e) { ROS_ERROR("[reliability-learned] inference failed: %s", e.what()); return; }
    std::vector<std::pair<int,int>> rank;
    for (auto &it : f_manager.feature) if (it.endFrame()==j) rank.push_back({it.used_num, it.feature_id});
    std::sort(rank.begin(),rank.end(),[](auto&a,auto&b){return a.first>b.first;});
    std::set<int> keep; for (int k=0;k<(int)rank.size()&&k<RELIABILITY_KEEPN;++k) keep.insert(rank[k].second);
    double wmin=1e9,wmax=-1e9;
    for (size_t k=0;k<fids.size();++k){
        double w = std::min(1.0,std::max((double)RELIABILITY_FLOOR,(double)wout[k]));
        if (keep.count(fids[k])) w=1.0;
        feat_weight_cur_[fids[k]]=w; wmin=std::min(wmin,w); wmax=std::max(wmax,w);
    }
    if (!feat_weight_cur_.empty())
        ROS_INFO("[reliability-learned] feats=%zu w_range=[%.3f,%.3f] (ONNX)", feat_weight_cur_.size(), wmin, wmax);
}

void Estimator::computeFeatureReliability()
{
    feat_weight_cur_.clear();
    if (!FEATURE_RELIABILITY_ENABLE)
        return;
    const int j = frame_count, i = frame_count - 1;
    if (i < 0)
        return;
    if (REL_USE_LEARNED_MODEL) { computeFeatureReliability_learned(); return; }

    // ---- recover pinhole intrinsics once (u = fx*nx + cx) from real observations ----
    if (!reliability_intr_ready_)
    {
        double Sx=0,Sxx=0,Su=0,Sxu=0, Sy=0,Syy=0,Sv=0,Syv=0; long N=0;
        for (auto &it : f_manager.feature)
            for (auto &f : it.feature_per_frame)
            {
                double nx=f.point.x(), ny=f.point.y(), u=f.uv.x(), v=f.uv.y();
                Sx+=nx; Sxx+=nx*nx; Su+=u; Sxu+=nx*u; Sy+=ny; Syy+=ny*ny; Sv+=v; Syv+=ny*v; N++;
            }
        if (N > 50)
        {
            double dx = N*Sxx - Sx*Sx, dy = N*Syy - Sy*Sy;
            if (std::abs(dx)>1e-9 && std::abs(dy)>1e-9)
            {
                rel_fx_ = (N*Sxu - Sx*Su)/dx; rel_cx_ = (Su - rel_fx_*Sx)/N;
                rel_fy_ = (N*Syv - Sy*Sv)/dy; rel_cy_ = (Sv - rel_fy_*Sy)/N;
                reliability_intr_ready_ = (rel_fx_ > 1.0 && rel_fy_ > 1.0);
            }
        }
        if (!reliability_intr_ready_) return;   // wait until we can calibrate intrinsics
    }

    // §2 ablation: weight signal source. motion (default) = INDEPENDENT wheel SE(2) reference (d2 of obs vs
    // wheel-predicted reprojection); residual = the VIO's OWN reprojection residual (estimator relative pose, NO
    // independent reference) -> isolates whether the *independent motion reference* is the key value, vs plain
    // robust-residual culling (which the optimizer's Huber kernel already does).
    const bool use_residual = RELIABILITY_WEIGHT_RESIDUAL;
    WheelPreintegration *wp = wheel_pre_integrations[j];
    if (!use_residual && (wp == nullptr || !wp->valid))
        return;   // motion mode needs the independent reference this interval (residual mode does not)

    const double fx=rel_fx_, fy=rel_fy_, cx=rel_cx_, cy=rel_cy_;
    const double sigma_uv = RELIABILITY_SIGMA_UV, sig2 = sigma_uv*sigma_uv;
    // baseline (cam0<->cam1) and cam0<->body extrinsic from current estimator state
    double baseline = (tic[0] - tic[1]).norm();
    Eigen::Matrix3d R_bc = ric[0]; Eigen::Vector3d t_bc = tic[0];
    Eigen::Matrix3d R_cb = R_bc.transpose(); Eigen::Vector3d t_cb = -R_cb * t_bc;
    // motion reference (wheel SE(2)) state — only used in motion mode
    Eigen::Matrix3d Sig_m = Eigen::Matrix3d::Identity();
    double dx_r=0, dy_r=0, dth_r=0;
    if (!use_residual)
    {
        Sig_m = wp->cov;   // 3x3 cov of (dx,dy,dtheta)
        dx_r = wp->dx; dy_r = wp->dy; dth_r = wp->dtheta;
        // P3 do-no-harm: lever-arm reference-error (~L*dtheta during turns), ONE global L, adaptive to turning.
        double lever_err = RELIABILITY_LEVER_ARM * std::abs(dth_r);
        Sig_m(0,0) += lever_err * lever_err;
        Sig_m(1,1) += lever_err * lever_err;
    }
    // estimator relative pose body_i -> body_j (residual mode reference = the VIO's own optimized motion)
    Eigen::Matrix3d R_rel = Rs[j].transpose() * Rs[i];
    Eigen::Vector3d t_rel = Rs[j].transpose() * (Ps[i] - Ps[j]);

    auto predict_wheel = [&](const Eigen::Vector3d &P_i, double pdx, double pdy, double pdth, bool &ok) -> Eigen::Vector2d {
        double c=std::cos(pdth), s=std::sin(pdth);
        Eigen::Matrix3d Rb; Rb << c,-s,0, s,c,0, 0,0,1;
        Eigen::Vector3d Pb_i = R_bc * P_i + t_bc;
        Eigen::Vector3d Pb_j = Rb * Pb_i + Eigen::Vector3d(pdx,pdy,0.0);
        Eigen::Vector3d Pc_j = R_cb * Pb_j + t_cb;
        if (Pc_j.z() <= 1e-6) { ok=false; return Eigen::Vector2d::Zero(); }
        ok=true; return Eigen::Vector2d(fx*Pc_j.x()/Pc_j.z()+cx, fy*Pc_j.y()/Pc_j.z()+cy);
    };
    auto predict_est = [&](const Eigen::Vector3d &P_i, bool &ok) -> Eigen::Vector2d {
        Eigen::Vector3d Pb_i = R_bc * P_i + t_bc;
        Eigen::Vector3d Pb_j = R_rel * Pb_i + t_rel;
        Eigen::Vector3d Pc_j = R_cb * Pb_j + t_cb;
        if (Pc_j.z() <= 1e-6) { ok=false; return Eigen::Vector2d::Zero(); }
        ok=true; return Eigen::Vector2d(fx*Pc_j.x()/Pc_j.z()+cx, fy*Pc_j.y()/Pc_j.z()+cy);
    };

    double wmin=1e9, wmax=-1e9;
    for (auto &it : f_manager.feature)
    {
        const int sf = it.start_frame, idx_i = i - sf, idx_j = j - sf;
        const int n = (int)it.feature_per_frame.size();
        if (idx_i < 0 || idx_j < 0 || idx_j >= n) continue;
        const FeaturePerFrame &fi = it.feature_per_frame[idx_i];
        const FeaturePerFrame &fj = it.feature_per_frame[idx_j];
        if (!fi.is_stereo) continue;
        double disp = fi.point.x() - fi.pointRight.x();
        if (!std::isfinite(disp) || std::abs(disp) < 1e-4) continue;
        double Z = baseline / disp;
        if (!(Z > 1.0 && Z < 120.0)) continue;
        Eigen::Vector3d P_i = Z * Eigen::Vector3d(fi.point.x(), fi.point.y(), 1.0);
        bool ok=false; Eigen::Vector2d uh = use_residual ? predict_est(P_i, ok) : predict_wheel(P_i, dx_r, dy_r, dth_r, ok);
        if (!ok) continue;
        Eigen::Vector2d e(fj.uv.x()-uh.x(), fj.uv.y()-uh.y());
        // motion term: ONLY in motion mode (independent wheel reference has a 3x3 cov). residual mode has no
        // independent motion uncertainty (the residual is taken vs the estimator's own pose).
        Eigen::Matrix2d motion = Eigen::Matrix2d::Zero();
        if (!use_residual)
        {
            const double eps=1e-5; Eigen::Matrix<double,2,3> Jp; bool o2;
            Jp.col(0) = (predict_wheel(P_i, dx_r+eps, dy_r, dth_r, o2) - uh)/eps;
            Jp.col(1) = (predict_wheel(P_i, dx_r, dy_r+eps, dth_r, o2) - uh)/eps;
            Jp.col(2) = (predict_wheel(P_i, dx_r, dy_r, dth_r+eps, o2) - uh)/eps;
            motion = Jp * Sig_m * Jp.transpose();
        }
        // depth term
        double sig_disp = std::sqrt(2.0)*sigma_uv/fx; double sig_Z = (Z*Z/std::max(baseline,1e-6))*sig_disp;
        double dZ = std::max(1e-4, 1e-3*Z);
        Eigen::Vector3d P_i2 = (Z+dZ) * Eigen::Vector3d(fi.point.x(), fi.point.y(), 1.0);
        bool o3; Eigen::Vector2d uh2 = use_residual ? predict_est(P_i2, o3) : predict_wheel(P_i2, dx_r, dy_r, dth_r, o3);
        Eigen::Vector2d Jd = (uh2 - uh)/dZ;
        Eigen::Matrix2d depth = Jd * Jd.transpose() * (sig_Z*sig_Z);
        Eigen::Matrix2d S = motion + depth + sig2*Eigen::Matrix2d::Identity();
        double d2 = e.transpose() * S.inverse() * e;
        if (!std::isfinite(d2) || d2 < 0) continue;
        // floored mapping: features statistically consistent with static (d2 < thresh) keep reliability 1.0;
        // only inconsistent features (d2 > chi2(2).95) are down-weighted. Avoids penalizing noisy-but-static feats.
        double d2_excess = std::max(0.0, d2 - RELIABILITY_D2_THRESH);
        double rel_raw = std::exp(-d2_excess / (2.0*RELIABILITY_KAPPA));
        rel_raw = std::min(1.0, std::max(0.0, rel_raw));
        // temporal memory: fast-down / slow-up
        double prev = track_rel_.count(it.feature_id) ? track_rel_[it.feature_id] : 1.0;
        double a = (rel_raw < prev) ? RELIABILITY_EMA_DOWN : RELIABILITY_EMA_UP;
        double ema = a*rel_raw + (1.0-a)*prev;
        track_rel_[it.feature_id] = std::max(RELIABILITY_FLOOR, std::min(1.0, ema));
    }

    // ---- anti-degeneracy: keep top-N current features (by track length) at weight 1.0 ----
    std::vector<std::pair<int,int>> rank;   // (used_num, feature_id) for features observed this frame
    for (auto &it : f_manager.feature)
        if (it.endFrame() == j) rank.push_back({it.used_num, it.feature_id});
    std::sort(rank.begin(), rank.end(), [](auto &a, auto &b){ return a.first > b.first; });
    std::set<int> keep;
    for (int k=0; k < (int)rank.size() && k < RELIABILITY_KEEPN; ++k) keep.insert(rank[k].second);

    // ---- finalize feat_weight_cur_ for every feature in the window ----
    for (auto &it : f_manager.feature)
    {
        double rel = track_rel_.count(it.feature_id) ? track_rel_[it.feature_id] : 1.0;
        if (keep.count(it.feature_id)) rel = 1.0;
        double w = std::sqrt(std::min(1.0, std::max(RELIABILITY_FLOOR, rel)));
        feat_weight_cur_[it.feature_id] = w;
        wmin = std::min(wmin, w); wmax = std::max(wmax, w);
    }
    if (!feat_weight_cur_.empty())
        ROS_INFO("[reliability] feats=%zu w_range=[%.3f,%.3f] kappa=%.2f", feat_weight_cur_.size(), wmin, wmax, RELIABILITY_KAPPA);
}

void Estimator::computePendingFeatureStats(
    const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame,
    double feature_tracker_time_ms,
    double image_timestamp,
    int image_width,
    int image_height)
{
    pending_feature_tracker_time_ms = feature_tracker_time_ms;

    if (reliability_prev_image_time < 0.0)
        pending_img_dt_sec = 0.0;
    else
        pending_img_dt_sec = std::max(0.0, image_timestamp - reliability_prev_image_time);

    reliability_prev_image_time = image_timestamp;

    std::vector<double> speeds;
    speeds.reserve(featureFrame.size());

    for (const auto &kv : featureFrame)
    {
        for (const auto &obs_pair : kv.second)
        {
            const auto &obs = obs_pair.second;

            // obs(5), obs(6): feature tracker velocity x/y
            const double vx = obs(5);
            const double vy = obs(6);
            const double speed = std::sqrt(vx * vx + vy * vy);

            if (std::isfinite(speed))
                speeds.push_back(speed);
        }
    }

    pending_mean_track_vel_px = meanOf(speeds);
    pending_median_track_vel_px = medianOf(speeds);
    pending_min_track_vel_px = 0.0;
    pending_max_track_vel_px = 0.0;

    if (!speeds.empty())
    {
        auto minmax_v = std::minmax_element(speeds.begin(), speeds.end());
        pending_min_track_vel_px = *minmax_v.first;
        pending_max_track_vel_px = *minmax_v.second;
    }

    pending_std_track_vel_px = stdOf(speeds);
    pending_p90_track_vel_px = percentileOf(speeds, 0.90);

    GridStats grid4 = computeGridStats(featureFrame, image_width, image_height, 4);
    GridStats grid8 = computeGridStats(featureFrame, image_width, image_height, 8);

    pending_coverage_4x4 = grid4.coverage;
    pending_coverage_8x8 = grid8.coverage;

    pending_occupied_cells_4x4 = grid4.occupied_cells;
    pending_occupied_cells_8x8 = grid8.occupied_cells;

    pending_entropy_4x4 = grid4.entropy;
    pending_entropy_8x8 = grid8.entropy;
}

void Estimator::computePendingImuStats(
    const vector<pair<double, Eigen::Vector3d>> &accVector,
    const vector<pair<double, Eigen::Vector3d>> &gyrVector)
{
    // 保留你原本 acc_norm / gyr_norm 統計

    pending_gyro_raw_delta_q = Eigen::Quaterniond::Identity();
    pending_gyro_bgcorr_delta_q = Eigen::Quaterniond::Identity();

    const int bg_idx = std::max(0, std::min(frame_count, WINDOW_SIZE));
    const Eigen::Vector3d bg = Bgs[bg_idx];

    std::vector<double> dt_list;
    std::vector<double> gx, gy, gz;
    std::vector<double> gx_abs, gy_abs, gz_abs;
    std::vector<double> bgcorr_norms;
    std::vector<double> bgcorr_x;
    std::vector<double> bgcorr_y;
    std::vector<double> bgcorr_z;

    double abs_angle_sum_rad = 0.0;

    for (size_t i = 0; i < gyrVector.size(); ++i)
    {
        const Eigen::Vector3d w_raw = gyrVector[i].second;
        const Eigen::Vector3d w_corr = w_raw - bg;

        bgcorr_x.push_back(w_corr.x());
        bgcorr_y.push_back(w_corr.y());
        bgcorr_z.push_back(w_corr.z());

        gx.push_back(w_raw.x());
        gy.push_back(w_raw.y());
        gz.push_back(w_raw.z());

        gx_abs.push_back(std::abs(w_raw.x()));
        gy_abs.push_back(std::abs(w_raw.y()));
        gz_abs.push_back(std::abs(w_raw.z()));

        bgcorr_norms.push_back(w_corr.norm());

        if (i == 0)
            continue;

        double dt = gyrVector[i].first - gyrVector[i - 1].first;

        if (!(dt > 0.0 && dt < 1.0))
            continue;

        dt_list.push_back(dt);

        const Eigen::Vector3d w_raw_prev = gyrVector[i - 1].second;
        const Eigen::Vector3d w_corr_prev = w_raw_prev - bg;

        const Eigen::Vector3d w_raw_mid = 0.5 * (w_raw_prev + w_raw);
        const Eigen::Vector3d w_corr_mid = 0.5 * (w_corr_prev + w_corr);

        pending_gyro_raw_delta_q =
            pending_gyro_raw_delta_q * Utility::expSO3(w_raw_mid * dt);

        pending_gyro_bgcorr_delta_q =
            pending_gyro_bgcorr_delta_q * Utility::expSO3(w_corr_mid * dt);

        pending_gyro_raw_delta_q.normalize();
        pending_gyro_bgcorr_delta_q.normalize();

        abs_angle_sum_rad += w_corr_mid.norm() * dt;
    }

    const double rad2deg = 180.0 / M_PI;

    Eigen::Vector3d raw_rv = Utility::logSO3(pending_gyro_raw_delta_q) * rad2deg;
    Eigen::Vector3d corr_rv = Utility::logSO3(pending_gyro_bgcorr_delta_q) * rad2deg;

    pending_gyro_raw_rotvec_x_deg = raw_rv.x();
    pending_gyro_raw_rotvec_y_deg = raw_rv.y();
    pending_gyro_raw_rotvec_z_deg = raw_rv.z();
    pending_gyro_raw_delta_angle_deg = raw_rv.norm();

    pending_gyro_bgcorr_rotvec_x_deg = corr_rv.x();
    pending_gyro_bgcorr_rotvec_y_deg = corr_rv.y();
    pending_gyro_bgcorr_rotvec_z_deg = corr_rv.z();
    pending_gyro_bgcorr_delta_angle_deg = corr_rv.norm();

    pending_gyro_abs_angle_sum_deg = abs_angle_sum_rad * rad2deg;

    pending_gyr_x_mean = meanOf(gx);
    pending_gyr_y_mean = meanOf(gy);
    pending_gyr_z_mean = meanOf(gz);

    pending_gyr_x_std = stdOf(gx);
    pending_gyr_y_std = stdOf(gy);
    pending_gyr_z_std = stdOf(gz);

    pending_gyr_x_max_abs = maxOf(gx_abs);
    pending_gyr_y_max_abs = maxOf(gy_abs);
    pending_gyr_z_max_abs = maxOf(gz_abs);

    pending_gyr_bgcorr_x_mean = meanOf(bgcorr_x);
    pending_gyr_bgcorr_y_mean = meanOf(bgcorr_y);
    pending_gyr_bgcorr_z_mean = meanOf(bgcorr_z);
    pending_gyr_bgcorr_norm_mean = meanOf(bgcorr_norms);

    pending_imu_dt_mean = meanOf(dt_list);
    pending_imu_dt_std = stdOf(dt_list);
    pending_imu_dt_min = dt_list.empty() ? 0.0 : *std::min_element(dt_list.begin(), dt_list.end());
    pending_imu_dt_max = dt_list.empty() ? 0.0 : *std::max_element(dt_list.begin(), dt_list.end());
    pending_imu_dt_gap_max = pending_imu_dt_max;

    pending_imu_total_dt = std::accumulate(dt_list.begin(), dt_list.end(), 0.0);
    pending_imu_image_dt_diff = std::abs(pending_img_dt_sec - pending_imu_total_dt);
}

double Estimator::computeAverageTrackLength() const
{
    if (f_manager.feature.empty())
        return 0.0;

    double sum_len = 0.0;
    int count = 0;

    for (const auto &feat : f_manager.feature)
    {
        sum_len += static_cast<double>(feat.feature_per_frame.size());
        ++count;
    }

    if (count <= 0)
        return 0.0;

    return sum_len / static_cast<double>(count);
}

void Estimator::computeManagerFeatureStats()
{
    std::vector<double> track_lengths;
    std::vector<double> depths;

    int good_depth_count = 0;
    int bad_depth_count = 0;

    for (const auto &it_per_id : f_manager.feature)
    {
        const double track_len = static_cast<double>(it_per_id.feature_per_frame.size());
        track_lengths.push_back(track_len);

        if (std::isfinite(it_per_id.estimated_depth) && it_per_id.estimated_depth > 0.0)
        {
            depths.push_back(it_per_id.estimated_depth);
            good_depth_count++;
        }
        else
        {
            bad_depth_count++;
        }
    }

    pending_track_len_min = 0.0;
    pending_track_len_max = 0.0;

    if (!track_lengths.empty())
    {
        auto minmax_track = std::minmax_element(track_lengths.begin(), track_lengths.end());
        pending_track_len_min = *minmax_track.first;
        pending_track_len_max = *minmax_track.second;
    }

    pending_track_len_std = stdOf(track_lengths);
    pending_track_len_p90 = percentileOf(track_lengths, 0.90);

    pending_good_depth_count = good_depth_count;
    pending_bad_depth_count = bad_depth_count;

    pending_depth_mean = meanOf(depths);
    pending_depth_min = 0.0;
    pending_depth_max = 0.0;

    if (!depths.empty())
    {
        auto minmax_depth = std::minmax_element(depths.begin(), depths.end());
        pending_depth_min = *minmax_depth.first;
        pending_depth_max = *minmax_depth.second;
    }

    pending_depth_std = stdOf(depths);
}

std::string Estimator::inferFailureReasonProxy(bool failure_flag) const
{
    if (failure_flag)
    {
        if (tracked_feature_count_mgr < 20)
            return "failure_detection_low_feature";

        if (outlier_ratio_last > 0.60)
            return "failure_detection_high_outlier";

        if (solver_time_ms_last > SOLVER_TIME * 1000.0 * 2.0)
            return "failure_detection_solver_slow";

        if (Bas[WINDOW_SIZE].norm() > 5.0)
            return "failure_detection_acc_bias_large";
        
        if (Bgs[WINDOW_SIZE].norm() > 1.0)
            return "failure_detection_gyr_bias_large";

        return "failure_detection";
    }

    if (tracked_feature_count_raw > 0 && tracked_feature_count_raw < 20)
        return "warning_low_raw_feature";

    if (tracked_feature_count_mgr > 0 && tracked_feature_count_mgr < 20)
        return "warning_low_manager_feature";

    if (outlier_ratio_last > 0.60)
        return "warning_high_outlier_ratio";

    if (solver_time_ms_last > SOLVER_TIME * 1000.0 * 2.0)
        return "warning_solver_slow";

    return "none";
}

void Estimator::setReliabilityFeatureJsonCallback(std::function<void(const std::string &)> cb)
{
    reliability_feature_json_callback = cb;
}

std::string Estimator::buildReliabilityFeatureJson(double header) const
{
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(9);

    Eigen::Quaterniond q(Rs[WINDOW_SIZE]);
    q.normalize();

    double delta_p_norm = 0.0;
    double delta_q_deg = 0.0;

    if (reliability_has_prev_logged_pose)
    {
        delta_p_norm = (Ps[WINDOW_SIZE] - reliability_prev_logged_P).norm();
        delta_q_deg = quatDistanceDeg(reliability_prev_logged_Q, q);
    }

    ss << "{";

    // ===== identity / timing =====
    ss << "\"timestamp\":" << header << ",";

    // ===== estimator mode =====
    ss << "\"current_is_keyframe\":" << (current_is_keyframe ? 1 : 0) << ",";
    ss << "\"use_imu\":" << (USE_IMU ? 1 : 0) << ",";
    ss << "\"stereo\":" << (STEREO ? 1 : 0) << ",";
    ss << "\"estimate_extrinsic\":" << ESTIMATE_EXTRINSIC << ",";
    ss << "\"estimate_td\":" << ESTIMATE_TD << ",";
    ss << "\"td_current\":" << td << ",";

    // ===== frontend / tracker quality =====
    ss << "\"feature_tracker_time_ms\":" << pending_feature_tracker_time_ms << ",";
    ss << "\"tracked_feature_count_raw\":" << tracked_feature_count_raw << ",";
    ss << "\"tracked_feature_count_mgr\":" << tracked_feature_count_mgr << ",";

    ss << "\"mean_track_vel_px\":" << pending_mean_track_vel_px << ",";
    ss << "\"median_track_vel_px\":" << pending_median_track_vel_px << ",";
    ss << "\"min_track_vel_px\":" << pending_min_track_vel_px << ",";
    ss << "\"max_track_vel_px\":" << pending_max_track_vel_px << ",";
    ss << "\"std_track_vel_px\":" << pending_std_track_vel_px << ",";
    ss << "\"p90_track_vel_px\":" << pending_p90_track_vel_px << ",";

    ss << "\"coverage_4x4\":" << pending_coverage_4x4 << ",";
    ss << "\"coverage_8x8\":" << pending_coverage_8x8 << ",";
    ss << "\"occupied_cells_4x4\":" << pending_occupied_cells_4x4 << ",";
    ss << "\"occupied_cells_8x8\":" << pending_occupied_cells_8x8 << ",";
    ss << "\"feature_entropy_4x4\":" << pending_entropy_4x4 << ",";
    ss << "\"feature_entropy_8x8\":" << pending_entropy_8x8 << ",";

    ss << "\"img_dt_sec\":" << pending_img_dt_sec << ",";

    // ===== backend health =====
    ss << "\"solver_time_ms_last\":" << solver_time_ms_last << ",";
    ss << "\"outlier_count_last\":" << outlier_count_last << ",";
    ss << "\"inlier_count_last\":" << inlier_count_last << ",";
    ss << "\"outlier_ratio_last\":" << outlier_ratio_last << ",";

    // ===== current state =====
    ss << "\"vel_norm\":" << Vs[WINDOW_SIZE].norm() << ",";
    ss << "\"ba_norm\":" << Bas[WINDOW_SIZE].norm() << ",";
    ss << "\"bg_norm\":" << Bgs[WINDOW_SIZE].norm() << ",";
    ss << "\"delta_p_norm\":" << delta_p_norm << ",";
    ss << "\"delta_q_deg\":" << delta_q_deg << ",";

    // ===== IMU statistics =====
    ss << "\"imu_sample_count\":" << pending_imu_sample_count << ",";
    ss << "\"acc_norm_mean\":" << pending_acc_norm_mean << ",";
    ss << "\"acc_norm_std\":" << pending_acc_norm_std << ",";
    ss << "\"acc_norm_max\":" << pending_acc_norm_max << ",";
    ss << "\"gyr_norm_mean\":" << pending_gyr_norm_mean << ",";
    ss << "\"gyr_norm_std\":" << pending_gyr_norm_std << ",";
    ss << "\"gyr_norm_max\":" << pending_gyr_norm_max << ",";

    // ===== FeatureManager / geometry statistics =====
    ss << "\"avg_track_length\":" << computeAverageTrackLength() << ",";
    ss << "\"track_len_min\":" << pending_track_len_min << ",";
    ss << "\"track_len_max\":" << pending_track_len_max << ",";
    ss << "\"track_len_std\":" << pending_track_len_std << ",";
    ss << "\"track_len_p90\":" << pending_track_len_p90 << ",";

    ss << "\"good_depth_count\":" << pending_good_depth_count << ",";
    ss << "\"bad_depth_count\":" << pending_bad_depth_count << ",";
    ss << "\"depth_mean\":" << pending_depth_mean << ",";
    ss << "\"depth_min\":" << pending_depth_min << ",";
    ss << "\"depth_max\":" << pending_depth_max << ",";
    ss << "\"depth_std\":" << pending_depth_std;

    ss << "}";

    return ss.str();
}

void Estimator::writeReliabilityFeatureRow(double header)
{
    if (!SAVE_RELIABILITY_FEATURES)
        return;

    const long long this_update_id = reliability_update_id++;

    if (RELIABILITY_LOG_EVERY_N > 1 &&
        (this_update_id % RELIABILITY_LOG_EVERY_N) != 0)
    {
        return;
    }

    if (!reliability_logger_ready)
        setupReliabilityLogger();

    if (!reliability_logger_ready)
        return;

    ReliabilityCsvRow row;

    // v5 feature schema
    row.schema_version = 3;

    // ============================================================
    // 1. identity / timing
    // ============================================================
    row.run_id = reliability_run_id;
    row.dataset_name = reliability_dataset_name;
    row.sequence_name = reliability_sequence_name;

    row.update_id = this_update_id;
    row.frame_count = frame_count;
    row.timestamp = header;

    // ============================================================
    // 2. estimator mode
    // ============================================================
    row.solver_flag = (solver_flag == NON_LINEAR) ? "NON_LINEAR" : "INITIAL";

    row.use_imu = USE_IMU ? 1 : 0;
    row.stereo = STEREO ? 1 : 0;
    row.current_is_keyframe = current_is_keyframe ? 1 : 0;
    row.estimate_extrinsic = ESTIMATE_EXTRINSIC;
    row.estimate_td = ESTIMATE_TD;
    row.td_current = td;

    // ============================================================
    // 3. frontend / tracker quality
    // ============================================================
    row.feature_tracker_time_ms = pending_feature_tracker_time_ms;

    row.tracked_feature_count_raw = tracked_feature_count_raw;
    row.tracked_feature_count_mgr = tracked_feature_count_mgr;

    row.mean_track_vel_px = pending_mean_track_vel_px;
    row.median_track_vel_px = pending_median_track_vel_px;
    row.min_track_vel_px = pending_min_track_vel_px;
    row.max_track_vel_px = pending_max_track_vel_px;
    row.std_track_vel_px = pending_std_track_vel_px;
    row.p90_track_vel_px = pending_p90_track_vel_px;

    row.coverage_4x4 = pending_coverage_4x4;
    row.coverage_8x8 = pending_coverage_8x8;
    row.occupied_cells_4x4 = pending_occupied_cells_4x4;
    row.occupied_cells_8x8 = pending_occupied_cells_8x8;
    row.feature_entropy_4x4 = pending_entropy_4x4;
    row.feature_entropy_8x8 = pending_entropy_8x8;

    row.img_dt_sec = pending_img_dt_sec;

    // ============================================================
    // 4. backend health
    // ============================================================
    row.solver_time_ms_last = solver_time_ms_last;
    row.outlier_count_last = outlier_count_last;
    row.inlier_count_last = inlier_count_last;
    row.outlier_ratio_last = outlier_ratio_last;
    row.failure_detected_last = failure_detected_last ? 1 : 0;
    row.failure_reason_proxy = inferFailureReasonProxy(failure_detected_last);

    // ============================================================
    // 5. current state
    // ============================================================
    Eigen::Quaterniond q_now(Rs[WINDOW_SIZE]);
    q_now.normalize();

    row.est_p_x = Ps[WINDOW_SIZE].x();
    row.est_p_y = Ps[WINDOW_SIZE].y();
    row.est_p_z = Ps[WINDOW_SIZE].z();

    row.est_q_x = q_now.x();
    row.est_q_y = q_now.y();
    row.est_q_z = q_now.z();
    row.est_q_w = q_now.w();

    row.vel_norm = Vs[WINDOW_SIZE].norm();
    row.ba_norm = Bas[WINDOW_SIZE].norm();
    row.bg_norm = Bgs[WINDOW_SIZE].norm();

    // ============================================================
    // 6. VINS pose delta
    //
    // 注意：
    // 這裡一定要先算 q_vins_delta，再更新 reliability_prev_logged_Q。
    // 不可以像舊版一樣太早更新 prev pose。
    // 因為後面 gyro-VINS consistency 需要 q_vins_delta。
    // ============================================================
    row.delta_p_norm = 0.0;
    row.delta_q_deg = 0.0;

    Eigen::Quaterniond q_vins_delta = Eigen::Quaterniond::Identity();

    if (reliability_has_prev_logged_pose)
    {
        row.delta_p_norm =
            (Ps[WINDOW_SIZE] - reliability_prev_logged_P).norm();

        q_vins_delta =
            reliability_prev_logged_Q.conjugate() * q_now;
        q_vins_delta.normalize();

        row.delta_q_deg = Utility::quatAngleDeg(q_vins_delta);
    }

    Eigen::Vector3d vins_rotvec_deg =
        Utility::logSO3(q_vins_delta) * 180.0 / M_PI;

    pending_vins_delta_angle_deg = vins_rotvec_deg.norm();
    pending_vins_rotvec_x_deg = vins_rotvec_deg.x();
    pending_vins_rotvec_y_deg = vins_rotvec_deg.y();
    pending_vins_rotvec_z_deg = vins_rotvec_deg.z();

    // ============================================================
    // 7. gyro-VINS SO(3) consistency
    //
    // pending_gyro_bgcorr_delta_q 由 computePendingImuStats() 先算好。
    // q_err = gyro_delta^{-1} * vins_delta
    // ============================================================
    Eigen::Quaterniond q_gyro_corr = pending_gyro_bgcorr_delta_q;
    q_gyro_corr.normalize();

    Eigen::Quaterniond q_gyro_raw = pending_gyro_raw_delta_q;
    q_gyro_raw.normalize();

    Eigen::Quaterniond q_err =
        q_gyro_corr.conjugate() * q_vins_delta;
    q_err.normalize();

    pending_gyro_vins_so3_diff_deg =
        Utility::quatAngleDeg(q_err);

    Eigen::Vector3d gyro_corr_rotvec_deg =
        Utility::logSO3(q_gyro_corr) * 180.0 / M_PI;

    Eigen::Vector3d gyro_vins_rotvec_diff_deg =
        vins_rotvec_deg - gyro_corr_rotvec_deg;

    pending_gyro_vins_rotvec_diff_x_deg =
        gyro_vins_rotvec_diff_deg.x();
    pending_gyro_vins_rotvec_diff_y_deg =
        gyro_vins_rotvec_diff_deg.y();
    pending_gyro_vins_rotvec_diff_z_deg =
        gyro_vins_rotvec_diff_deg.z();
    pending_gyro_vins_rotvec_diff_norm_deg =
        gyro_vins_rotvec_diff_deg.norm();

    pending_gyro_vins_angle_ratio =
        pending_gyro_bgcorr_delta_angle_deg /
        std::max(pending_vins_delta_angle_deg, 1e-6);

    // ============================================================
    // 8. visual admission state
    // ============================================================
    row.visual_w_pred = visual_w_pred;
    row.visual_gate_pass = visual_gate_pass ? 1 : 0;
    row.visual_alpha = visual_alpha;
    row.visual_has_prediction = visual_has_prediction ? 1 : 0;
    row.visual_soft_target_proxy = visual_soft_target_proxy;

    // ============================================================
    // 9. original IMU statistics
    // ============================================================
    row.imu_sample_count = pending_imu_sample_count;

    row.acc_norm_mean = pending_acc_norm_mean;
    row.acc_norm_std = pending_acc_norm_std;
    row.acc_norm_max = pending_acc_norm_max;

    row.gyr_norm_mean = pending_gyr_norm_mean;
    row.gyr_norm_std = pending_gyr_norm_std;
    row.gyr_norm_max = pending_gyr_norm_max;

    // ============================================================
    // 10. v5 SO(3) gyro integration features
    // ============================================================
    row.gyro_raw_delta_angle_deg =
        pending_gyro_raw_delta_angle_deg;
    row.gyro_raw_rotvec_x_deg =
        pending_gyro_raw_rotvec_x_deg;
    row.gyro_raw_rotvec_y_deg =
        pending_gyro_raw_rotvec_y_deg;
    row.gyro_raw_rotvec_z_deg =
        pending_gyro_raw_rotvec_z_deg;

    row.gyro_raw_delta_q_w = q_gyro_raw.w();
    row.gyro_raw_delta_q_x = q_gyro_raw.x();
    row.gyro_raw_delta_q_y = q_gyro_raw.y();
    row.gyro_raw_delta_q_z = q_gyro_raw.z();

    row.gyro_bgcorr_delta_angle_deg =
        pending_gyro_bgcorr_delta_angle_deg;
    row.gyro_bgcorr_rotvec_x_deg =
        pending_gyro_bgcorr_rotvec_x_deg;
    row.gyro_bgcorr_rotvec_y_deg =
        pending_gyro_bgcorr_rotvec_y_deg;
    row.gyro_bgcorr_rotvec_z_deg =
        pending_gyro_bgcorr_rotvec_z_deg;

    row.gyro_bgcorr_delta_q_w = q_gyro_corr.w();
    row.gyro_bgcorr_delta_q_x = q_gyro_corr.x();
    row.gyro_bgcorr_delta_q_y = q_gyro_corr.y();
    row.gyro_bgcorr_delta_q_z = q_gyro_corr.z();

    row.gyro_abs_angle_sum_deg =
        pending_gyro_abs_angle_sum_deg;

    row.gyr_x_mean = pending_gyr_x_mean;
    row.gyr_y_mean = pending_gyr_y_mean;
    row.gyr_z_mean = pending_gyr_z_mean;

    row.gyr_x_std = pending_gyr_x_std;
    row.gyr_y_std = pending_gyr_y_std;
    row.gyr_z_std = pending_gyr_z_std;

    row.gyr_x_max_abs = pending_gyr_x_max_abs;
    row.gyr_y_max_abs = pending_gyr_y_max_abs;
    row.gyr_z_max_abs = pending_gyr_z_max_abs;

    row.gyr_bgcorr_x_mean = pending_gyr_bgcorr_x_mean;
    row.gyr_bgcorr_y_mean = pending_gyr_bgcorr_y_mean;
    row.gyr_bgcorr_z_mean = pending_gyr_bgcorr_z_mean;
    row.gyr_bgcorr_norm_mean = pending_gyr_bgcorr_norm_mean;

    // ============================================================
    // 11. v5 IMU timing quality
    // ============================================================
    row.imu_dt_mean = pending_imu_dt_mean;
    row.imu_dt_std = pending_imu_dt_std;
    row.imu_dt_min = pending_imu_dt_min;
    row.imu_dt_max = pending_imu_dt_max;
    row.imu_dt_gap_max = pending_imu_dt_gap_max;
    row.imu_total_dt = pending_imu_total_dt;
    row.imu_image_dt_diff = pending_imu_image_dt_diff;

    // ============================================================
    // 12. v5 VINS delta quaternion / rotvec
    // ============================================================
    row.vins_delta_angle_deg =
        pending_vins_delta_angle_deg;
    row.vins_rotvec_x_deg =
        pending_vins_rotvec_x_deg;
    row.vins_rotvec_y_deg =
        pending_vins_rotvec_y_deg;
    row.vins_rotvec_z_deg =
        pending_vins_rotvec_z_deg;

    row.vins_delta_q_w = q_vins_delta.w();
    row.vins_delta_q_x = q_vins_delta.x();
    row.vins_delta_q_y = q_vins_delta.y();
    row.vins_delta_q_z = q_vins_delta.z();

    // ============================================================
    // 13. v5 gyro-VINS consistency
    // ============================================================
    row.gyro_vins_so3_diff_deg =
        pending_gyro_vins_so3_diff_deg;

    row.gyro_vins_rotvec_diff_x_deg =
        pending_gyro_vins_rotvec_diff_x_deg;
    row.gyro_vins_rotvec_diff_y_deg =
        pending_gyro_vins_rotvec_diff_y_deg;
    row.gyro_vins_rotvec_diff_z_deg =
        pending_gyro_vins_rotvec_diff_z_deg;
    row.gyro_vins_rotvec_diff_norm_deg =
        pending_gyro_vins_rotvec_diff_norm_deg;

    row.gyro_vins_angle_ratio =
        pending_gyro_vins_angle_ratio;

    // ============================================================
    // 14. v5 visual flow vs gyro rotation consistency
    //
    // 這些值由 computePendingVisionGyroConsistencyStats()
    // 在 processMeasurements() 裡先算好。
    // ============================================================
    row.vg_flow_valid_count =
        pending_vg_flow_valid_count;

    row.vg_flow_obs_mean =
        pending_vg_flow_obs_mean;
    row.vg_flow_obs_std =
        pending_vg_flow_obs_std;
    row.vg_flow_obs_p90 =
        pending_vg_flow_obs_p90;

    row.vg_flow_pred_mean =
        pending_vg_flow_pred_mean;
    row.vg_flow_pred_std =
        pending_vg_flow_pred_std;
    row.vg_flow_pred_p90 =
        pending_vg_flow_pred_p90;

    row.vg_flow_res_mean =
        pending_vg_flow_res_mean;
    row.vg_flow_res_std =
        pending_vg_flow_res_std;
    row.vg_flow_res_p90 =
        pending_vg_flow_res_p90;

    row.vg_flow_res_flip_mean =
        pending_vg_flow_res_flip_mean;
    row.vg_flow_res_min_mean =
        pending_vg_flow_res_min_mean;

    row.vg_flow_cos_mean =
        pending_vg_flow_cos_mean;
    row.vg_flow_cos_median =
        pending_vg_flow_cos_median;

    row.vg_flow_mag_ratio_median =
        pending_vg_flow_mag_ratio_median;
    row.vg_flow_mag_ratio_p90 =
        pending_vg_flow_mag_ratio_p90;

    // ============================================================
    // 15. FeatureManager / geometry statistics
    // ============================================================
    row.avg_track_length = computeAverageTrackLength();

    row.track_len_min = pending_track_len_min;
    row.track_len_max = pending_track_len_max;
    row.track_len_std = pending_track_len_std;
    row.track_len_p90 = pending_track_len_p90;

    row.good_depth_count = pending_good_depth_count;
    row.bad_depth_count = pending_bad_depth_count;
    row.depth_mean = pending_depth_mean;
    row.depth_min = pending_depth_min;
    row.depth_max = pending_depth_max;
    row.depth_std = pending_depth_std;

    // ============================================================
    // 16. extrinsic telemetry: cam0
    // ============================================================
    {
        const int cam = 0;

        Eigen::Quaterniond q_cam(ric[cam]);
        q_cam.normalize();

        row.cam0_tic_x = tic[cam].x();
        row.cam0_tic_y = tic[cam].y();
        row.cam0_tic_z = tic[cam].z();

        row.cam0_q_x = q_cam.x();
        row.cam0_q_y = q_cam.y();
        row.cam0_q_z = q_cam.z();
        row.cam0_q_w = q_cam.w();

        if (reliability_initial_extrinsic_ready)
        {
            row.cam0_init_delta_t_norm =
                (tic[cam] - reliability_initial_tic[cam]).norm();

            row.cam0_init_delta_r_deg =
                rotationDistanceDeg(reliability_initial_ric[cam], ric[cam]);
        }
    }

    // ============================================================
    // 17. extrinsic telemetry: cam1
    // ============================================================
    if (NUM_OF_CAM > 1)
    {
        const int cam = 1;

        Eigen::Quaterniond q_cam(ric[cam]);
        q_cam.normalize();

        row.cam1_tic_x = tic[cam].x();
        row.cam1_tic_y = tic[cam].y();
        row.cam1_tic_z = tic[cam].z();

        row.cam1_q_x = q_cam.x();
        row.cam1_q_y = q_cam.y();
        row.cam1_q_z = q_cam.z();
        row.cam1_q_w = q_cam.w();

        if (reliability_initial_extrinsic_ready)
        {
            row.cam1_init_delta_t_norm =
                (tic[cam] - reliability_initial_tic[cam]).norm();

            row.cam1_init_delta_r_deg =
                rotationDistanceDeg(reliability_initial_ric[cam], ric[cam]);
        }
    }

    // ============================================================
    // 18. append row
    // ============================================================
    reliability_feature_logger.append(row);

    // ============================================================
    // 19. update previous logged pose
    //
    // 注意：
    // 一定放最後。這樣本次 row 的 delta_q / gyro-VINS diff
    // 都是相對上一筆 logged pose，而不是相對自己。
    // ============================================================
    reliability_prev_logged_P = Ps[WINDOW_SIZE];
    reliability_prev_logged_Q = q_now;
    reliability_has_prev_logged_pose = true;
}

void Estimator::fastPredictIMU(double t, Eigen::Vector3d linear_acceleration, Eigen::Vector3d angular_velocity)
{
    double dt = t - latest_time;
    latest_time = t;
    Eigen::Vector3d un_acc_0 = latest_Q * (latest_acc_0 - latest_Ba) - g;
    Eigen::Vector3d un_gyr = 0.5 * (latest_gyr_0 + angular_velocity) - latest_Bg;
    latest_Q = latest_Q * Utility::deltaQ(un_gyr * dt);
    Eigen::Vector3d un_acc_1 = latest_Q * (linear_acceleration - latest_Ba) - g;
    Eigen::Vector3d un_acc = 0.5 * (un_acc_0 + un_acc_1);
    latest_P = latest_P + dt * latest_V + 0.5 * dt * dt * un_acc;
    latest_V = latest_V + dt * un_acc;
    latest_acc_0 = linear_acceleration;
    latest_gyr_0 = angular_velocity;
}

void Estimator::updateLatestStates()
{
    mPropagate.lock();
    latest_time = Headers[frame_count] + td;
    latest_P = Ps[frame_count];
    latest_Q = Rs[frame_count];
    latest_V = Vs[frame_count];
    latest_Ba = Bas[frame_count];
    latest_Bg = Bgs[frame_count];
    latest_acc_0 = acc_0;
    latest_gyr_0 = gyr_0;
    mBuf.lock();
    queue<pair<double, Eigen::Vector3d>> tmp_accBuf = accBuf;
    queue<pair<double, Eigen::Vector3d>> tmp_gyrBuf = gyrBuf;
    mBuf.unlock();
    while(!tmp_accBuf.empty())
    {
        double t = tmp_accBuf.front().first;
        Eigen::Vector3d acc = tmp_accBuf.front().second;
        Eigen::Vector3d gyr = tmp_gyrBuf.front().second;
        fastPredictIMU(t, acc, gyr);
        tmp_accBuf.pop();
        tmp_gyrBuf.pop();
    }
    mPropagate.unlock();
}