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
#pragma once
 
#include <thread>
#include <mutex>
#include <std_msgs/msg/header.h>
#include <std_msgs/msg/float32.h>
#include <ceres/ceres.h>
#include <unordered_map>
#include <queue>
#include <deque>
#include <opencv2/core/eigen.hpp>
#include <eigen3/Eigen/Dense>
#include <eigen3/Eigen/Geometry>

#include "parameters.h"
#include "feature_manager.h"
#include "../utility/utility.h"
#include "../utility/tic_toc.h"
#include "../initial/solve_5pts.h"
#include "../initial/initial_sfm.h"
#include "../initial/initial_alignment.h"
#include "../initial/initial_ex_rotation.h"
#include "../factor/imu_factor.h"
#include "../factor/pose_local_parameterization.h"
#include "../factor/marginalization_factor.h"
#include "../factor/projectionTwoFrameOneCamFactor.h"
#include "../factor/projectionTwoFrameTwoCamFactor.h"
#include "../factor/projectionOneFrameTwoCamFactor.h"
#include "../factor/fog_rotation_factor.h"      // P1 (fwvio) explicit factors
#include "../factor/wheel_forward_factor.h"
#include "../factor/nhc_factor.h"
#include "../factor/wheel_preintegration.h"     // P1-Wheel v3.3 SE(2) preintegration
#include "../factor/wheel_se2_factor.h"
#include "../factor/fog_yaw_preintegration.h"   // P1-FogWheel v1 FOG yaw preintegration
#include "../factor/fog_yaw_factor.h"
#include "../featureTracker/feature_tracker.h"
#include "reliability_logger.h"
#include "perfeat_logger.h"   // P1-Reliability R1: per-feature read-only logging
#include <string>
#include <functional>

#define ROS_INFO RCUTILS_LOG_INFO
#define ROS_WARN RCUTILS_LOG_WARN
#define ROS_ERROR RCUTILS_LOG_ERROR


class Estimator
{
  public:
    Estimator();
    ~Estimator();
    void setParameter();

    // ===== visual admission / debug state =====
    double visual_w_pred;                 // 模型原始 reliability score [0, 1]
    bool visual_gate_pass;                // 是否通過 hard gate

    // backend 最終使用的 visual information weight
    // 注意：visual_alpha 不再代表 raw w_pred
    double visual_alpha;

    // uncertainty mapping debug
    double visual_alpha_target;           // smoothing 前的 target alpha
    double visual_sigma_px;               // 由 w_pred 轉出的 visual measurement sigma(px)
    bool visual_alpha_initialized;        // smoothing 是否初始化

    double visual_soft_target_proxy;      // 只做 debug 對照用
    bool visual_has_prediction;           // 這一幀是否有外部預測
    bool enable_visual_admission;         // 是否啟用 admission 機制
    double visual_gate_tau;               // hard gate 門檻

    enum VisualAdmissionMode
    {
        VISUAL_ALWAYS = 0,
        HARD_GATE = 1,
        SOFT_WEIGHT = 2,
        GATE_AND_WEIGHT = 3
    };

    VisualAdmissionMode visual_admission_mode;

    // ===== internal alpha schedule (no external publisher needed) =====
    bool visual_internal_alpha_schedule_enable;
    double visual_internal_alpha_value;
    double visual_internal_alpha_start_ts;
    double visual_internal_alpha_end_ts;
    void setInternalAlphaSchedule(bool enable, double alpha_value, double start_ts, double end_ts);

    // ===== integrity: latest-pose covariance (logging only) =====
    double latest_pose_cov_pos_trace;
    double latest_pose_cov_rot_trace;

    // ===== runtime debug counters =====
    int tracked_feature_count_raw;        // image.size()
    int tracked_feature_count_mgr;        // f_manager.getFeatureCount()
    bool current_is_keyframe;

    int outlier_count_last;
    int inlier_count_last;
    double outlier_ratio_last;

    bool failure_detected_last;
    double solver_time_ms_last;

