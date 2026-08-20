"""Isolate serving env: never inherit TRAINED_PATH=trained from .env."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_trained_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAINED_PATH", "shadow")
