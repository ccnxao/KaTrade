#pragma once

#include <string>

namespace qt::execution {

class OrderNormalizer {
public:
    std::string normalize_symbol(const std::string& raw) const;
    std::string normalize_side(const std::string& raw) const;
};

}  // namespace qt::execution