    // interface
    void initFirstPose(Eigen::Vector3d p, Eigen::Matrix3d r);
    void inputIMU(double t, const Vector3d &linearAcceleration, const Vector3d &angularVelocity);
    void inputWheel(double t, double dl, double dr, double df);   // P1-Wheel
    void inputFogYaw(double t, double dyaw, double dt);           // P1-FogWheel
    bool fogYawAvailable(double t);
    void buildFogYawPreint(int idx, double t0, double t1);
    void inputFeature(double t, const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame);
    void inputImage(double t, const cv::Mat &_img, const cv::Mat &_img1 = cv::Mat());
    void processIMU(double t, double dt, const Vector3d &linear_acceleration, const Vector3d &angular_velocity);
    void processImage(const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &image, const double header);
    void processMeasurements();
    void changeSensorType(int use_imu, int use_stereo);

    // visual admission helpers
    void setVisualAdmissionConfig(bool enable, VisualAdmissionMode mode, double tau);
    void setVisualAdmissionPrediction(double w_pred, double soft_target_proxy = -1.0);
    void clearVisualAdmissionPrediction();
    void resetVisualAdmissionState();
    void updateVisualDebugPre(const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &image);
    void updateVisualDebugPost(const set<int> &removeIndex, bool failure_flag, double solver_ms);
    double selectVisualAlpha() const;
    void applyVisualResidualWeight();

    // internal
    void clearState();
    bool initialStructure();
    bool visualInitialAlign();
    bool relativePose(Matrix3d &relative_R, Vector3d &relative_T, int &l);
    void slideWindow();
    void slideWindowNew();
    void slideWindowOld();
    void optimization();
    void vector2double();
    void double2vector();
    bool failureDetection();
    bool getIMUInterval(double t0, double t1, vector<pair<double, Eigen::Vector3d>> &accVector, 
                                              vector<pair<double, Eigen::Vector3d>> &gyrVector);
    void getPoseInWorldFrame(Eigen::Matrix4d &T);
    void getPoseInWorldFrame(int index, Eigen::Matrix4d &T);
    void predictPtsInNextFrame();
    void outliersRejection(set<int> &removeIndex);
    double reprojectionError(Matrix3d &Ri, Vector3d &Pi, Matrix3d &rici, Vector3d &tici,
                                     Matrix3d &Rj, Vector3d &Pj, Matrix3d &ricj, Vector3d &ticj, 
                                     double depth, Vector3d &uvi, Vector3d &uvj);
    void updateLatestStates();
    void fastPredictIMU(double t, Eigen::Vector3d linear_acceleration, Eigen::Vector3d angular_velocity);
    bool IMUAvailable(double t);
    void initFirstIMUPose(vector<pair<double, Eigen::Vector3d>> &accVector);
    
    // ===== reliability CSV logger helpers =====
    
    void setupReliabilityLogger();

    void computePendingFeatureStats(
        const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame,
        double feature_tracker_time_ms,
        double image_timestamp,
        int image_width,
        int image_height);

    void computePendingImuStats(
        const vector<pair<double, Eigen::Vector3d>> &accVector,
        const vector<pair<double, Eigen::Vector3d>> &gyrVector);

    void computePendingVisionGyroConsistencyStats(
        const map<int, vector<pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame);

    double computeAverageTrackLength() const;

    void computeManagerFeatureStats();

    std::string inferFailureReasonProxy(bool failure_flag) const;

    void writeReliabilityFeatureRow(double header);
    
    // ===== realtime reliability inference topic bridge =====
    // 讓 rosNodeTest.cpp 設定一個 callback，Estimator 每次產生 feature 後可以把 JSON 丟出去
    void setReliabilityFeatureJsonCallback(std::function<void(const std::string &)> cb);

    // 把目前 estimator 內部的 reliability feature 組成 JSON string
    std::string buildReliabilityFeatureJson(double header) const;

    enum SolverFlag
    {
        INITIAL,
        NON_LINEAR
    };

