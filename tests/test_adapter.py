"""Tests for core/adapter.py - UniversalLLM class."""
import pytest
from unittest.mock import MagicMock, patch


class TestUniversalLLMInit:
    def test_init_sets_model(self):
        with patch("core.adapter.OpenAI"):
            from core.adapter import UniversalLLM
            llm = UniversalLLM("key-123", "https://api.example.com/v1", "gpt-4")
        assert llm.model == "gpt-4"

    def test_init_creates_openai_client(self):
        with patch("core.adapter.OpenAI") as MockOpenAI:
            from core.adapter import UniversalLLM
            llm = UniversalLLM("key-123", "https://api.example.com/v1", "gpt-4")
        MockOpenAI.assert_called_once()
        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs.get("api_key") == "key-123"
        assert call_kwargs.get("base_url") == "https://api.example.com/v1"

    def test_init_stores_client_reference(self):
        mock_client = MagicMock()
        with patch("core.adapter.OpenAI", return_value=mock_client):
            from core.adapter import UniversalLLM
            llm = UniversalLLM("key-123", "https://api.example.com/v1", "gpt-4")
        assert llm.client is mock_client

    def test_init_timeout_is_120_seconds(self):
        with patch("core.adapter.OpenAI") as MockOpenAI:
            from core.adapter import UniversalLLM
            UniversalLLM("k", "https://base.url/v1", "model-x")
        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs.get("timeout") == 120

    def test_different_models_stored_correctly(self):
        with patch("core.adapter.OpenAI"):
            from core.adapter import UniversalLLM
            llm1 = UniversalLLM("k1", "https://a.com/v1", "claude-opus")
            llm2 = UniversalLLM("k2", "https://b.com/v1", "gpt-3.5-turbo")
        assert llm1.model == "claude-opus"
        assert llm2.model == "gpt-3.5-turbo"


class TestUniversalLLMChat:
    def _make_llm(self, response_text="Hello!"):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = response_text
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("core.adapter.OpenAI", return_value=mock_client):
            from core.adapter import UniversalLLM
            llm = UniversalLLM("key", "https://api.example.com/v1", "test-model")
        return llm, mock_client

    def test_chat_returns_string_response(self):
        llm, _ = self._make_llm("This is a response.")
        result = llm.chat("What is 2+2?")
        assert result == "This is a response."

    def test_chat_sends_user_role_message(self):
        llm, mock_client = self._make_llm()
        llm.chat("Tell me a joke.")
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Tell me a joke."

    def test_chat_uses_correct_model(self):
        llm, mock_client = self._make_llm()
        llm.chat("Hello")
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "test-model"

    def test_chat_called_once_per_invocation(self):
        llm, mock_client = self._make_llm()
        llm.chat("First")
        llm.chat("Second")
        assert mock_client.chat.completions.create.call_count == 2

    def test_chat_empty_prompt_still_sends_request(self):
        llm, mock_client = self._make_llm("empty response")
        result = llm.chat("")
        mock_client.chat.completions.create.assert_called_once()
        assert result == "empty response"

    def test_chat_raises_if_api_raises(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        with patch("core.adapter.OpenAI", return_value=mock_client):
            from core.adapter import UniversalLLM
            llm = UniversalLLM("key", "https://api.example.com/v1", "model")
        with pytest.raises(Exception, match="API error"):
            llm.chat("Will this fail?")
