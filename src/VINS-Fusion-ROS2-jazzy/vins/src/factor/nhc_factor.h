#pragma once
// P1 (fwvio): soft non-holonomic constraint (NHC) on the body-frame velocity at keyframe i.
// residual = [ e_y^T R_i^T v_i ; e_z^T R_i^T v_i ]  (2-dim, lateral + vertical body velocity),
// whitened by 1/sigma_nhc (pre-registered (0.3 m/s)^2 -> sqrt_info = 1/0.3). SOFT prior, not hard.
// Parameters: para_Pose[i] (for R_i), para_SpeedBias[i] (v_i = first 3). Behind NHC_ENABLE (default OFF).
#include <ceres/ceres.h>
#include <Eigen/Dense>

struct NhcFunctor
{
    explicit NhcFunctor(double sqrt_info) : sqrt_info_(sqrt_info) {}

    template <typename T>
    bool operator()(const T *const pose_i, const T *const speedbias_i, T *residuals) const
    {
        Eigen::Quaternion<T> Qi(pose_i[6], pose_i[3], pose_i[4], pose_i[5]);
        Eigen::Matrix<T, 3, 1> Vi(speedbias_i[0], speedbias_i[1], speedbias_i[2]);
        Eigen::Matrix<T, 3, 1> v_body = Qi.conjugate() * Vi;   // R_i^T v_i
        residuals[0] = T(sqrt_info_) * v_body[1];              // lateral (y)
        residuals[1] = T(sqrt_info_) * v_body[2];              // vertical (z)
        return true;
    }

    static ceres::CostFunction *Create(double sigma_nhc_ms)
    {
        double sqrt_info = 1.0 / std::max(sigma_nhc_ms, 1e-6);
        return new ceres::AutoDiffCostFunction<NhcFunctor, 2, 7, 9>(
            new NhcFunctor(sqrt_info));
    }

    double sqrt_info_;
};
