#pragma once
// P1-Reliability R1: per-feature read-only logging (one row per tracked feature per keyframe).
// Pure diagnostic — never feeds the optimization. Default OFF (save_perfeat_reliability=0).
// Schema logs the RAW per-feature + per-interval state needed to recompute the consistency d^2
// OFFLINE in R2 (estimator real relative pose: wheel SE(2) + FOG yaw; triangulated depth; Sigma_uv).
#include <filesystem>
#include <fstream>
#include <mutex>
#include <stdexcept>
#include <string>

class PerFeatCsvLogger
{
public:
    PerFeatCsvLogger() = default;
    ~PerFeatCsvLogger() { close(); }

    void open(const std::string &path, const std::string &header)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        if (ofs_.is_open() && path_ == path)
            return;
        if (ofs_.is_open())
            ofs_.close();
        path_ = path;
        std::filesystem::path p(path_);
        if (p.has_parent_path())
            std::filesystem::create_directories(p.parent_path());
        ofs_.open(path_, std::ios::out | std::ios::trunc);
        if (!ofs_.is_open())
            throw std::runtime_error("Failed to open per-feature CSV: " + path_);
        ofs_ << header << "\n";
        ofs_.flush();
    }

    void append(const std::string &line)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        if (!ofs_.is_open())
            return;
        ofs_ << line << "\n";
    }

    void flush()
    {
        std::lock_guard<std::mutex> lock(mtx_);
        if (ofs_.is_open())
            ofs_.flush();
    }

    void close()
    {
        std::lock_guard<std::mutex> lock(mtx_);
        if (ofs_.is_open())
            ofs_.close();
    }

    bool isOpen() const { return ofs_.is_open(); }

private:
    std::string path_;
    std::ofstream ofs_;
    mutable std::mutex mtx_;
};
