#pragma once
// P1 (fwvio): explicit FOG relative-rotation factor between adjacent keyframes i, j.
// residual = Log[ (dR_FOG)^{-1} * R_i^T R_j ]  (SO(3), 3-dim), whitened by sqrt_info.
// dR_FOG = SO(3) increment integrated from /fog/imu angular velocity between the two keyframe
// timestamps; sqrt_info from sensors.yaml cov_diag_rad2 scaled by actual dt (built by caller).
// Autodiff (per brief: efficiency later). Behind FOG_FACTOR_ENABLE (default OFF).
#include <ceres/ceres.h>
#include <Eigen/Dense>

struct FogRotationFunctor
{
    FogRotationFunctor(const Eigen::Quaterniond &dR_fog, const Eigen::Matrix3d &sqrt_info)
        : dR_fog_(dR_fog), sqrt_info_(sqrt_info) {}

    template <typename T>
    bool operator()(const T *const pose_i, const T *const pose_j, T *residuals) const
    {
        // pose layout: [px,py,pz, qx,qy,qz,qw]
        Eigen::Quaternion<T> Qi(pose_i[6], pose_i[3], pose_i[4], pose_i[5]);
        Eigen::Quaternion<T> Qj(pose_j[6], pose_j[3], pose_j[4], pose_j[5]);
        Eigen::Quaternion<T> dR = dR_fog_.cast<T>();
        // error quaternion: (dR_FOG)^{-1} * R_i^T * R_j
        Eigen::Quaternion<T> qe = dR.conjugate() * Qi.conjugate() * Qj;
        if (qe.w() < T(0)) { qe.coeffs() = -qe.coeffs(); }   // shortest geodesic
        Eigen::Matrix<T, 3, 1> r;
        r << T(2) * qe.x(), T(2) * qe.y(), T(2) * qe.z();    // 2*vec(q) = SO(3) log (small-angle exact to 1st order)
        Eigen::Map<Eigen::Matrix<T, 3, 1>> res(residuals);
        res = sqrt_info_.cast<T>() * r;
        return true;
    }

    static ceres::CostFunction *Create(const Eigen::Quaterniond &dR_fog, const Eigen::Matrix3d &sqrt_info)
    {
        return new ceres::AutoDiffCostFunction<FogRotationFunctor, 3, 7, 7>(
            new FogRotationFunctor(dR_fog, sqrt_info));
    }

    Eigen::Quaterniond dR_fog_;
    Eigen::Matrix3d sqrt_info_;
};
