"""Regression tests for the deterministic statistical decision boundary."""

from __future__ import annotations

import pytest

from spc_watchdog.nelson import evaluate_latest


def rules(values: list[float]) -> set[int]:
    """Return only rule numbers so each fixture states its intended contract."""

    return {item.rule for item in evaluate_latest(values, center=10.0, sigma=1.0)}


@pytest.mark.parametrize("value", [13.0001, 6.9999])
def test_rule_1_fires_strictly_beyond_three_sigma(value: float) -> None:
    assert 1 in rules([value])


@pytest.mark.parametrize("value", [13.0, 7.0, 10.0])
def test_rule_1_does_not_fire_on_or_inside_boundary(value: float) -> None:
    assert 1 not in rules([value])


def test_rule_2_fires_on_ninth_point_strictly_above_center() -> None:
    assert 2 not in rules([10.1] * 8)
    assert 2 in rules([10.1] * 9)


def test_rule_2_equality_breaks_sequence() -> None:
    assert 2 not in rules([10.1] * 8 + [10.0])


@pytest.mark.parametrize(
    "values",
    [
        [9.5, 9.4, 9.3, 9.2, 9.1, 9.0],
        [10.1, 10.2, 10.3, 10.4, 10.5, 10.6],
    ],
)
def test_rule_3_fires_on_sixth_strictly_monotonic_point(values: list[float]) -> None:
    assert 3 not in rules(values[:5])
    assert 3 in rules(values)


def test_rule_3_equality_breaks_sequence() -> None:
    assert 3 not in rules([10.0, 10.1, 10.2, 10.2, 10.3, 10.4])


def test_overlapping_rules_are_preserved() -> None:
    found = rules([10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 13.1])
    assert found == {1, 2, 3}


def test_sigma_must_be_positive() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        evaluate_latest([10.0], center=10.0, sigma=0.0)
