#include "qt/replay_data.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>

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

}  // namespace

std::vector<BacktestStep> CsvReplayLoader::load(const std::string& path) {
    std::ifstream input(path);
    if (!input.is_open()) {
        throw std::runtime_error("failed to open replay file: " + path);
    }

    std::vector<BacktestStep> steps;
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
        if (steps.empty() || steps.back().label != timestamp) {
            steps.push_back(BacktestStep{timestamp, {}});
        }

        steps.back().bars.push_back(Bar{timestamp,
                                        {fields[1], fields[2]},
                                        parse_double(fields[3], "open"),
                                        parse_double(fields[4], "high"),
                                        parse_double(fields[5], "low"),
                                        parse_double(fields[6], "close"),
                                        parse_double(fields[7], "volume")});
    }

    return steps;
}

}  // namespace qt
