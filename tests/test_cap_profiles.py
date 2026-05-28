from src.common.cap_profiles import CAP_PROFILES, resolve_cap_profile


def test_cap_profiles_include_medium_and_aggressive() -> None:
    assert CAP_PROFILES["medium"]["expression"] == 25
    assert CAP_PROFILES["medium"]["mutations"] == 10
    assert CAP_PROFILES["aggressive"]["expression"] == 100
    assert CAP_PROFILES["aggressive"]["mutations"] == 40


def test_resolve_cap_profile() -> None:
    assert resolve_cap_profile("medium") == (25, 10)
    assert resolve_cap_profile("aggressive") == (100, 40)
