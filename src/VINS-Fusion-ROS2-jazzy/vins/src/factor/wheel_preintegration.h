#pragma once
// P1-Wheel v3.3 C1: immutable differential-drive SE(2) wheel preintegration over a keyframe interval.
// Built once when keyframe j forms; opt + marginalization use the SAME object. (WHEEL_MODEL.md is the contract.)
//   ds  = (dl+dr)/2      [m]   forward arc length (rear axle)
//   dth = (dr-dl)/b      [rad] heading change
// Exact-arc local step; |dth|<1e-6 -> 2nd-order expansion. Covariance propagated from per-wheel (sigmaL,sigmaR).
#include <Eigen/Dense>
#include <cmath>

class WheelPreintegration
{
public:
    WheelPreintegration(double b, double sigmaL, double sigmaR)
        : b_(b), sL2_(sigmaL*sigmaL), sR2_(sigmaR*sigmaR) {}

    double t_start = 0, t_end = 0;
    int n_samples = 0;
    double sum_dl = 0, sum_dr = 0;
    double dx = 0, dy = 0, dtheta = 0;       // accumulated SE(2) increment (body/rear frame at interval start)
    Eigen::Matrix3d cov = Eigen::Matrix3d::Zero();
    bool valid = false;

    void addSample(double dl, double dr)
    {
        const double ds = 0.5 * (dl + dr);
        const double dth = (dr - dl) / b_;
        double dxl, dyl;
        if (std::fabs(dth) < 1e-6) { dxl = ds * (1.0 - dth*dth/6.0); dyl = ds * dth * 0.5; }
        else { dxl = (ds/dth) * std::sin(dth); dyl = (ds/dth) * (1.0 - std::cos(dth)); }
        const double c = std::cos(dtheta), s = std::sin(dtheta);
        // covariance propagation BEFORE updating the mean (uses current heading dtheta)
        Eigen::Matrix3d A = Eigen::Matrix3d::Identity();
        A(0,2) = -s*dxl - c*dyl;
        A(1,2) =  c*dxl - s*dyl;
        Eigen::Matrix<double,2,2> Quv; Quv << sL2_, 0, 0, sR2_;     // (dl,dr) noise
        Eigen::Matrix<double,2,2> Jw; Jw << 0.5, 0.5, -1.0/b_, 1.0/b_;  // (ds,dth) <- (dl,dr)
        Eigen::Matrix<double,3,2> Bl; Bl << 1.0, 0.0,  dth*0.5, ds*0.5,  0.0, 1.0; // (dxl,dyl,dthl)<-(ds,dth)
        Eigen::Matrix3d Cm; Cm << c,-s,0, s,c,0, 0,0,1;
        Eigen::Matrix<double,3,2> B = Cm * Bl * Jw;                 // 3x2 wrt (dl,dr)
        cov = A * cov * A.transpose() + B * Quv * B.transpose();
        // mean update (exact-arc compose)
        dx += c*dxl - s*dyl;
        dy += s*dxl + c*dyl;
        dtheta += dth;
        sum_dl += dl; sum_dr += dr; ++n_samples;
        valid = (n_samples > 0);
    }

    // Two-segment SE(2) composition: *this (earlier) then o (later). Used by MARGIN_SECOND_NEW.
    void merge(const WheelPreintegration &o)
    {
        const double c = std::cos(dtheta), s = std::sin(dtheta);
        Eigen::Matrix3d A = Eigen::Matrix3d::Identity();
        A(0,2) = -s*o.dx - c*o.dy;
        A(1,2) =  c*o.dx - s*o.dy;
        Eigen::Matrix3d Ad; Ad << c,-s,0, s,c,0, 0,0,1;            // rotate o's cov into this frame
        cov = A * cov * A.transpose() + Ad * o.cov * Ad.transpose();
        dx += c*o.dx - s*o.dy;
        dy += s*o.dx + c*o.dy;
        dtheta += o.dtheta;
        sum_dl += o.sum_dl; sum_dr += o.sum_dr; n_samples += o.n_samples;
        t_end = o.t_end; valid = valid && o.valid;
    }

    double b_, sL2_, sR2_;
};
