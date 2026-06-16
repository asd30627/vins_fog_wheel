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

#include <cstdlib>
#include "parameters.h"
#include <regex>
#include <fstream>
#include <sstream>
#include <algorithm>

double INIT_DEPTH;
double MIN_PARALLAX;
double ACC_N, ACC_W;
double GYR_N, GYR_W;

std::vector<Eigen::Matrix3d> RIC;
std::vector<Eigen::Vector3d> TIC;

Eigen::Vector3d G{0.0, 0.0, 9.8};

int USE_GPU;
int USE_GPU_ACC_FLOW;
int USE_GPU_CERES;

double BIAS_ACC_THRESHOLD;
double BIAS_GYR_THRESHOLD;
double SOLVER_TIME;
int NUM_ITERATIONS;
int ESTIMATE_EXTRINSIC;
int ESTIMATE_TD;
int ROLLING_SHUTTER;
std::string EX_CALIB_RESULT_PATH;
std::string IMU_NOISE_MODE;
std::string VINS_RESULT_PATH;
std::string OUTPUT_FOLDER;
std::string IMU_TOPIC;
int ROW, COL;
double TD;
int NUM_OF_CAM;
int STEREO;
int USE_IMU;
int MULTIPLE_THREAD;
int SAVE_RELIABILITY_FEATURES = 1;
int RELIABILITY_LOG_EVERY_N = 1;
int SAVE_PERFEAT_RELIABILITY = 0;   // P1-Reliability R1: per-feature read-only log, default OFF
// P1-Reliability R2: build+log wheel/FOG preintegration as a consistency REFERENCE without adding the factor to
// the optimization (keeps the reference INDEPENDENT of the estimator pose). Default OFF.
int WHEEL_REFERENCE_ONLY = 0;
int FOG_YAW_REFERENCE_ONLY = 0;
// P1-Reliability R3b: per-feature reliability weight into the visual factor. Default OFF.
int FEATURE_RELIABILITY_ENABLE = 0;
double RELIABILITY_KAPPA = 8.0;          // gentler suppression beyond the threshold (offline-tuned)
double RELIABILITY_D2_THRESH = 5.99;     // chi2(2).95: features with d2 below this are kept at reliability 1.0
double RELIABILITY_SIGMA_UV = 3.0;
double RELIABILITY_FLOOR = 0.05;
int RELIABILITY_KEEPN = 30;
double RELIABILITY_EMA_DOWN = 0.7;   // fast-down: ema = DOWN*new + (1-DOWN)*old  when new < old
double RELIABILITY_EMA_UP = 0.1;     // slow-up:   ema = UP*new   + (1-UP)*old    when new >= old
int POSE_COV_ENABLE = 0;   // DEFAULT OFF — expensive [pose-cov] DENSE_SVD diagnostic (Paper-2 Sigma_A only)
int POSE_COV_EVERY_N = 1;
// P1 (fwvio) factor switches — DEFAULT OFF. flags-off => baseline behaviour unchanged (bit-invariance guardrail).
int FOG_FACTOR_ENABLE = 0;
int WHEEL_FACTOR_ENABLE = 0;
int NHC_ENABLE = 0;
int WHEEL_MODE_SE2 = 1;   // 1=SE(2) default, 0=forward_only ablation (env WHEEL_MODE)
int FOG_YAW_ENABLE = 0;   // P1-FogWheel FOG yaw factor switch, default 0 (env FOG_YAW_ENABLE)
map<int, Eigen::Vector3d> pts_gt;
std::string IMAGE0_TOPIC, IMAGE1_TOPIC;
std::string FISHEYE_MASK;
std::vector<std::string> CAM_NAMES;
int MAX_CNT;
int MIN_DIST;
double F_THRESHOLD;
int SHOW_TRACK;
int FLOW_BACK;

static bool parseVehicleTxtToT(const std::string &path, Eigen::Matrix4d &T);
static bool parseRightYamlBaseline(const std::string &path, double &baseline);
static bool inferSequenceFromOutputPath(const std::string &output_path, std::string &seq_name);
static bool loadSequenceSpecificExtrinsic(
    const std::string &output_folder,
    Eigen::Matrix4d &T_b_c0,
    Eigen::Matrix4d &T_b_c1);

static bool parseOpenCvBodyTFromFile(
    const std::string &path,
    const std::string &key,
    Eigen::Matrix4d &T);

static bool loadFixedExtrinsicFromBaselineResult(
    const std::string &output_folder,
    Eigen::Matrix4d &T_b_c0,
    Eigen::Matrix4d &T_b_c1);

static Eigen::Matrix4d openVinsKaistT_LtoR();

template <typename T>
T readParam(rclcpp::Node::SharedPtr n, std::string name)
{
    T ans;
    if (n->get_parameter(name, ans))
    {
        ROS_INFO("Loaded %s: ", name);
        std::cout << ans << std::endl;
    }
    else
    {
        ROS_ERROR("Failed to load %s", name);
        rclcpp::shutdown();
    }
    return ans;
}

