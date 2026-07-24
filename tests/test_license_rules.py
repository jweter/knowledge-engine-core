from __future__ import annotations

import pytest

from knowledge_engine.license_rules import evaluate_license, license_deed_url


def test_missing_license_is_incomplete() -> None:
    assert evaluate_license(None) == "incomplete_missing_license"


def test_cc_by_passes() -> None:
    assert evaluate_license("CC BY 4.0") == "passed"


def test_cc0_passes() -> None:
    assert evaluate_license("CC0") == "passed"


def test_cc_by_nc_nd_is_unsupported() -> None:
    assert evaluate_license("CC BY-NC-ND 4.0") == "unsupported_license_basis"


def test_lowercase_license_is_normalized() -> None:
    assert evaluate_license("cc by") == "passed"


@pytest.mark.parametrize(
    "license_type,expected_url",
    [
        ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
        ("CC BY", "https://creativecommons.org/licenses/by/4.0/"),
        ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
        ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    ],
)
def test_license_deed_url_maps_allowed_licenses(license_type: str, expected_url: str) -> None:
    assert license_deed_url(license_type) == expected_url


def test_license_deed_url_rejects_unsupported_licenses() -> None:
    with pytest.raises(ValueError, match="Unsupported license type"):
        license_deed_url("CC BY-NC-ND 4.0")
