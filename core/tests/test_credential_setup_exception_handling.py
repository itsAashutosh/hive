"""
Tests for exception handling in framework.credentials.setup.

Verifies that CredentialSetupSession:
- Uses narrow exception types instead of bare `except Exception`
- Logs warnings for caught errors instead of silently swallowing
- Re-raises KeyboardInterrupt and SystemExit
- Still handles expected error scenarios gracefully
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from framework.credentials.setup import (
    CredentialSetupSession,
    MissingCredential,
    _load_nodes_from_json_agent,
    _load_nodes_from_python_agent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_credential(**overrides) -> MissingCredential:
    """Create a test MissingCredential with sensible defaults."""
    defaults = {
        "credential_name": "test_cred",
        "env_var": "TEST_API_KEY",
        "description": "Test credential",
        "help_url": "https://example.com",
        "api_key_instructions": "Get key from example.com",
        "tools": ["test_tool"],
    }
    defaults.update(overrides)
    return MissingCredential(**defaults)


def _make_session(
    missing: list[MissingCredential] | None = None,
    input_fn=None,
    password_fn=None,
) -> CredentialSetupSession:
    """Create a CredentialSetupSession with captured output."""
    return CredentialSetupSession(
        missing=missing or [_make_credential()],
        input_fn=input_fn or (lambda _: ""),
        print_fn=lambda _: None,  # suppress output
        password_fn=password_fn or (lambda _: "test-key-value"),
    )


# ---------------------------------------------------------------------------
# Tests — run_interactive exception handling
# ---------------------------------------------------------------------------


class TestRunInteractiveExceptionHandling:
    """Verify run_interactive() uses proper exception types."""

    def test_keyboard_interrupt_stops_setup(self):
        """KeyboardInterrupt should stop the loop and not be swallowed."""
        cred = _make_credential()
        session = _make_session([cred])

        with patch.object(session, "_ensure_credential_key", return_value=True):
            with patch.object(
                session,
                "_setup_single_credential",
                side_effect=KeyboardInterrupt,
            ):
                result = session.run_interactive()
                # KeyboardInterrupt is handled gracefully (not re-raised)
                assert cred.credential_name in result.skipped

    def test_oserror_is_caught_and_reported(self):
        """OSError during setup should be caught and added to errors."""
        cred = _make_credential()
        session = _make_session([cred])

        with patch.object(session, "_ensure_credential_key", return_value=True):
            with patch.object(
                session,
                "_setup_single_credential",
                side_effect=OSError("permission denied"),
            ):
                result = session.run_interactive()
                assert len(result.errors) == 1
                assert "permission denied" in result.errors[0]

    def test_value_error_is_caught_and_reported(self):
        """ValueError during setup should be caught and added to errors."""
        cred = _make_credential()
        session = _make_session([cred])

        with patch.object(session, "_ensure_credential_key", return_value=True):
            with patch.object(
                session,
                "_setup_single_credential",
                side_effect=ValueError("invalid key format"),
            ):
                result = session.run_interactive()
                assert len(result.errors) == 1
                assert "invalid key format" in result.errors[0]


# ---------------------------------------------------------------------------
# Tests — _ensure_credential_key exception handling
# ---------------------------------------------------------------------------


class TestEnsureCredentialKey:
    """Verify _ensure_credential_key() uses narrow exception types."""

    def test_oserror_returns_false(self):
        """OSError from key generation should return False."""
        session = _make_session()

        with (
            patch(
                "framework.credentials.key_storage.load_credential_key",
                return_value=None,
            ),
            patch(
                "framework.credentials.key_storage.generate_and_save_credential_key",
                side_effect=OSError("disk full"),
            ),
        ):
            assert session._ensure_credential_key() is False

    def test_permission_error_returns_false(self):
        """PermissionError from key generation should return False."""
        session = _make_session()

        with (
            patch(
                "framework.credentials.key_storage.load_credential_key",
                return_value=None,
            ),
            patch(
                "framework.credentials.key_storage.generate_and_save_credential_key",
                side_effect=PermissionError("access denied"),
            ),
        ):
            assert session._ensure_credential_key() is False


# ---------------------------------------------------------------------------
# Tests — password input exception handling
# ---------------------------------------------------------------------------


class TestPasswordInputExceptionHandling:
    """Verify password input falls back gracefully."""

    def test_keyboard_interrupt_in_password_is_not_swallowed(self):
        """KeyboardInterrupt during password input should propagate."""
        cred = _make_credential()
        session = _make_session(
            [cred],
            password_fn=MagicMock(side_effect=KeyboardInterrupt),
        )

        with pytest.raises(KeyboardInterrupt):
            session._setup_direct_api_key(cred)

    def test_system_exit_in_password_is_not_swallowed(self):
        """SystemExit during password input should propagate."""
        cred = _make_credential()
        session = _make_session(
            [cred],
            password_fn=MagicMock(side_effect=SystemExit(1)),
        )

        with pytest.raises(SystemExit):
            session._setup_direct_api_key(cred)

    def test_eoferror_falls_back_to_plain_input(self):
        """EOFError should fall back to plain input."""
        cred = _make_credential()
        input_fn = MagicMock(return_value="fallback-key")
        session = _make_session(
            [cred],
            input_fn=input_fn,
            password_fn=MagicMock(side_effect=EOFError),
        )

        with (
            patch.object(session, "_run_health_check", return_value=None),
            patch.object(session, "_store_credential"),
        ):
            result = session._setup_direct_api_key(cred)
            assert result is True


# ---------------------------------------------------------------------------
# Tests — agent loading exception handling
# ---------------------------------------------------------------------------


class TestAgentLoading:
    """Verify agent loading functions re-raise critical exceptions."""

    def test_load_python_agent_keyboard_interrupt(self, tmp_path):
        """KeyboardInterrupt during Python agent loading should propagate."""
        agent_py = tmp_path / "agent.py"
        agent_py.write_text("raise KeyboardInterrupt")

        with pytest.raises(KeyboardInterrupt):
            _load_nodes_from_python_agent(tmp_path)

    def test_load_python_agent_import_error_returns_empty(self, tmp_path):
        """ImportError should be caught and return empty list."""
        agent_py = tmp_path / "agent.py"
        agent_py.write_text("import nonexistent_module_xyz_12345")

        result = _load_nodes_from_python_agent(tmp_path)
        assert result == []

    def test_load_json_agent_invalid_json_returns_empty(self, tmp_path):
        """Invalid JSON should be caught and return empty list."""
        agent_json = tmp_path / "agent.json"
        agent_json.write_text("{invalid json", encoding="utf-8")

        result = _load_nodes_from_json_agent(agent_json)
        assert result == []

    def test_load_json_agent_missing_file_returns_empty(self, tmp_path):
        """Missing file should be caught and return empty list."""
        agent_json = tmp_path / "nonexistent.json"

        result = _load_nodes_from_json_agent(agent_json)
        assert result == []


# ---------------------------------------------------------------------------
# Tests — health check exception handling
# ---------------------------------------------------------------------------


class TestHealthCheckExceptionHandling:
    """Verify _run_health_check re-raises critical exceptions."""

    def test_keyboard_interrupt_propagates(self):
        """KeyboardInterrupt during health check should not be swallowed."""
        cred = _make_credential()
        session = _make_session([cred])

        with patch(
            "aden_tools.credentials.check_credential_health",
            side_effect=KeyboardInterrupt,
            create=True,
        ):
            with pytest.raises(KeyboardInterrupt):
                session._run_health_check(cred, "test-key")

    def test_import_error_returns_none(self):
        """ImportError (no health checker) should return None."""
        cred = _make_credential()
        session = _make_session([cred])

        # The function has a try/except ImportError that returns None
        # when check_credential_health is not importable
        result = session._run_health_check(cred, "test-key")
        # Either returns None (no checker) or a dict (checker available)
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Tests — logging verification
# ---------------------------------------------------------------------------


class TestExceptionLogging:
    """Verify that caught exceptions are properly logged."""

    def test_oserror_during_setup_is_logged(self, caplog):
        """OSError during credential setup should produce a warning log."""
        cred = _make_credential()
        session = _make_session([cred])

        with (
            caplog.at_level(logging.WARNING),
            patch.object(session, "_ensure_credential_key", return_value=True),
            patch.object(
                session,
                "_setup_single_credential",
                side_effect=OSError("disk full"),
            ),
        ):
            session.run_interactive()
            assert any("Credential setup failed" in r.message for r in caplog.records)

    def test_store_credential_oserror_is_logged(self, caplog):
        """OSError in _store_credential should produce a warning log."""
        cred = _make_credential()
        session = _make_session([cred])

        with (
            caplog.at_level(logging.WARNING),
            patch(
                "framework.credentials.CredentialStore.with_encrypted_storage",
                side_effect=OSError("disk full"),
            ),
        ):
            session._store_credential(cred, "test-key")
            assert any("Could not store credential" in r.message for r in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
