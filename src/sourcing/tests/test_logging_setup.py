"""Smoke test for logging configuration."""

from logging_setup import configure_logging


def test_configure_logging_does_not_raise() -> None:
    configure_logging("INFO")