static void applyImuNoiseProfile(const std::string &mode, cv::FileStorage &fsSettings)
{
    if (mode == "xsens")
    {
        // ACC_N = 0.01;
        // ACC_W = 0.0008;
        // GYR_N = 0.0005;
        // GYR_W = 0.0001;
        ACC_N = 0.1;
        ACC_W = 0.0005;
        GYR_N = 0.001;
        GYR_W = 0.0001;
        ROS_WARN("Use built-in IMU noise profile: xsens");
    }
    else if (mode == "fog_xsens")
    {
        ACC_N = 0.1;
        ACC_W = 0.0005;
        GYR_N = 0.001;
        GYR_W = 0.00001;
        ROS_WARN("Use built-in IMU noise profile: fog_xsens");
    }
    else if (mode == "custom")
    {
        ACC_N = fsSettings["acc_n"];
        ACC_W = fsSettings["acc_w"];
        GYR_N = fsSettings["gyr_n"];
        GYR_W = fsSettings["gyr_w"];
        ROS_WARN("Use custom IMU noise profile from YAML");
    }
    else
    {
        ROS_WARN("Unknown imu_noise_mode=%s, fallback to custom", mode.c_str());
        ACC_N = fsSettings["acc_n"];
        ACC_W = fsSettings["acc_w"];
        GYR_N = fsSettings["gyr_n"];
        GYR_W = fsSettings["gyr_w"];
    }
}

