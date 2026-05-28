from __future__ import annotations

from typing import Literal


CapProfileName = Literal["medium", "aggressive"]

CAP_PROFILES: dict[CapProfileName, dict[str, int]] = {
    "medium": {"expression": 25, "mutations": 10},
    "aggressive": {"expression": 100, "mutations": 40},
}


def resolve_cap_profile(profile: CapProfileName) -> tuple[int, int]:
    caps = CAP_PROFILES[profile]
    return caps["expression"], caps["mutations"]
