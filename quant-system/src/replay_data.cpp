#include "qt/replay_data.hpp"

#include "qt/history_client.hpp"

#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace qt {

namespace {

std::vector<std::string> split_csv_line(const std::string& line) {
    std::vector<std::string> fields;
    std::stringstream stream(line);
    std::string field;
    while (std::getline(stream, field, ',')) {
        fields.push_back(field);
    }
    return fields;
}

double parse_double(const std::string& value, const std::string& field_name) {
    try {
        return std::stod(value);
    } catch (const std::exception&) {
        throw std::runtime_error("failed to parse numeric field: " + field_name +
                                 " value=" + value);
    }
}

std::vector<Bar> load_bars(const std::string& path) {
    std::ifstream input(path);
    if (!input.is_open()) {
        throw std::runtime_error("failed to open replay file: " + path);
    }

    std::vector<Bar> bars;
    std::string line;
    bool header_skipped = false;

    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }

        if (!header_skipped) {
            header_skipped = true;
            continue;
        }

        const auto fields = split_csv_line(line);
        if (fields.size() != 8) {
            throw std::runtime_error("expected 8 CSV fields but got " +
                                     std::to_string(fields.size()));
        }

        const std::string& timestamp = fields[0];
        bars.push_back(Bar{timestamp,
                           {fields[1], fields[2]},
                           parse_double(fields[3], "open"),
                           parse_double(fields[4], "high"),
                           parse_double(fields[5], "low"),
                           parse_double(fields[6], "close"),
                           parse_double(fields[7], "volume")});
    }
    return bars;
}

std::vector<BacktestStep> steps_from_bars(std::vector<Bar> bars) {
    std::sort(bars.begin(), bars.end(), [](const Bar& lhs, const Bar& rhs) {
        if (lhs.timestamp != rhs.timestamp) {
            return lhs.timestamp < rhs.timestamp;
        }
        return instrument_key(lhs.instrument) < instrument_key(rhs.instrument);
    });

    std::vector<BacktestStep> steps;
    for (const auto& bar : bars) {
        if (steps.empty() || steps.back().label != bar.timestamp) {
            steps.push_back(BacktestStep{bar.timestamp, {}});
        }
        steps.back().bars.push_back(bar);
    }
    return steps;
}

}  // namespace

std::vector<BacktestStep> CsvReplayLoader::load(const std::string& path) {
    return steps_from_bars(load_bars(path));
}

std::vector<BacktestStep> CsvReplayLoader::load_many(
    const std::vector<std::string>& paths) {
    std::vector<Bar> bars;
    for (const auto& path : paths) {
        auto loaded = load_bars(path);
        bars.insert(bars.end(), loaded.begin(), loaded.end());
    }
    return steps_from_bars(std::move(bars));
}

std::vector<BacktestStep> ReplayDataSource::load(const RuntimeConfig& config) {
    if (config.history_mode == "remote") {
        HistoryDataClient client(config.history_server_url,
                                 config.history_cache_dir,
                                 config.history_cache_ttl_seconds);
        const auto result = client.ensure_contracts_cached(config.history_contracts);
        return CsvReplayLoader::load_many(result.cached_paths);
    }
    return CsvReplayLoader::load(config.replay_path);
}

}  // namespace qt
