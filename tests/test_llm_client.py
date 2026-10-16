"""
Deterministic tests for the parameter handling of ``utils.llm_client``.

The real client wraps LangChain's ``ChatOpenAI``, which the CI does not install.
These tests put tiny fakes for ``langchain_openai``, ``langchain_core.messages``
and ``dotenv`` in ``sys.modules`` so they exercise only this project's logic:
which temperature / max_tokens actually reach the model. No network, no LLM.
"""

import importlib
import sys
import types

import pytest

import utils.config as config_module


class FakeChatOpenAI:
    """Records the kwargs it was built with; invoke() returns a fixed answer."""

    instances: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeChatOpenAI.instances.append(self)

    def invoke(self, messages):
        return types.SimpleNamespace(content="ok")


class _Message:
    def __init__(self, content):
        self.content = content


class RecordingLogger:
    """Stands in for the module logger so a warning can be asserted on."""

    def __init__(self):
        self.warnings = []

    def warning(self, msg, *args):
        self.warnings.append(msg % args if args else msg)

    def debug(self, *args, **kwargs):
        pass


@pytest.fixture
def llm_client(monkeypatch):
    """Import utils.llm_client against fakes, with a clean config singleton."""
    FakeChatOpenAI.instances = []
    fake_openai = types.ModuleType("langchain_openai")
    fake_openai.ChatOpenAI = FakeChatOpenAI
    fake_messages = types.ModuleType("langchain_core.messages")
    for name in ("HumanMessage", "SystemMessage", "AIMessage"):
        setattr(fake_messages, name, type(name, (_Message,), {}))
    fake_core = types.ModuleType("langchain_core")
    fake_core.messages = fake_messages
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: False

    monkeypatch.setitem(sys.modules, "langchain_openai", fake_openai)
    monkeypatch.setitem(sys.modules, "langchain_core", fake_core)
    monkeypatch.setitem(sys.modules, "langchain_core.messages", fake_messages)
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)
    monkeypatch.delitem(sys.modules, "utils.llm_client", raising=False)
    monkeypatch.setattr(config_module, "_settings", None)

    module = importlib.import_module("utils.llm_client")
    module.reset_llm_client()
    yield module
    module.reset_llm_client()
    sys.modules.pop("utils.llm_client", None)


def _client(module, **overrides):
    params = {
        "model": "test-model",
        "temperature": 0.7,
        "max_tokens": 100,
        "base_url": "http://localhost:9/v1",
        "api_key": "test",
    }
    params.update(overrides)
    return module.LLMClient(**params)


def test_chat_honours_zero_temperature(llm_client):
    client = _client(llm_client)
    client.chat([{"role": "user", "content": "hi"}], temperature=0.0)

    per_call = FakeChatOpenAI.instances[-1]
    assert per_call.kwargs["temperature"] == 0.0
    assert per_call.kwargs["max_tokens"] == 100  # untouched default kept


def test_generate_forwards_zero_temperature(llm_client):
    client = _client(llm_client)
    client.generate("hi", temperature=0.0, max_tokens=50)

    per_call = FakeChatOpenAI.instances[-1]
    assert per_call.kwargs["temperature"] == 0.0
    assert per_call.kwargs["max_tokens"] == 50


def test_chat_without_overrides_reuses_base_model(llm_client):
    client = _client(llm_client)
    client.chat([{"role": "user", "content": "hi"}])

    assert len(FakeChatOpenAI.instances) == 1  # no per-call model was built


def test_get_llm_client_defaults_come_from_config(llm_client, monkeypatch):
    monkeypatch.setenv("LLM_TEMPERATURE", "0.15")
    monkeypatch.setenv("LLM_MAX_TOKENS", "256")
    monkeypatch.setattr(config_module, "_settings", None)

    client = llm_client.get_llm_client()

    assert client.temperature == 0.15
    assert client.max_tokens == 256


def test_get_llm_client_warns_when_arguments_are_ignored(llm_client, monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(llm_client, "logger", recorder)

    first = llm_client.get_llm_client(temperature=0.2)
    second = llm_client.get_llm_client(temperature=0.9)

    assert second is first
    assert first.temperature == 0.2
    assert len(recorder.warnings) == 1
    assert "temperature" in recorder.warnings[0]


def test_get_llm_client_repeated_plain_calls_do_not_warn(llm_client, monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(llm_client, "logger", recorder)

    first = llm_client.get_llm_client(temperature=0.2)
    assert llm_client.get_llm_client() is first
    assert llm_client.get_llm_client(temperature=0.2) is first
    assert recorder.warnings == []