void readParameters(std::string config_file)
{
    FILE *fh = fopen(config_file.c_str(),"r");
    if(fh == NULL){
        ROS_WARN("config_file dosen't exist; wrong config_file path");
        // ROS_BREAK();
        return;          
    }
    fclose(fh);

    cv::FileStorage fsSettings(config_file, cv::FileStorage::READ);
    if(!fsSettings.isOpened())
    {
        std::cerr << "ERROR: Wrong path to settings" << std::endl;
    }

    fsSettings["image0_topic"] >> IMAGE0_TOPIC;
    fsSettings["image1_topic"] >> IMAGE1_TOPIC;
    MAX_CNT = fsSettings["max_cnt"];
    MIN_DIST = fsSettings["min_dist"];
    F_THRESHOLD = fsSettings["F_threshold"];
    SHOW_TRACK = fsSettings["show_track"];
    FLOW_BACK = fsSettings["flow_back"];

    MULTIPLE_THREAD = fsSettings["multiple_thread"];

    // ===== reliability / research telemetry logging =====
    // 預設開啟，舊 YAML 沒寫也不會爆
    SAVE_RELIABILITY_FEATURES = 1;
    RELIABILITY_LOG_EVERY_N = 1;

    if (!fsSettings["save_reliability_features"].empty())
        SAVE_RELIABILITY_FEATURES = (int)fsSettings["save_reliability_features"];

    if (!fsSettings["reliability_log_every_n"].empty())
        RELIABILITY_LOG_EVERY_N = (int)fsSettings["reliability_log_every_n"];

    if (RELIABILITY_LOG_EVERY_N < 1)
        RELIABILITY_LOG_EVERY_N = 1;

    ROS_WARN("SAVE_RELIABILITY_FEATURES: %d", SAVE_RELIABILITY_FEATURES);
    ROS_WARN("RELIABILITY_LOG_EVERY_N: %d", RELIABILITY_LOG_EVERY_N);

    // ===== P1-Reliability R1: per-feature read-only logging — DEFAULT OFF =====
    // Pure diagnostic (one row per tracked feature per keyframe), never feeds optimization.
    // Off => bit-identical to p1-fogwheel-v1-codefreeze. Env REL_PERFEAT_LOG / config override.
    SAVE_PERFEAT_RELIABILITY = 0;
    if (!fsSettings["save_perfeat_reliability"].empty())
        SAVE_PERFEAT_RELIABILITY = (int)fsSettings["save_perfeat_reliability"];
    // env override (enable OR disable) — keeps default OFF; lets gate runs toggle without editing config.
    if (const char* e = std::getenv("REL_PERFEAT_LOG"))
    {
        std::string v(e);
        if (v == "1" || v == "true" || v == "True" || v == "ON" || v == "on")
            SAVE_PERFEAT_RELIABILITY = 1;
        else if (v == "0" || v == "false" || v == "False" || v == "OFF" || v == "off")
            SAVE_PERFEAT_RELIABILITY = 0;
    }
    ROS_WARN("SAVE_PERFEAT_RELIABILITY: %d", SAVE_PERFEAT_RELIABILITY);

    // R2 reference-only switches (build+log preint, no factor) — env override, default OFF
    WHEEL_REFERENCE_ONLY = 0; FOG_YAW_REFERENCE_ONLY = 0;
    if (const char* e = std::getenv("REL_WHEEL_REFERENCE_ONLY"))
    { std::string v(e); WHEEL_REFERENCE_ONLY = (v=="1"||v=="true"||v=="on"||v=="ON") ? 1 : 0; }
    if (const char* e = std::getenv("REL_FOG_REFERENCE_ONLY"))
    { std::string v(e); FOG_YAW_REFERENCE_ONLY = (v=="1"||v=="true"||v=="on"||v=="ON") ? 1 : 0; }
    ROS_WARN("WHEEL_REFERENCE_ONLY: %d  FOG_YAW_REFERENCE_ONLY: %d", WHEEL_REFERENCE_ONLY, FOG_YAW_REFERENCE_ONLY);

    // R3b reliability weighting (default OFF). Env overrides.
    FEATURE_RELIABILITY_ENABLE = 0;
    if (const char* e = std::getenv("REL_FEATURE_RELIABILITY"))
    { std::string v(e); FEATURE_RELIABILITY_ENABLE = (v=="1"||v=="true"||v=="on"||v=="ON") ? 1 : 0; }
    if (const char* e = std::getenv("REL_KAPPA"))    RELIABILITY_KAPPA = atof(e);
    if (const char* e = std::getenv("REL_D2_THRESH")) RELIABILITY_D2_THRESH = atof(e);
    if (const char* e = std::getenv("REL_SIGMA_UV")) RELIABILITY_SIGMA_UV = atof(e);
    if (const char* e = std::getenv("REL_FLOOR"))    RELIABILITY_FLOOR = atof(e);
    if (const char* e = std::getenv("REL_KEEPN"))    RELIABILITY_KEEPN = atoi(e);
    ROS_WARN("FEATURE_RELIABILITY_ENABLE: %d kappa=%.2f d2_thresh=%.2f sigma_uv=%.2f floor=%.2f keepN=%d",
             FEATURE_RELIABILITY_ENABLE, RELIABILITY_KAPPA, RELIABILITY_D2_THRESH, RELIABILITY_SIGMA_UV, RELIABILITY_FLOOR, RELIABILITY_KEEPN);

    // ===== [pose-cov] integrity diagnostic switch — DEFAULT OFF =====
    // The DENSE_SVD per-keyframe covariance is expensive and throttles VINS below real-time at
    // playback_rate 3.0. Keep it OFF for baseline / System A / Paper-2 smoke. Enable only when building
    // the pose-covariance dataset, via config `pose_cov_enable: 1` OR env `SAVE_POSE_COVARIANCE=1`.
    // Optionally subsample with `pose_cov_every_n` / env `POSE_COV_EVERY_N`.
    POSE_COV_ENABLE = 0;
    POSE_COV_EVERY_N = 1;
    if (!fsSettings["pose_cov_enable"].empty())
        POSE_COV_ENABLE = (int)fsSettings["pose_cov_enable"];
    {
        const char *env_pc = getenv("SAVE_POSE_COVARIANCE");
        if (env_pc && atoi(env_pc) != 0) POSE_COV_ENABLE = 1;
    }
    if (!fsSettings["pose_cov_every_n"].empty())
        POSE_COV_EVERY_N = (int)fsSettings["pose_cov_every_n"];
    {
        const char *env_pcn = getenv("POSE_COV_EVERY_N");
        if (env_pcn && atoi(env_pcn) > 0) POSE_COV_EVERY_N = atoi(env_pcn);
    }
    if (POSE_COV_EVERY_N < 1) POSE_COV_EVERY_N = 1;
    ROS_WARN("POSE_COV_ENABLE: %d (every_n=%d)", POSE_COV_ENABLE, POSE_COV_EVERY_N);

    // P1 (fwvio) factor switches — default 0 (flags-off bit-invariance). Set via config or env.
    FOG_FACTOR_ENABLE = 0; WHEEL_FACTOR_ENABLE = 0; NHC_ENABLE = 0;
    if (!fsSettings["fog_factor_enable"].empty())   FOG_FACTOR_ENABLE   = (int)fsSettings["fog_factor_enable"];
    if (!fsSettings["wheel_factor_enable"].empty()) WHEEL_FACTOR_ENABLE = (int)fsSettings["wheel_factor_enable"];
    if (!fsSettings["nhc_enable"].empty())          NHC_ENABLE          = (int)fsSettings["nhc_enable"];
    { const char *e;
      if ((e=getenv("FOG_FACTOR_ENABLE")))   FOG_FACTOR_ENABLE   = atoi(e);
      if ((e=getenv("WHEEL_FACTOR_ENABLE"))) WHEEL_FACTOR_ENABLE = atoi(e);
      if ((e=getenv("NHC_ENABLE")))          NHC_ENABLE          = atoi(e);
      if ((e=getenv("FOG_YAW_ENABLE")))      FOG_YAW_ENABLE      = atoi(e); }
    { const char *m = getenv("WHEEL_MODE");
      if (m) WHEEL_MODE_SE2 = (std::string(m) == "forward_only") ? 0 : 1; }
    ROS_WARN("P1 factors: FOG=%d WHEEL=%d (mode=%s) NHC=%d", FOG_FACTOR_ENABLE, WHEEL_FACTOR_ENABLE,
             WHEEL_MODE_SE2 ? "se2" : "forward_only", NHC_ENABLE);

    USE_GPU = fsSettings["use_gpu"];
    USE_GPU_ACC_FLOW = fsSettings["use_gpu_acc_flow"];
    USE_GPU_CERES = fsSettings["use_gpu_ceres"];
    USE_IMU = fsSettings["imu"];

    printf("USE_IMU: %d\n", USE_IMU);
    if(USE_IMU)
    {
        fsSettings["imu_topic"] >> IMU_TOPIC;
        printf("IMU_TOPIC: %s\n", IMU_TOPIC.c_str());

        if (!fsSettings["imu_noise_mode"].empty())
            fsSettings["imu_noise_mode"] >> IMU_NOISE_MODE;
        else
            IMU_NOISE_MODE = "custom";

        applyImuNoiseProfile(IMU_NOISE_MODE, fsSettings);

        G.z() = fsSettings["g_norm"];

        // DEBUG-ONLY env-gated gravity-sign flip (default off; no behavior change).
        // DEBUG_GRAVITY_SIGN_FLIP=1 -> negate the world gravity vector to test gravity-sign convention.
        if (std::getenv("DEBUG_GRAVITY_SIGN_FLIP") &&
            std::string(std::getenv("DEBUG_GRAVITY_SIGN_FLIP")) == "1") {
            G = -G;
            std::cout << "[DBG_GRAVITY_SIGN_FLIP] G negated -> " << G.transpose() << std::endl;
        }

        std::cout << "IMU_NOISE_MODE: " << IMU_NOISE_MODE << std::endl;
        std::cout << "ACC_N: " << ACC_N << " ACC_W: " << ACC_W
                << " GYR_N: " << GYR_N << " GYR_W: " << GYR_W << std::endl;
    }

    SOLVER_TIME = fsSettings["max_solver_time"];
    NUM_ITERATIONS = fsSettings["max_num_iterations"];
    MIN_PARALLAX = fsSettings["keyframe_parallax"];
    MIN_PARALLAX = MIN_PARALLAX / FOCAL_LENGTH;

    fsSettings["output_path"] >> OUTPUT_FOLDER;
    VINS_RESULT_PATH = OUTPUT_FOLDER + "/vio.csv";

    // Safety guard: refuse to write into sacred baseline directories
    {
        char *rp = realpath(OUTPUT_FOLDER.c_str(), nullptr);
        const std::string resolved = rp ? std::string(rp) : OUTPUT_FOLDER;
        if (rp) free(rp);

        static const char *SACRED[] = {
            "kaist_fixedext_best_baseline",
            "kaist_fixedext_from_baseline",
            "kaist_fixedext_hybrid_baseline",
            "kaist_fixedext_urban28forall_baseline",
        };
        for (const char *root : SACRED)
        {
            if (resolved.find(root) != std::string::npos)
            {
                ROS_ERROR("[SAFETY] output_path resolves into sacred baseline: %s",
                          resolved.c_str());
                ROS_ERROR("[SAFETY] Refusing to overwrite master data. Aborting.");
                rclcpp::shutdown();
                return;
            }
        }
    }

    Eigen::Matrix4d T0_seq, T1_seq;

    // ------------------------------------------------------------------
    // Extrinsic source selection. Priority:
    //   1. explicit_fixedext_config : body_T_cam0/cam1 are embedded in THIS
    //      config yaml; do NOT read any run-time CSV or dataset calibration.
    //      (set via `extrinsic_source: "explicit_fixedext_config"`)
    //   2. fixedext / counterfactual_prefix output path : load fixed
    //      extrinsic CSV from the baseline-result folder (legacy behaviour).
    //   3. otherwise : dataset-derived extrinsic from KAIST calibration files.
    // ------------------------------------------------------------------
    std::string extrinsic_source_str;
    if (!fsSettings["extrinsic_source"].empty())
        fsSettings["extrinsic_source"] >> extrinsic_source_str;

    const bool use_explicit_fixedext =
        (extrinsic_source_str == "explicit_fixedext_config");

    const bool output_is_fixedext =
        (OUTPUT_FOLDER.find("fixedext") != std::string::npos);

    const bool output_is_counterfactual_prefix =
        (OUTPUT_FOLDER.find("counterfactual_prefix") != std::string::npos);

    // Explicit config always wins; it never consults the run-time CSV path.
    const bool want_fixed_extrinsic =
        (!use_explicit_fixedext) &&
        (output_is_fixedext || output_is_counterfactual_prefix);

    if (use_explicit_fixedext)
    {
        ROS_WARN("[FIXED_EXTRINSIC] source=explicit_fixedext_config");
        ROS_WARN("[FIXED_EXTRINSIC] config = %s", config_file.c_str());
        ROS_WARN("[FIXED_EXTRINSIC] using body_T_cam0/cam1 embedded in this config; "
                 "no run-time CSV / dataset-derived extrinsic.");
    }
    else if (output_is_counterfactual_prefix)
    {
        ROS_WARN("[FIXED_EXTRINSIC] source=baseline_csv (counterfactual_prefix detected).");
    }
    else if (output_is_fixedext)
    {
        ROS_WARN("[FIXED_EXTRINSIC] source=baseline_csv (fixedext output detected).");
    }
    else
    {
        ROS_WARN("[FIXED_EXTRINSIC] source=dataset_derived (no explicit/fixedext marker).");
    }

    bool loaded_fixed_ex = false;

    if (want_fixed_extrinsic)
    {
        loaded_fixed_ex = loadFixedExtrinsicFromBaselineResult(OUTPUT_FOLDER, T0_seq, T1_seq);

        if (!loaded_fixed_ex)
        {
            ROS_ERROR("[FIXED_EXTRINSIC] fixedext run requested, but failed to load fixed extrinsic. Abort.");
            rclcpp::shutdown();
            return;
        }
    }

    // explicit_fixedext_config => use the embedded YAML body_T (loaded_seq_ex=false).
    bool loaded_seq_ex = false;
    if (loaded_fixed_ex)
        loaded_seq_ex = true;
    else if (!use_explicit_fixedext)
        loaded_seq_ex = loadSequenceSpecificExtrinsic(OUTPUT_FOLDER, T0_seq, T1_seq);

    std::cout << "result path " << VINS_RESULT_PATH << std::endl;
    std::ofstream fout(VINS_RESULT_PATH, std::ios::out);
    fout.close();

    ESTIMATE_EXTRINSIC = fsSettings["estimate_extrinsic"];

    if (loaded_fixed_ex || use_explicit_fixedext)
    {
        ESTIMATE_EXTRINSIC = 0;
        EX_CALIB_RESULT_PATH = OUTPUT_FOLDER + "/extrinsic_parameter.csv";
        ROS_WARN("[FIXED_EXTRINSIC] force ESTIMATE_EXTRINSIC = 0 (estimate_extrinsic=%d)",
                 ESTIMATE_EXTRINSIC);
    }
    if (ESTIMATE_EXTRINSIC == 2)
    {
        ROS_WARN("have no prior about extrinsic param, calibrate extrinsic param");
        RIC.push_back(Eigen::Matrix3d::Identity());
        TIC.push_back(Eigen::Vector3d::Zero());
        EX_CALIB_RESULT_PATH = OUTPUT_FOLDER + "/extrinsic_parameter.csv";
    }
    else 
    {
        if ( ESTIMATE_EXTRINSIC == 1)
        {
            ROS_WARN(" Optimize extrinsic param around initial guess!");
            EX_CALIB_RESULT_PATH = OUTPUT_FOLDER + "/extrinsic_parameter.csv";
        }
        if (ESTIMATE_EXTRINSIC == 0)
            ROS_WARN(" fix extrinsic param ");

        if (loaded_seq_ex)
        {
            if (loaded_fixed_ex)
                ROS_WARN("[FIXED_EXTRINSIC] Use fixed baseline_fog extrinsic for cam0");
            else
                ROS_WARN("Use sequence-specific extrinsic for cam0 from calibration folder");

            RIC.push_back(T0_seq.block<3, 3>(0, 0));
            TIC.push_back(T0_seq.block<3, 1>(0, 3));
        }
        else
        {
            if (use_explicit_fixedext)
                ROS_WARN("[FIXED_EXTRINSIC] source=explicit_fixedext_config; use embedded body_T_cam0");
            else
                ROS_WARN("Fallback to YAML body_T_cam0");
            cv::Mat cv_T;
            fsSettings["body_T_cam0"] >> cv_T;
            Eigen::Matrix4d T;
            cv::cv2eigen(cv_T, T);
            RIC.push_back(T.block<3, 3>(0, 0));
            TIC.push_back(T.block<3, 1>(0, 3));
        }

        if (use_explicit_fixedext)
        {
            ROS_WARN("[FIXED_EXTRINSIC] cam0 tic = [%.6f, %.6f, %.6f]",
                     TIC[0].x(), TIC[0].y(), TIC[0].z());
            std::cout << "[FIXED_EXTRINSIC] cam0 ric =\n" << RIC[0] << std::endl;
        }
    }
    
    NUM_OF_CAM = fsSettings["num_of_cam"];
    printf("camera number %d\n", NUM_OF_CAM);

    if(NUM_OF_CAM != 1 && NUM_OF_CAM != 2)
    {
        printf("num_of_cam should be 1 or 2\n");
        assert(0);
    }


    int pn = config_file.find_last_of('/');
    std::string configPath = config_file.substr(0, pn);
    
    std::string cam0Calib;
    fsSettings["cam0_calib"] >> cam0Calib;
    std::string cam0Path = configPath + "/" + cam0Calib;
    CAM_NAMES.push_back(cam0Path);

    if(NUM_OF_CAM == 2)
    {
        STEREO = 1;
        std::string cam1Calib;
        fsSettings["cam1_calib"] >> cam1Calib;
        std::string cam1Path = configPath + "/" + cam1Calib; 
        //printf("%s cam1 path\n", cam1Path.c_str() );
        CAM_NAMES.push_back(cam1Path);
        
        if (loaded_seq_ex)
        {
            if (loaded_fixed_ex)
                ROS_WARN("[FIXED_EXTRINSIC] Use fixed baseline_fog extrinsic for cam1");
            else
                ROS_WARN("Use sequence-specific extrinsic for cam1 from calibration folder");

            RIC.push_back(T1_seq.block<3, 3>(0, 0));
            TIC.push_back(T1_seq.block<3, 1>(0, 3));
        }
        else
        {
            if (use_explicit_fixedext)
                ROS_WARN("[FIXED_EXTRINSIC] source=explicit_fixedext_config; use embedded body_T_cam1");
            else
                ROS_WARN("Fallback to YAML body_T_cam1");
            cv::Mat cv_T;
            fsSettings["body_T_cam1"] >> cv_T;
            Eigen::Matrix4d T;
            cv::cv2eigen(cv_T, T);
            RIC.push_back(T.block<3, 3>(0, 0));
            TIC.push_back(T.block<3, 1>(0, 3));
        }

        if (use_explicit_fixedext)
        {
            ROS_WARN("[FIXED_EXTRINSIC] cam1 tic = [%.6f, %.6f, %.6f]",
                     TIC[1].x(), TIC[1].y(), TIC[1].z());
            std::cout << "[FIXED_EXTRINSIC] cam1 ric =\n" << RIC[1] << std::endl;
        }
    }

    INIT_DEPTH = 5.0;
    BIAS_ACC_THRESHOLD = 0.1;
    BIAS_GYR_THRESHOLD = 0.1;

    TD = fsSettings["td"];
    ESTIMATE_TD = fsSettings["estimate_td"];
    if (ESTIMATE_TD)
        ROS_INFO("Unsynchronized sensors, online estimate time offset, initial td: %f", TD);
    else
        ROS_INFO("Synchronized sensors, fix time offset: %f", TD);

    ROW = fsSettings["image_height"];
    COL = fsSettings["image_width"];
    ROS_INFO("ROW: %d COL: %d ", ROW, COL);

    if(!USE_IMU)
    {
        ESTIMATE_EXTRINSIC = 0;
        ESTIMATE_TD = 0;
        printf("no imu, fix extrinsic param; no time offset calibration\n");
    }

    fsSettings.release();
}


