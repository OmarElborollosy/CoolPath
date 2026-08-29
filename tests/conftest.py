"""Pytest configuration for CoolPath test suite.

Monkeypatches FortyGuardService._client to None for all tests so the
synthesized fallback path runs instead of making real API calls.
This makes tests deterministic and fast without a live FortyGuard API key.

To run tests against the real API, set env var COOLPATH_LIVE_TESTS=1.
"""
from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def disable_live_fortyguard_client(monkeypatch):
    """Disable live FortyGuard API client during tests unless COOLPATH_LIVE_TESTS=1."""
    if os.getenv("COOLPATH_LIVE_TESTS") == "1":
        # Let the real client through
        yield
        return

    # Patch FortyGuardService.__init__ to never create a live client,
    # forcing all service calls through the synthesized baseline fallback.
    from app.services import fortyguard_service as fg_mod

    original_init = fg_mod.FortyGuardService.__init__

    def _patched_init(self, api_key=None, base_url=None):
        original_init(self, api_key=None, base_url=base_url)
        self._client = None  # force synthesized fallback

    monkeypatch.setattr(fg_mod.FortyGuardService, "__init__", _patched_init)
    yield
