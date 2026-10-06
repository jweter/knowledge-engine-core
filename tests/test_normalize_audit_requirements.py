from __future__ import annotations

import pytest

from engineering.normalize_audit_requirements import normalize


def test_deduplicates_overlapping_active_markers() -> None:
    lines = [
        'nvidia-cublas==13.6.0.2 ; python_version >= "3.12"',
        'nvidia-cublas==13.6.0.2 ; python_version < "4.0"',
    ]
    assert normalize(lines) == ["nvidia-cublas==13.6.0.2"]


def test_drops_inactive_markers() -> None:
    lines = [
        'demo==1.0 ; python_version < "2"',
        'demo==2.0 ; python_version >= "3"',
    ]
    assert normalize(lines) == ["demo==2.0"]


def test_conflicting_active_requirements_fail_closed() -> None:
    with pytest.raises(ValueError, match="conflicting active requirements"):
        normalize(["demo==1.0", "demo==2.0"])
