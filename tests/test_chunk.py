import pytest

from app.chunking import chunk


def test_splits_with_overlap():
    parts = chunk("a" * 2000, size=800, overlap=100)
    assert [len(p) for p in parts] == [800, 800, 600]


def test_empty_text_returns_nothing():
    assert chunk("   ") == []


def test_invalid_sizes_rejected():
    with pytest.raises(ValueError):
        chunk("abc", size=100, overlap=100)
