from src.core.version_check import compare_versions, normalize_version_text, parse_version


def test_normalize_version_text_strips_v() -> None:
    assert normalize_version_text("v0.4.0") == "0.4.0"
    assert normalize_version_text("0.4.0") == "0.4.0"


def test_normalize_version_text_extracts_from_sentence() -> None:
    assert normalize_version_text("release v0.1.5") == "0.1.5"


def test_parse_version_supports_prerelease() -> None:
    pv = parse_version("0.3.0b0")
    assert pv is not None
    assert pv.parts[:3] == (0, 3, 0)
    assert pv.pre_kind == "b"
    assert pv.pre_num == 0


def test_compare_versions_numeric() -> None:
    assert compare_versions("0.4.0", "0.3.0") == 1
    assert compare_versions("v0.3.0", "0.3.0") == 0


def test_compare_versions_prerelease_ordering() -> None:
    assert compare_versions("0.3.0b0", "0.3.0") == -1
    assert compare_versions("0.3.0rc1", "0.3.0") == -1
    assert compare_versions("0.3.0a1", "0.3.0b0") == -1


def test_compare_versions_invalid_returns_none() -> None:
    assert compare_versions("not-a-version", "0.1.0") is None