/////////my
static bool parseVehicleTxtToT(const std::string &path, Eigen::Matrix4d &T)
{
    std::ifstream fin(path);
    if (!fin.is_open()) return false;
    std::stringstream buffer;
    buffer << fin.rdbuf();
    std::string text = buffer.str();

    auto parse_numbers = [](const std::string &s) {
        std::vector<double> nums;
        std::regex num_re(R"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)");
        auto begin = std::sregex_iterator(s.begin(), s.end(), num_re);
        auto end = std::sregex_iterator();
        for (auto it = begin; it != end; ++it) nums.push_back(std::stod(it->str()));
        return nums;
    };

    std::regex rR(R"(R\s*:\s*([^\n\r]+))");
    std::regex rT(R"(T\s*:\s*([^\n\r]+))");
    std::smatch mR, mT;
    if (std::regex_search(text, mR, rR) && std::regex_search(text, mT, rT))
    {
        auto Rnums = parse_numbers(mR[1].str());
        auto Tnums = parse_numbers(mT[1].str());
        if (Rnums.size() == 9 && Tnums.size() == 3)
        {
            T.setIdentity();
            T(0,0)=Rnums[0]; T(0,1)=Rnums[1]; T(0,2)=Rnums[2];
            T(1,0)=Rnums[3]; T(1,1)=Rnums[4]; T(1,2)=Rnums[5];
            T(2,0)=Rnums[6]; T(2,1)=Rnums[7]; T(2,2)=Rnums[8];
            T(0,3)=Tnums[0]; T(1,3)=Tnums[1]; T(2,3)=Tnums[2];
            return true;
        }
    }

    auto nums = parse_numbers(text);
    if (nums.size() == 15)
    {
        T.setIdentity();
        T(0,0)=nums[3];  T(0,1)=nums[4];  T(0,2)=nums[5];
        T(1,0)=nums[6];  T(1,1)=nums[7];  T(1,2)=nums[8];
        T(2,0)=nums[9];  T(2,1)=nums[10]; T(2,2)=nums[11];
        T(0,3)=nums[12]; T(1,3)=nums[13]; T(2,3)=nums[14];
        return true;
    }

    return false;
}

