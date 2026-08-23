import pytest

from rule_tester.config import ConfigurationError, ENVIRONMENT_KEYS, IntegrationConfig


def test_configuration_reads_only_named_integration_variables(monkeypatch):
    for key in ENVIRONMENT_KEYS:
        monkeypatch.setenv(key, "3306" if key.endswith("_PORT") else key.lower())
    monkeypatch.setenv("DATABASE_URL", "must-not-be-used")

    config = IntegrationConfig.from_environment()

    assert config.port == 3306
    assert config.host == "mysql_integration_host"
    assert config.password == "mysql_integration_password"
    assert "mysql_integration_password" not in repr(config)


def test_missing_configuration_error_does_not_include_secret(monkeypatch):
    for key in ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MYSQL_INTEGRATION_PASSWORD", "top-secret-value")

    with pytest.raises(ConfigurationError) as caught:
        IntegrationConfig.from_environment()

    assert "top-secret-value" not in str(caught.value)
