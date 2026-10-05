"""Isolated numeric and metadata checks, not a scientific reference bank."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from proof_of_work import integer, match_contract, number


@pytest.mark.parametrize("value", ["0", "1.0", " 5 ", 30, 123000.0])
def test_integer_equivalent_formats(value):
    assert integer(value) == int(float(value))


@pytest.mark.parametrize("value", [True, -1, "1.1", "nan", "inf"])
def test_integer_invalid_values(value):
    with pytest.raises(AssertionError):
        integer(value)


@pytest.mark.parametrize("value", [0.0, 0.2, 1.0, -0.1])
def test_numeric_parser_has_no_private_effect_strength(value):
    assert number(value) == value


def test_metadata_allows_harmless_extra_fields():
    match_contract({"classifier": {"trees": 200.0, "seed": 0, "note": "same settings"},
                    "description": "extra context"}, {"classifier": {"trees": 200, "seed": 0}})


@pytest.mark.parametrize("actual", [
    {}, {"classifier": {"trees": 201, "seed": 0}},
    {"classifier": {"trees": 200, "seed": True}},
])
def test_metadata_requires_declared_settings(actual):
    with pytest.raises(AssertionError):
        match_contract(actual, {"classifier": {"trees": 200, "seed": 0}})