    enum MarginalizationFlag
    {
        MARGIN_OLD = 0,
        MARGIN_SECOND_NEW = 1
    };

    std::mutex mProcess;
    std::mutex mBuf;
    std::mutex mPropagate;
    queue<pair<double, Eigen::Vector3d>> accBuf;
    queue<pair<double, Eigen::Vector3d>> gyrBuf;
    // P1-Wheel: raw measurements stored BY TIMESTAMP (never by sliding-window index).
    struct WheelMeasurement { double timestamp; double delta_left; double delta_right; double delta_forward; };
    std::deque<WheelMeasurement> wheel_buffer;
    std::mutex mWheel;
    // P1-FogWheel: FOG yaw raw measurements by timestamp.
    struct FogYawMeasurement { double timestamp; double dyaw; double dt; };
    std::deque<FogYawMeasurement> fog_buffer;
    std::mutex mFog;
    FogYawPreintegration *fog_yaw_preint[(WINDOW_SIZE + 1)] = {nullptr};
    double fog_arw_ = 3.49e-6, fog_yaw_scale_ = 1.0;   // FOG ARW [rad/sqrt(s)], yaw sqrt_info scale (YAML in F4)
    queue<pair<double, map<int, vector<pair<int, Eigen::Matrix<double, 7, 1> > > > > > featureBuf;
    double prevTime, curTime;
    bool openExEstimation;

    std::thread trackThread;
    std::thread processThread;

    FeatureTracker featureTracker;

    SolverFlag solver_flag;
    MarginalizationFlag  marginalization_flag;
    Vector3d g;

    Matrix3d ric[2];
    Vector3d tic[2];

    Vector3d        Ps[(WINDOW_SIZE + 1)];
    Vector3d        Vs[(WINDOW_SIZE + 1)];
    Matrix3d        Rs[(WINDOW_SIZE + 1)];
    Vector3d        Bas[(WINDOW_SIZE + 1)];
    Vector3d        Bgs[(WINDOW_SIZE + 1)];
    double td;

    Matrix3d back_R0, last_R, last_R0;
    Vector3d back_P0, last_P, last_P0;
    double Headers[(WINDOW_SIZE + 1)];

    IntegrationBase *pre_integrations[(WINDOW_SIZE + 1)];
    // P1-Wheel v3.3 C2: immutable SE(2) wheel preintegration per keyframe interval (mirrors pre_integrations).
    WheelPreintegration *wheel_pre_integrations[(WINDOW_SIZE + 1)] = {nullptr};
    bool wheelAvailable(double t);
    void buildWheelPreint(int idx, double t0, double t1);
    // frozen WHEEL_MODEL.md params (YAML-overridden in C3)
    double wheel_b_ = 1.52439, wheel_sigmaL_ = 0.02, wheel_sigmaR_ = 0.02, wheel_yaw_scale_ = 1.0, wheel_huber_ = 1.0;
    Vector3d acc_0, gyr_0;

    vector<double> dt_buf[(WINDOW_SIZE + 1)];
    vector<Vector3d> linear_acceleration_buf[(WINDOW_SIZE + 1)];
    vector<Vector3d> angular_velocity_buf[(WINDOW_SIZE + 1)];

    int frame_count;
    int sum_of_outlier, sum_of_back, sum_of_front, sum_of_invalid;
    int inputImageCnt;

    FeatureManager f_manager;
    MotionEstimator m_estimator;
    InitialEXRotation initial_ex_rotation;

    bool first_imu;
    bool is_valid, is_key;
    bool failure_occur;

    vector<Vector3d> point_cloud;
    vector<Vector3d> margin_cloud;
    vector<Vector3d> key_poses;
    double initial_timestamp;


    double para_Pose[WINDOW_SIZE + 1][SIZE_POSE];
    double para_SpeedBias[WINDOW_SIZE + 1][SIZE_SPEEDBIAS];
    double para_Feature[NUM_OF_F][SIZE_FEATURE];
    double para_Ex_Pose[2][SIZE_POSE];
    double para_Retrive_Pose[SIZE_POSE];
    double para_Td[1][1];
    double para_Tr[1][1];

