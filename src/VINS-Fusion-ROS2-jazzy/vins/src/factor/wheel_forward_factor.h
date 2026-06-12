#pragma once
// P1 (fwvio): wheel forward-displacement factor between adjacent keyframes i, j.
// residual = e_x^T R_i^T (p_j - p_i) - ds_wheel   (1-dim), whitened by 1/sqrt(forward_var).
// e_x = body forward axis [1,0,0]; ds_wheel = (dL+dR)/2 * pi*D/4096 integrated from /wheel/ds
// between the two keyframe timestamps. var = forward_var_m2 (sensors.yaml; placeholder until Task5).
// Behind WHEEL_FACTOR_ENABLE (default OFF).
#include <ceres/ceres.h>
#include <Eigen/Dense>

struct WheelForwardFunctor
{
    WheelForwardFunctor(double ds_wheel, double sqrt_info)
        : ds_wheel_(ds_wheel), sqrt_info_(sqrt_info) {}

    template <typename T>
    bool operator()(const T *const pose_i, const T *const pose_j, T *residuals) const
    {
        Eigen::Matrix<T, 3, 1> Pi(pose_i[0], pose_i[1], pose_i[2]);
        Eigen::Matrix<T, 3, 1> Pj(pose_j[0], pose_j[1], pose_j[2]);
        Eigen::Quaternion<T> Qi(pose_i[6], pose_i[3], pose_i[4], pose_i[5]);
        Eigen::Matrix<T, 3, 1> dp_body = Qi.conjugate() * (Pj - Pi);   // R_i^T (p_j - p_i)
        residuals[0] = T(sqrt_info_) * (dp_body[0] - T(ds_wheel_));    // forward (x) component
        return true;
    }

    static ceres::CostFunction *Create(double ds_wheel, double forward_var)
    {
        double sqrt_info = 1.0 / std::sqrt(std::max(forward_var, 1e-12));
        return new ceres::AutoDiffCostFunction<WheelForwardFunctor, 1, 7, 7>(
            new WheelForwardFunctor(ds_wheel, sqrt_info));
    }

    double ds_wheel_, sqrt_info_;
};
