"""Tests for configuration loading."""

import os
import tempfile

import pytest
import yaml

from vfs_monitor.config import AppConfig, CenterConfig, EnvConfig, load_config


def test_center_config_defaults():
    c = CenterConfig(country_code="fr", country_name="France")
    assert c.enabled is False
    assert c.city == "London"
    assert c.from_country == "gb"
    assert c.issuer_id == ""


def test_app_config_enabled_centers():
    config = AppConfig(
        centers=[
            CenterConfig(country_code="fr", country_name="France", enabled=True),
            CenterConfig(country_code="nl", country_name="Netherlands", enabled=False),
            CenterConfig(country_code="it", country_name="Italy", enabled=True),
        ]
    )
    enabled = config.enabled_centers
    assert len(enabled) == 2
    assert enabled[0].country_code == "fr"
    assert enabled[1].country_code == "it"


def test_env_config_admin_ids():
    env = EnvConfig(
        telegram_bot_token="test",
        telegram_admin_ids="123,456,789",
        tls_email="test@test.com",
        tls_password="pass",
    )
    assert env.admin_ids == [123, 456, 789]


def test_env_config_empty_admin_ids():
    env = EnvConfig(
        telegram_bot_token="test",
        telegram_admin_ids="",
        tls_email="test@test.com",
        tls_password="pass",
    )
    assert env.admin_ids == []


def test_load_config_from_yaml():
    yaml_data = {
        "centers": [
            {
                "country_code": "fr",
                "country_name": "France",
                "from_country": "gb",
                "issuer_id": "gbLON2fr",
                "city": "London",
                "enabled": True,
            }
        ],
        "polling": {
            "slot_check_interval_seconds": 300,
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(yaml_data, f)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    assert len(config.centers) == 1
    assert config.centers[0].country_code == "fr"
    assert config.centers[0].issuer_id == "gbLON2fr"
    assert config.centers[0].enabled is True
    assert config.polling.slot_check_interval_seconds == 300


def test_load_config_no_file():
    """Loading with no file should return defaults."""
    config = load_config("/nonexistent/path.yaml")
    assert len(config.centers) == 0
    assert config.polling.slot_check_interval_seconds == 300