static bool parseRightYamlBaseline(const std::string &path, double &baseline)
{
    cv::FileStorage fs(path, cv::FileStorage::READ);
    if (!fs.isOpened())
        return false;

    cv::Mat P;
    fs["projection_matrix"] >> P;
    fs.release();

    if (P.empty() || P.rows != 3 || P.cols != 4)
        return false;

    cv::Mat P64;
    P.convertTo(P64, CV_64F);

    const double fx = P64.at<double>(0, 0);
    const double tx = P64.at<double>(0, 3);

    if (std::abs(fx) < 1e-12)
        return false;

    baseline = -tx / fx;
    return true;
}

static bool inferSequenceFromOutputPath(const std::string &output_path, std::string &seq_name)
{
    std::regex re(R"(urban(\d+)[_-]([A-Za-z0-9]+))", std::regex::icase);
    std::smatch m;
    if (!std::regex_search(output_path, m, re)) return false;
    seq_name = "urban" + m[1].str() + "-" + m[2].str();
    std::transform(seq_name.begin(), seq_name.end(), seq_name.begin(), ::tolower);
    return true;
}

static Eigen::Matrix4d openVinsKaistT_LtoR()
{
    // OpenVINS KAIST stereo left-to-right transform.
    //
    // Convention:
    //   T_LtoR maps vehicle->left chain into vehicle->right chain in the
    //   OpenVINS derivation:
    //
    //   T_LtoI = T_VtoI * inv(T_VtoL)
    //   T_RtoI = T_VtoI * inv(T_LtoR * T_VtoL)
    //
    // Therefore:
    //   T_RtoI = T_LtoI * inv(T_LtoR)
    //
    // This is NOT the same as only adding right.yaml projection baseline.
    Eigen::Matrix4d T;
    T <<  1.0000, -0.0021, -0.0036, -0.4751,
          0.0021,  1.0000,  0.0046, -0.0011,
          0.0036, -0.0046,  1.0000,  0.0020,
          0.0000,  0.0000,  0.0000,  1.0000;

    return T;
}


