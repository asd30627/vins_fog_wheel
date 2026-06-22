/*******************************************************
 * Copyright (C) 2019, Aerial Robotics Group, Hong Kong University of Science and Technology
 * 
 * This file is part of VINS.
 * 
 * Licensed under the GNU General Public License v3.0;
 * you may not use this file except in compliance with the License.
 *
 * Author: Qin Tong (qintonguav@gmail.com)
 *******************************************************/

#pragma once

#include <rcpputils/asserts.hpp>
#include <ceres/ceres.h>
#include <Eigen/Dense>
#include "../utility/utility.h"
#include "../utility/tic_toc.h"
#include "../estimator/parameters.h"

class ProjectionOneFrameTwoCamFactor : public ceres::SizedCostFunction<2, 7, 7, 1, 1>
{
  public:
    ProjectionOneFrameTwoCamFactor(const Eigen::Vector3d &_pts_i, const Eigen::Vector3d &_pts_j,
    				   			   const Eigen::Vector2d &_velocity_i, const Eigen::Vector2d &_velocity_j,
    	   			   			   const double _td_i, const double _td_j);
    virtual bool Evaluate(double const *const *parameters, double *residuals, double **jacobians) const;
    void check(double **parameters);

    Eigen::Vector3d pts_i, pts_j;
    Eigen::Vector3d velocity_i, velocity_j;
    double td_i, td_j;
    Eigen::Matrix<double, 2, 3> tangent_base;
    static Eigen::Matrix2d sqrt_info;
    double feat_weight_ = 1.0;   // P1-Reliability R3: per-feature reliability weight (sqrt of reliability); 1.0 = bit-identical
    // P1-Reliability M0: per-feature anisotropic sqrt(information). When use_inst_sqrt_info_ is true,
    // sqrt_info_inst_ (full 2x2 left-multiplier W with W^T W = Lambda) REPLACES feat_weight_*sqrt_info.
    // Default false => the legacy scalar path runs verbatim => bit-identical.
    Eigen::Matrix2d sqrt_info_inst_ = Eigen::Matrix2d::Zero();
    bool use_inst_sqrt_info_ = false;
    static double sum_t;
};