    int loop_window_index;

    MarginalizationInfo *last_marginalization_info;
    vector<double *> last_marginalization_parameter_blocks;

    map<double, ImageFrame> all_image_frame;
    IntegrationBase *tmp_pre_integration;

    Eigen::Vector3d initP;
    Eigen::Matrix3d initR;

    double latest_time;
    Eigen::Vector3d latest_P, latest_V, latest_Ba, latest_Bg, latest_acc_0, latest_gyr_0;
    Eigen::Quaterniond latest_Q;

    bool initFirstPoseFlag;
    bool initThreadFlag;
    // ===== reliability CSV logger state =====

    ReliabilityCsvLogger reliability_feature_logger;

    bool reliability_logger_ready = false;

    // ===== P1-Reliability R1: per-feature read-only logger (default OFF) =====
    PerFeatCsvLogger perfeat_logger;
    bool perfeat_logger_ready = false;
    long long perfeat_update_id = 0;
    std::string perfeat_csv_path = "/tmp/perfeat_reliability_vins.csv";
    void setupPerFeatLogger();
    void writePerFeatRows(double header);

    // ===== P1-Reliability R3b: per-feature reliability weight =====
    std::map<int, double> track_rel_;     // persistent per-track reliability (temporal memory)
    std::map<int, double> feat_weight_cur_;  // feature_id -> sqrt(reliability) for the current optimization
    bool reliability_intr_ready_ = false;
    double rel_fx_ = 0, rel_fy_ = 0, rel_cx_ = 0, rel_cy_ = 0;
    void computeFeatureReliability();     // fills feat_weight_cur_ (call at top of optimization when enabled)

    // §2 controlled dynamic injection (leak-free; coherent synthetic moving block; ids >= INJ_ID_BASE)
    static const int INJ_ID_BASE = 900000;
    std::vector<std::pair<double,double>> inj_nxny_;   // current synthetic block normalized positions
    bool inj_init_ = false;
    void injectDynamicFeatures(std::map<int, std::vector<std::pair<int, Eigen::Matrix<double, 7, 1>>>> &featureFrame, double t);

    std::string reliability_run_id = "run_001";
    std::string reliability_dataset_name = "kaist";
    std::string reliability_sequence_name = "unknown_sequence";

    std::string reliability_feature_csv_path =
        "/tmp/reliability_features_vins.csv";


    
    long long reliability_update_id = 0;

    double reliability_prev_image_time = -1.0;

    double pending_feature_tracker_time_ms = 0.0;

    double pending_img_dt_sec = 0.0;

    double pending_mean_track_vel_px = 0.0;
    double pending_median_track_vel_px = 0.0;
    double pending_min_track_vel_px = 0.0;
    double pending_max_track_vel_px = 0.0;
    double pending_std_track_vel_px = 0.0;
    double pending_p90_track_vel_px = 0.0;

    double pending_coverage_4x4 = 0.0;
    double pending_coverage_8x8 = 0.0;
    int pending_occupied_cells_4x4 = 0;
    int pending_occupied_cells_8x8 = 0;
    double pending_entropy_4x4 = 0.0;
    double pending_entropy_8x8 = 0.0;

    int pending_imu_sample_count = 0;
    double pending_acc_norm_mean = 0.0;
    double pending_acc_norm_std = 0.0;
    double pending_acc_norm_max = 0.0;
    double pending_gyr_norm_mean = 0.0;
    double pending_gyr_norm_std = 0.0;
    double pending_gyr_norm_max = 0.0;
    
    // ===== v5 SO(3) gyro integration =====
    Eigen::Quaterniond pending_gyro_raw_delta_q;
    Eigen::Quaterniond pending_gyro_bgcorr_delta_q;

    // ===== P1 (fwvio) factor data buffers — keyed by keyframe index j (rel to i=j-1).
    // Filled by the player->estimator FOG/wheel plumbing (P1 Task 2). Empty => factor guards skip,
    // so flag-ON is a safe no-op until plumbing lands; flag-OFF (default) = baseline unchanged.