static bool parseOpenCvBodyTFromFile(
    const std::string &path,
    const std::string &key,
    Eigen::Matrix4d &T)
{
    std::ifstream fin(path);

    if (!fin.is_open())
    {
        ROS_WARN("[FIXED_EXTRINSIC] failed to open file: %s", path.c_str());
        return false;
    }

    std::stringstream buffer;
    buffer << fin.rdbuf();
    const std::string text = buffer.str();

    const size_t key_pos = text.find(key);

    if (key_pos == std::string::npos)
    {
        ROS_WARN("[FIXED_EXTRINSIC] cannot find key %s in %s", key.c_str(), path.c_str());
        return false;
    }

    const std::string sub = text.substr(key_pos, 3000);

    std::regex data_re(R"(data\s*:\s*\[([^\]]+)\])");
    std::smatch m;

    if (!std::regex_search(sub, m, data_re))
    {
        ROS_WARN("[FIXED_EXTRINSIC] cannot find data block for %s in %s", key.c_str(), path.c_str());
        return false;
    }

    std::vector<double> nums;
    std::regex num_re(R"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)");

    const std::string data = m[1].str();

    auto begin = std::sregex_iterator(data.begin(), data.end(), num_re);
    auto end = std::sregex_iterator();

    for (auto it = begin; it != end; ++it)
        nums.push_back(std::stod(it->str()));

    if (nums.size() != 16)
    {
        ROS_WARN("[FIXED_EXTRINSIC] %s should have 16 values, got %zu", key.c_str(), nums.size());
        return false;
    }

    T.setIdentity();

    for (int r = 0; r < 4; ++r)
    {
        for (int c = 0; c < 4; ++c)
            T(r, c) = nums[r * 4 + c];
    }

    return true;
}
static bool loadFixedExtrinsicFromBaselineResult(
    const std::string &output_folder,
    Eigen::Matrix4d &T_b_c0,
    Eigen::Matrix4d &T_b_c1)
{
    std::string seq_name;

    if (!inferSequenceFromOutputPath(output_folder, seq_name))
    {
        ROS_WARN("[FIXED_EXTRINSIC] cannot infer sequence name from output_path: %s",
                 output_folder.c_str());
        return false;
    }

    // ============================================================
    // Priority 1:
    //   Use the final best-available extrinsic selected by
    //   best_available_fixed_baseline_source_map_18_39.csv.
    //
    // This folder should contain:
    //   - own online-estimated extrinsic if seqwise_fixed was selected
    //   - urban28 online-estimated extrinsic if urban28forall_fixed was selected
    //   - hybrid extrinsic if hybrid_rerun_fixed was selected
    //
    // Priority 2:
    //   Fallback to old seqwise fixed extrinsic folder.
    // ============================================================
    const std::string best_root =
        "/mnt/sata4t/ivlab3_data/vins_project/results/fixed_extrinsic_best_available_fog";

    const std::string old_seqwise_root =
        "/mnt/sata4t/ivlab3_data/vins_project/results/fixed_extrinsic_from_baseline_fog";

    const std::string best_csv =
        best_root + "/" + seq_name + "/extrinsic_parameter.csv";

    const std::string old_csv =
        old_seqwise_root + "/" + seq_name + "/extrinsic_parameter.csv";

    std::string fixed_csv;

    {
        std::ifstream fin(best_csv);
        if (fin.good())
        {
            fixed_csv = best_csv;
            ROS_WARN("[FIXED_EXTRINSIC] using BEST_AVAILABLE extrinsic.");
        }
        else
        {
            fixed_csv = old_csv;
            ROS_WARN("[FIXED_EXTRINSIC] BEST_AVAILABLE extrinsic not found, fallback to old seqwise fixed extrinsic.");
            ROS_WARN("[FIXED_EXTRINSIC] missing best path = %s", best_csv.c_str());
        }
    }

    if (!parseOpenCvBodyTFromFile(fixed_csv, "body_T_cam0", T_b_c0))
        return false;

    if (!parseOpenCvBodyTFromFile(fixed_csv, "body_T_cam1", T_b_c1))
        return false;

    ROS_WARN("[FIXED_EXTRINSIC] sequence = %s", seq_name.c_str());
    ROS_WARN("[FIXED_EXTRINSIC] source = %s", fixed_csv.c_str());

    ROS_WARN("[FIXED_EXTRINSIC] cam0 T_b_c0:");
    std::cout << T_b_c0 << std::endl;

    ROS_WARN("[FIXED_EXTRINSIC] cam1 T_b_c1:");
    std::cout << T_b_c1 << std::endl;

    const double stereo_baseline =
        (T_b_c1.block<3, 1>(0, 3) - T_b_c0.block<3, 1>(0, 3)).norm();

    ROS_WARN("[FIXED_EXTRINSIC] stereo baseline from fixed file = %.9f m",
             stereo_baseline);

    return true;
}


