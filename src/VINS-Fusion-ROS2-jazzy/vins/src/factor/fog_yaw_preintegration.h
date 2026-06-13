#pragma once
// P1-FogWheel v1 F1: immutable FOG yaw preintegration over a keyframe interval (1-D, yaw only — D16).
// Integrates FOG yaw increments between two keyframes; variance grows with ARW (var += N^2 * dt).
// Opt + marginalization use the SAME object (mirror of WheelPreintegration discipline). FOG only constrains
// yaw; roll/pitch stay with the IMU.
#include <cmath>

class FogYawPreintegration
{
public:
    // arw_rad_sqrt_s = FOG angle-random-walk noise density [rad/sqrt(s)] (from sensors.yaml cov_diag).
    explicit FogYawPreintegration(double arw_rad_sqrt_s) : N2_(arw_rad_sqrt_s * arw_rad_sqrt_s) {}

    double t_start = 0, t_end = 0;
    int n_samples = 0;
    double dpsi = 0;     // accumulated relative yaw [rad]
    double var = 0;      // accumulated yaw variance [rad^2]
    bool valid = false;

    // dyaw = FOG yaw increment for this sample [rad]; dt = sample interval [s].
    void addSample(double dyaw, double dt)
    {
        dpsi += dyaw;
        var += N2_ * dt;          // ARW: variance linear in integration time
        ++n_samples;
        valid = (n_samples > 0);
    }

    // two-segment merge (*this earlier, o later) — MARGIN_SECOND_NEW. Yaw is commutative -> simple add.
    void merge(const FogYawPreintegration &o)
    {
        dpsi += o.dpsi;
        var += o.var;
        n_samples += o.n_samples;
        t_end = o.t_end;
        valid = valid && o.valid;
    }

    double N2_;
};
