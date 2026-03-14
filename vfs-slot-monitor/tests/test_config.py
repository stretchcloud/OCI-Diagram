"""Tests for configuration loading."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from vfs_monitor.config import AppConfig, CenterConfig, EnvConfig, load_config


def test_center_config_defaults():
    c = CenterConfig(country_code="fra", country_name="France")
    assert c.enabled is False
    assert c.centers == ["London"]
    assert c.mission_code == ""


def test_app_config_enabled_centers():
    config = AppConfig(
        centers=[
            CenterConfig(country_code="fra", country_name="France", enabled=True),
            CenterConfig(country_code="nld", country_name="Netherlands", enabled=False),
            CenterConfig(country_code="ita", country_name="Italy", enabled=True),
        ]
    )
    enabled = config.enabled_centers
    assert len(enabled) == 2
    assert enabled[0].country_code == "fra"
    assert enabled[1].country_code == "ita"


def test_env_config_admin_ids():
    env = EnvConfig(
        telegram_bot_token="test",
        telegram_admin_ids="123,456,789",
        vfs_email="test@test.com",
        vfs_password="pass",
    )
    assert env.admin_ids == [123, 456, 789]


def test_env_config_empty_admin_ids():
    env = EnvConfig(
        telegram_bot_token="test",
        telegram_admin_ids="",
        vfs_email="test@test.com",
        vfs_password="pass",
    )
    assert env.admin_ids == []


def test_load_config_from_yaml():
    yaml_data = {
        "centers": [
            {
                "country_code": "fra",
                "country_name": "France",
                "mission_code": "fra",
                "center_code": "FRUK",
                "visa_category_code": "002",
                "enabled": True,
            }
        ],
        "polling": {
            "slot_check_interval_seconds": 10,
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(yaml_data, f)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    assert len(config.centers) == 1
    assert config.centers[0].country_code == "fra"
    assert config.centers[0].enabled is True
    assert config.polling.slot_check_interval_seconds == 10


def test_load_config_no_file():
    """Loading with no file should return defaults."""
    config = load_config("/nonexistent/path.yaml")
    assert len(config.centers) == 0
    assert config.polling.slot_check_interval_seconds == 8
