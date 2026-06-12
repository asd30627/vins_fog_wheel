#pragma once
// P1-Wheel v3.3 C3: SE(2) wheel factor between adjacent keyframes i, j (autodiff).
// residual = Log_SE2( dT_wheel^{-1} . dT_pred ), 3-dim [ex, ey, eyaw], whitened by sqrt_info.
//   dT_pred  = planar relative pose body_i->body_j (rear frame; lever-arm T_body_rear applied by caller-side
//              pose if available — C3 uses identity lever, flagged in WHEEL_MODEL.md).
//   dT_wheel = preintegrated SE(2) increment (wx, wy, wth) from WheelPreintegration.
// Translation rows (ex,ey) are the primary constraint; yaw row pre-scaled loose by the caller (sqrt_info).
#include <ceres/ceres.h>
#include <Eigen/Dense>

struct WheelSE2Functor
{
    WheelSE2Functor(double wx, double wy, double wth, const Eigen::Matrix3d &sqrt_info)
        : wx_(wx), wy_(wy), wth_(wth), cw_(std::cos(wth)), sw_(std::sin(wth)), sqrt_info_(sqrt_info) {}

    template <typename T>
    bool operator()(const T *const pose_i, const T *const pose_j, T *residuals) const
    {
        Eigen::Quaternion<T> Qi(pose_i[6], pose_i[3], pose_i[4], pose_i[5]);
        Eigen::Quaternion<T> Qj(pose_j[6], pose_j[3], pose_j[4], pose_j[5]);
        Eigen::Matrix<T, 3, 1> Pi(pose_i[0], pose_i[1], pose_i[2]);
        Eigen::Matrix<T, 3, 1> Pj(pose_j[0], pose_j[1], pose_j[2]);
        Eigen::Matrix<T, 3, 1> dp = Qi.conjugate() * (Pj - Pi);            // relative translation in body_i frame
        Eigen::Matrix<T, 3, 3> Rrel = (Qi.conjugate() * Qj).toRotationMatrix();
        T pth = ceres::atan2(Rrel(1, 0), Rrel(0, 0));                       // relative yaw (planar)
        T px = dp[0], py = dp[1];
        // SE(2) error = dT_wheel^{-1} . dT_pred
        T dxw = px - T(wx_), dyw = py - T(wy_);
        T ex =  T(cw_) * dxw + T(sw_) * dyw;
        T ey = -T(sw_) * dxw + T(cw_) * dyw;
        T eth = pth - T(wth_);                  // adjacent keyframes: |eth| << pi, no wrap needed
        Eigen::Matrix<T, 3, 1> e; e << ex, ey, eth;
        Eigen::Map<Eigen::Matrix<T, 3, 1>> res(residuals);
        res = sqrt_info_.cast<T>() * e;
        return true;
    }

    static ceres::CostFunction *Create(double wx, double wy, double wth, const Eigen::Matrix3d &sqrt_info)
    {
        return new ceres::AutoDiffCostFunction<WheelSE2Functor, 3, 7, 7>(
            new WheelSE2Functor(wx, wy, wth, sqrt_info));
    }

    double wx_, wy_, wth_, cw_, sw_;
    Eigen::Matrix3d sqrt_info_;
};
