#pragma once

#include <string>

namespace qt::risk {

enum class KillSwitchLevel { Off, Soft, Hard };

struct KillSwitch {
    bool enabled{false};
    KillSwitchLevel level{KillSwitchLevel::Off};
    std::string reason;
};

}  // namespace qt::risk