    double pending_gyro_raw_delta_angle_deg;
    double pending_gyro_raw_rotvec_x_deg;
    double pending_gyro_raw_rotvec_y_deg;
    double pending_gyro_raw_rotvec_z_deg;

    double pending_gyro_bgcorr_delta_angle_deg;
    double pending_gyro_bgcorr_rotvec_x_deg;
    double pending_gyro_bgcorr_rotvec_y_deg;
    double pending_gyro_bgcorr_rotvec_z_deg;

    double pending_gyro_abs_angle_sum_deg;

    double pending_gyr_x_mean;
    double pending_gyr_y_mean;
    double pending_gyr_z_mean;
    double pending_gyr_x_std;
    double pending_gyr_y_std;
    double pending_gyr_z_std;
    double pending_gyr_x_max_abs;
    double pending_gyr_y_max_abs;
    double pending_gyr_z_max_abs;

    double pending_gyr_bgcorr_x_mean;
    double pending_gyr_bgcorr_y_mean;
    double pending_gyr_bgcorr_z_mean;
    double pending_gyr_bgcorr_norm_mean;

    // ===== v5 IMU timing quality =====
    double pending_imu_dt_mean;
    double pending_imu_dt_std;
    double pending_imu_dt_min;
    double pending_imu_dt_max;
    double pending_imu_dt_gap_max;
    double pending_imu_total_dt;
    double pending_imu_image_dt_diff;

    // ===== v5 gyro vs VINS consistency =====
    double pending_vins_delta_angle_deg;
    double pending_vins_rotvec_x_deg;
    double pending_vins_rotvec_y_deg;
    double pending_vins_rotvec_z_deg;

    double pending_gyro_vins_so3_diff_deg;
    double pending_gyro_vins_rotvec_diff_x_deg;
    double pending_gyro_vins_rotvec_diff_y_deg;
    double pending_gyro_vins_rotvec_diff_z_deg;
    double pending_gyro_vins_rotvec_diff_norm_deg;
    double pending_gyro_vins_angle_ratio;

    // ===== v5 visual flow vs gyro rotation consistency =====
    int pending_vg_flow_valid_count;
    double pending_vg_flow_obs_mean;
    double pending_vg_flow_obs_std;
    double pending_vg_flow_obs_p90;

    double pending_vg_flow_pred_mean;
    double pending_vg_flow_pred_std;
    double pending_vg_flow_pred_p90;

    double pending_vg_flow_res_mean;
    double pending_vg_flow_res_std;
    double pending_vg_flow_res_p90;

    double pending_vg_flow_res_flip_mean;
    double pending_vg_flow_res_min_mean;

    double pending_vg_flow_cos_mean;
    double pending_vg_flow_cos_median;

    double pending_vg_flow_mag_ratio_median;
    double pending_vg_flow_mag_ratio_p90;

    double pending_track_len_min = 0.0;
    double pending_track_len_max = 0.0;
    double pending_track_len_std = 0.0;
    double pending_track_len_p90 = 0.0;

    int pending_good_depth_count = 0;
    int pending_bad_depth_count = 0;
    double pending_depth_mean = 0.0;
    double pending_depth_min = 0.0;
    double pending_depth_max = 0.0;
    double pending_depth_std = 0.0;

    bool reliability_has_prev_logged_pose = false;
    Eigen::Vector3d reliability_prev_logged_P = Eigen::Vector3d::Zero();
    Eigen::Quaterniond reliability_prev_logged_Q = Eigen::Quaterniond::Identity();

    bool reliability_initial_extrinsic_ready = false;
    Eigen::Matrix3d reliability_initial_ric[2];
    Eigen::Vector3d reliability_initial_tic[2];
    double reliability_initial_td = 0.0;
    // callback owned by rosNodeTest.cpp, used to publish /vins_admission/features_json
    std::function<void(const std::string &)> reliability_feature_json_callback;
};