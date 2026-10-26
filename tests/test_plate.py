import random

import pytest

from vtrace import plate


def test_normalize_strips_symbols_and_keeps_wildcards_on_request():
    assert plate.normalize("sgx-12 34a") == "SGX1234A"
    assert plate.normalize("SGX12??", keep_wildcards=True) == "SGX12??"
    assert plate.normalize("SGX12??") == "SGX12"


def test_query_similarity_handles_wildcards_and_partial_plates():
    assert plate.query_similarity("SGX12??", "SGX1234A") == 1.0
    assert plate.query_similarity("1234", "SGX1234A") == 1.0          # partial, mid-plate
    assert plate.query_similarity("SGX9999", "SGX1234A") < 0.6
    assert plate.query_similarity("", "SGX1234A") == 0.0


def test_similarity_is_wildcard_aware():
    assert plate.similarity("SGX1234A", "SGX1234A") == 1.0
    assert plate.similarity("SG??234A", "SGX1234A") == 1.0
    assert plate.similarity("SGX1234A", "SBA9876C") < 0.3
    assert plate.similarity("", "SGX1234A") == 0.0


@pytest.mark.parametrize("level", ["clear", "partial", "blurred", "hidden"])
def test_degrade_levels(level):
    rng = random.Random(0)
    p = plate.random_plate(rng)
    d = plate.degrade(p, level, rng)
    if level == "hidden":
        assert d == ""
    elif level == "partial":
        assert len(d) == len(p) and "?" in d
    else:
        assert 0 < len(d) <= len(p)


def test_random_plate_format():
    p = plate.random_plate(random.Random(1))
    assert len(p) == 8 and p[0] == "S" and p[3:7].isdigit()
