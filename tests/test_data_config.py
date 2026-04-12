"""Минимальные проверки конфигурации без GUI."""
import re

from data_config import APP_VERSION


def test_app_version_semver_like():
    assert re.match(r"^\d+\.\d+\.\d+$", APP_VERSION), f"unexpected APP_VERSION: {APP_VERSION!r}"
