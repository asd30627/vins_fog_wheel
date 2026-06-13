#pragma once
// P1-FogWheel v1 F3: FOG yaw factor between adjacent keyframes i, j (autodiff, 1-D).
// residual = yaw(R_i^T R_j) - Δψ_FOG   (only yaw; roll/pitch untouched -> IMU). yaw via atan2 (autodiff-safe).
// sqrt_info from FOG yaw cov (tight -> FOG dominates rotation, the paper premise: FOG ~100x better than wheel yaw).
#include <ceres/ceres.h>
#include <Eigen/Dense>

struct FogYawFunctor
{
    FogYawFunctor(double dpsi_fog, double sqrt_info) : dpsi_(dpsi_fog), sqrt_info_(sqrt_info) {}

    template <typename T>
    bool operator()(const T *const pose_i, const T *const pose_j, T *residuals) const
    {
        Eigen::Quaternion<T> Qi(pose_i[6], pose_i[3], pose_i[4], pose_i[5]);
        Eigen::Quaternion<T> Qj(pose_j[6], pose_j[3], pose_j[4], pose_j[5]);
        Eigen::Matrix<T, 3, 3> Rrel = (Qi.conjugate() * Qj).toRotationMatrix();
        T yaw = ceres::atan2(Rrel(1, 0), Rrel(0, 0));     // relative yaw (planar projection)
        residuals[0] = T(sqrt_info_) * (yaw - T(dpsi_));   // adjacent keyframes: |yaw-dpsi| small, no wrap
        return true;
    }

    static ceres::CostFunction *Create(double dpsi_fog, double sqrt_info)
    {
        return new ceres::AutoDiffCostFunction<FogYawFunctor, 1, 7, 7>(
            new FogYawFunctor(dpsi_fog, sqrt_info));
    }

    double dpsi_, sqrt_info_;
};
