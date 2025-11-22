#!/usr/bin/env python

"""Tests for `ifcb_prometheus_exporter` package."""

import pytest


@pytest.fixture
def example_data() -> str:
    return "hi"


def test_content(example_data):
    """Sample pytest test function with the pytest fixture as an argument."""
    assert example_data == "hi"
