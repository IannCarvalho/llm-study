"""
Tests for ``utils.config`` and ``utils.models`` after the Pydantic V2 migration.

- Importing them must not emit ``PydanticDeprecatedSince20`` (checked in a
  subprocess, so the already-imported models of this test session are untouched).
- Settings fields map to the environment variables of the same name without the
  removed ``Field(env=...)`` argument.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import utils.config as config_module

ROOT = Path(__file__).resolve().parent.parent


def test_config_and_models_import_without_pydantic_deprecations():
    code = (
        "import warnings\n"
        "from pydantic.warnings import PydanticDeprecatedSince20\n"
        "warnings.simplefilter('error', PydanticDeprecatedSince20)\n"
        "import utils.config, utils.models\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=str(ROOT)),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_settings_read_environment_variables_by_field_name(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.0")
    monkeypatch.setenv("PINECONE_API_KEY", "pc-test")

    settings = config_module.Settings()

    assert settings.ollama_model == "test-model"
    assert settings.ollama_base_url == "http://localhost:1234/v1"
    assert settings.llm_temperature == 0.0
    assert settings.pinecone_api_key == "pc-test"


def test_settings_keep_their_validation_bounds(monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "5")
    with pytest.raises(ValidationError):
        config_module.Settings()
