import pytest
from src.cleaning.clean import safe_float, derive_delay_category


def test_safe_float_with_none():
    assert safe_float(None) == 0.0


def test_safe_float_with_nan():
    assert safe_float(float("nan")) == 0.0


def test_safe_float_with_valid():
    assert safe_float(15.5) == 15.5


def test_delay_category_on_time():
    assert derive_delay_category(0.0, False) == "ON_TIME"


def test_delay_category_cancelled():
    assert derive_delay_category(0.0, True) == "CANCELLED"


def test_delay_category_severe():
    assert derive_delay_category(90.0, False) == "SEVERE"


def test_delay_category_minor():
    assert derive_delay_category(10.0, False) == "MINOR"


def test_delay_category_moderate():
    assert derive_delay_category(45.0, False) == "MODERATE"