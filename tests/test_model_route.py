import pytest

from applyapp.config import Settings
from applyapp.llm import ModelConfigError, chat_model, resolve_model
from applyapp.models import FormattedDocument


def _settings(**overrides) -> Settings:
    fields = {
        "anthropic_api_key": "sk-ant-test",
        "anthropic_model": "claude-sonnet-5",
        "openai_api_key": "",
        "llm_provider": "anthropic",
        "llm_model": "",
        "llm_api_key": "",
        "llm_base_url": "",
    }
    for step in ("analyze", "resume", "cover", "format", "critique"):
        fields[f"{step}_provider"] = ""
        fields[f"{step}_model"] = ""
        fields[f"{step}_api_key"] = ""
        fields[f"{step}_base_url"] = ""
    fields.update(overrides)
    return Settings(**fields)


def test_defaults_follow_anthropic():
    spec = resolve_model(_settings(), "resume")
    assert spec.provider == "anthropic"
    assert spec.model == "claude-sonnet-5"
    assert spec.api_key == "sk-ant-test"
    assert spec.base_url == ""


def test_step_override_uses_openai_compatible_host():
    spec = resolve_model(
        _settings(
            critique_provider="openai",
            critique_model="llama3.1",
            critique_base_url="http://localhost:11434/v1",
        ),
        "critique",
    )
    assert spec.provider == "openai"
    assert spec.model == "llama3.1"
    assert spec.base_url == "http://localhost:11434/v1"
    assert spec.api_key == "ollama"
    assert "ollama" not in spec.label()


def test_model_prefix_sets_provider():
    spec = resolve_model(
        _settings(openai_api_key="sk-openai", format_model="openai:gpt-4.1"),
        "format",
    )
    assert spec.provider == "openai"
    assert spec.model == "gpt-4.1"
    assert spec.api_key == "sk-openai"


def test_step_key_beats_shared_key():
    spec = resolve_model(
        _settings(llm_api_key="shared", critique_api_key="critic", critique_provider="openai", critique_model="llama3.1"),
        "critique",
    )
    assert spec.api_key == "critic"


def test_provider_prefix_mismatch_is_an_error():
    settings = _settings(critique_provider="anthropic", critique_model="openai:llama3.1")
    with pytest.raises(ModelConfigError, match="does not match"):
        resolve_model(settings, "critique")


def test_formatted_blocks_accept_a_json_string():
    raw = '{"blocks":[{"kind":"name","text":"Alex Rivera"}]}'
    doc = FormattedDocument.model_validate({"blocks": raw})
    assert doc.blocks[0].text == "Alex Rivera"


def test_sonnet_5_does_not_send_temperature():
    model = chat_model(_settings(), "analyze")
    assert model.temperature is None
    older = chat_model(_settings(anthropic_model="claude-sonnet-4-5"), "analyze")
    assert older.temperature == 0.2


def test_openai_without_a_model_name_is_an_error():
    settings = _settings(
        anthropic_api_key="",
        llm_provider="openai",
        openai_api_key="sk-openai",
    )
    with pytest.raises(ModelConfigError, match="LLM_MODEL"):
        resolve_model(settings, "analyze")