static bool loadSequenceSpecificExtrinsic(
    const std::string &output_folder,
    Eigen::Matrix4d &T_b_c0,
    Eigen::Matrix4d &T_b_c1)
{
    std::string seq_name;
    if (!inferSequenceFromOutputPath(output_folder, seq_name))
    {
        ROS_WARN("[KAIST_EXTRINSIC] cannot infer sequence name from output_path: %s",
                 output_folder.c_str());
        return false;
    }

    const std::string dataset_root =
        "/mnt/sata4t/datasets/kaist_complex_urban/extracted";

    const std::string calib_dir =
        dataset_root + "/" + seq_name + "/calibration/" + seq_name + "/calibration";

    Eigen::Matrix4d T_v_i;
    Eigen::Matrix4d T_v_s;

    if (!parseVehicleTxtToT(calib_dir + "/Vehicle2IMU.txt", T_v_i))
    {
        ROS_WARN("[KAIST_EXTRINSIC] failed to parse Vehicle2IMU.txt: %s",
                 (calib_dir + "/Vehicle2IMU.txt").c_str());
        return false;
    }

    if (!parseVehicleTxtToT(calib_dir + "/Vehicle2Stereo.txt", T_v_s))
    {
        ROS_WARN("[KAIST_EXTRINSIC] failed to parse Vehicle2Stereo.txt: %s",
                 (calib_dir + "/Vehicle2Stereo.txt").c_str());
        return false;
    }

    // cam0:
    // Keep your current sequence-specific cam0 derivation.
    // This is the part you already confirmed works for mono extrinsic=0.
    T_b_c0 = T_v_i.inverse() * T_v_s;

    // cam1:
    // Old wrong / approximate method:
    //   T_b_c1 = T_b_c0 * [baseline only]
    //
    // New method:
    //   Use OpenVINS full KAIST stereo left-to-right transform.
    //
    // OpenVINS derivation:
    //   T_LtoI = T_VtoI * inv(T_VtoL)
    //   T_RtoI = T_VtoI * inv(T_LtoR * T_VtoL)
    //
    // Since T_b_c0 here is camera0-to-IMU/body,
    //   T_b_c1 = T_b_c0 * inv(T_LtoR)
    const Eigen::Matrix4d T_LtoR = openVinsKaistT_LtoR();
    T_b_c1 = T_b_c0 * T_LtoR.inverse();

    // Optional sanity print: right.yaml baseline is only used for comparison now.
    double baseline_from_projection = 0.0;
    const bool has_projection_baseline =
        parseRightYamlBaseline(calib_dir + "/right.yaml", baseline_from_projection);

    ROS_WARN("[KAIST_EXTRINSIC] sequence = %s", seq_name.c_str());
    ROS_WARN("[KAIST_EXTRINSIC] method = sequence_cam0 + OpenVINS_full_T_LtoR_for_cam1");
    ROS_WARN("[KAIST_EXTRINSIC] calib_dir = %s", calib_dir.c_str());

    if (has_projection_baseline)
    {
        ROS_WARN("[KAIST_EXTRINSIC] right.yaml projection baseline = %.9f m, but cam1 uses full T_LtoR, not baseline-only.",
                 baseline_from_projection);
    }
    else
    {
        ROS_WARN("[KAIST_EXTRINSIC] right.yaml projection baseline unavailable; continue with full T_LtoR.");
    }

    ROS_WARN("[KAIST_EXTRINSIC] cam0 T_b_c0:");
    std::cout << T_b_c0 << std::endl;

    ROS_WARN("[KAIST_EXTRINSIC] cam1 T_b_c1:");
    std::cout << T_b_c1 << std::endl;

    return true;
}