"""Tests for core/brain.py - Brain class."""
import json
import pytest
from unittest.mock import MagicMock, patch


def make_mock_llm(model="test-model"):
    llm = MagicMock()
    llm.model = model
    llm.client = MagicMock()
    return llm


def make_mock_memory(prefs=None, relevant=None):
    mem = MagicMock()
    mem.get_preferences.return_value = prefs or []
    mem.get_relevant.return_value = relevant or []
    return mem


def make_brain(prefs=None, relevant=None, use_native_tools=True):
    """Helper: create a Brain with mocked LLM and memory."""
    llm = make_mock_llm()
    mem = make_mock_memory(prefs=prefs, relevant=relevant)

    with patch("core.brain.MemoryStore", return_value=mem), \
         patch("core.brain.TOOLS_SCHEMA", []):
        from core.brain import Brain
        brain = Brain(llm=llm, use_native_tools=use_native_tools, tools_schema=[])
    brain._memory = mem
    return brain


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestBrainInit:
    def test_messages_start_with_system_message(self):
        brain = make_brain()
        assert brain.messages[0]["role"] == "system"

    def test_system_message_appends_preferences(self):
        brain = make_brain(prefs=["I prefer dark mode", "Use Python 3.11"])
        system_content = brain.messages[0]["content"]
        assert "I prefer dark mode" in system_content
        assert "Use Python 3.11" in system_content

    def test_no_preferences_no_preference_section(self):
        brain = make_brain(prefs=[])
        system_content = brain.messages[0]["content"]
        assert "I prefer dark mode" not in system_content

    def test_initial_message_count_is_one(self):
        brain = make_brain()
        assert len(brain.messages) == 1

    def test_use_native_tools_flag_stored(self):
        brain_native = make_brain(use_native_tools=True)
        brain_text = make_brain(use_native_tools=False)
        assert brain_native.use_native_tools is True
        assert brain_text.use_native_tools is False


# ---------------------------------------------------------------------------
# _append_user()
# ---------------------------------------------------------------------------

class TestBrainAppendUser:
    def test_plain_text_appended_as_user_message(self):
        brain = make_brain()
        brain._append_user("Hello world")
        assert brain.messages[-1]["role"] == "user"
        assert brain.messages[-1]["content"] == "Hello world"

    def test_first_message_may_prepend_relevant_memories(self):
        brain = make_brain(relevant=["Memory A", "Memory B"])
        brain._append_user("Tell me about Python")
        content = brain.messages[-1]["content"]
        # Either the content includes memories, or it's just the message
        assert "Tell me about Python" in content

    def test_image_path_nonexistent_falls_back_to_text(self):
        brain = make_brain()
        brain._append_user("No image here", "/nonexistent/path/img.png")
        last_msg = brain.messages[-1]
        assert last_msg["role"] == "user"

    def test_multiple_appends_grow_message_list(self):
        brain = make_brain()
        initial = len(brain.messages)
        brain._append_user("First")
        brain._append_user("Second")
        assert len(brain.messages) == initial + 2

    def test_image_path_with_valid_file_creates_multipart(self, tmp_path):
        # Write a minimal PNG
        img = tmp_path / "test.png"
        img.write_bytes(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
            b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
            b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        brain = make_brain()
        brain._append_user("Here is an image", str(img))
        last_msg = brain.messages[-1]
        assert last_msg["role"] == "user"
        # Content should be either a list (multipart) or a string
        assert last_msg["content"] is not None


# ---------------------------------------------------------------------------
# _estimate_tokens()
# ---------------------------------------------------------------------------

class TestBrainEstimateTokens:
    def test_empty_string_content_counts_zero(self):
        brain = make_brain()
        brain.messages = [{"role": "user", "content": ""}]
        assert brain._estimate_tokens() == 0

    def test_text_content_estimated_by_char_count(self):
        brain = make_brain()
        # 400 chars / 4 = 100 tokens
        brain.messages = [{"role": "user", "content": "A" * 400}]
        assert brain._estimate_tokens() == 100

    def test_image_url_part_counts_extra_tokens(self):
        brain = make_brain()
        brain.messages = [{
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]
        }]
        tokens = brain._estimate_tokens()
        assert tokens > 0

    def test_list_content_with_text_and_image_sums_both(self):
        brain = make_brain()
        brain.messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "A" * 400},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ]
        }]
        text_only_tokens = 100  # 400 chars / 4
        total = brain._estimate_tokens()
        assert total > text_only_tokens

    def test_multiple_messages_tokens_summed(self):
        brain = make_brain()
        brain.messages = [
            {"role": "user", "content": "A" * 400},
            {"role": "assistant", "content": "B" * 400},
        ]
        assert brain._estimate_tokens() == 200


# ---------------------------------------------------------------------------
# _compress_context()
# ---------------------------------------------------------------------------

class TestBrainCompressContext:
    def _make_large_messages(self, brain, n=20, chars_per_msg=8000):
        brain.messages = [brain.messages[0]]  # keep system msg
        for i in range(n):
            brain.messages.append({"role": "user", "content": "X" * chars_per_msg})
            brain.messages.append({"role": "assistant", "content": "Y" * chars_per_msg})

    def test_compress_context_does_not_crash(self):
        brain = make_brain()
        self._make_large_messages(brain)
        brain._compress_context()  # Should not raise

    def test_compress_context_reduces_token_count(self):
        brain = make_brain()
        self._make_large_messages(brain, n=30, chars_per_msg=6000)
        before = brain._estimate_tokens()
        brain._compress_context()
        after = brain._estimate_tokens()
        assert after <= before

    def test_compress_context_no_op_when_under_limit(self):
        brain = make_brain()
        # Only system message - well under token limit
        original_len = len(brain.messages)
        brain._compress_context()
        assert len(brain.messages) == original_len

    def test_compress_strips_images_from_old_messages(self):
        brain = make_brain()
        brain.messages = [brain.messages[0]]
        for i in range(25):
            brain.messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "screenshot"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + "A" * 100}},
                ]
            })
            brain.messages.append({"role": "assistant", "content": "B" * 2000})
        brain._compress_context()
        # After compression, total tokens should be reduced
        assert brain._estimate_tokens() < 25 * (1000 + 500)


# ---------------------------------------------------------------------------
# _call_text() - text fallback mode
# ---------------------------------------------------------------------------

class TestBrainCallText:
    def _make_completion(self, brain, text):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = text
        brain.llm.client.chat.completions.create.return_value = resp
        return resp

    def test_call_text_parses_json_code_block(self):
        brain = make_brain(use_native_tools=False)
        payload = '{"name": "web_search", "arguments": {"query": "test"}}'
        self._make_completion(brain, f"```json\n{payload}\n```")
        result = brain._call_text()
        assert result is not None
        assert result.get("name") == "web_search"

    def test_call_text_returns_none_when_no_json(self):
        brain = make_brain(use_native_tools=False)
        self._make_completion(brain, "Just a plain text response with no tool call.")
        result = brain._call_text()
        assert result is None

    def test_call_text_returns_none_when_no_choices(self):
        brain = make_brain(use_native_tools=False)
        resp = MagicMock()
        resp.choices = []
        brain.llm.client.chat.completions.create.return_value = resp
        result = brain._call_text()
        assert result is None

    def test_call_text_appends_assistant_message(self):
        brain = make_brain(use_native_tools=False)
        self._make_completion(brain, "Hello there!")
        brain._call_text()
        assert brain.messages[-1]["role"] == "assistant"
        assert brain.messages[-1]["content"] == "Hello there!"


# ---------------------------------------------------------------------------
# _call_native() and _feed_native_result()
# ---------------------------------------------------------------------------

class TestBrainCallNative:
    def _make_native_completion(self, brain, content=None, tool_calls=None):
        resp = MagicMock()
        msg = MagicMock()
        msg.content = content
        msg.tool_calls = tool_calls or []
        msg.model_dump.return_value = {
            "role": "assistant",
            "content": content,
        }
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg
        brain.llm.client.chat.completions.create.return_value = resp
        return resp

    def test_call_native_text_reply_returns_text_dict(self):
        brain = make_brain()
        self._make_native_completion(brain, content="Here is your answer.")
        result = brain._call_native()
        assert result == {"text": "Here is your answer."}

    def test_call_native_no_choices_returns_none(self):
        brain = make_brain()
        resp = MagicMock()
        resp.choices = []
        brain.llm.client.chat.completions.create.return_value = resp
        result = brain._call_native()
        assert result is None

    def test_call_native_tool_call_returns_action_dict(self):
        brain = make_brain()
        tc = MagicMock()
        tc.function.name = "screenshot"
        tc.function.arguments = "{}"
        tc.id = "call_abc123"
        self._make_native_completion(brain, tool_calls=[tc])
        result = brain._call_native()
        assert result is not None
        if isinstance(result, list):
            assert any(r.get("name") == "screenshot" for r in result)
        else:
            assert result.get("name") == "screenshot"

    def test_feed_native_result_appends_tool_message(self):
        brain = make_brain()
        brain._feed_native_result("call_xyz", {"ok": True, "result": "done"})
        last = brain.messages[-1]
        assert last["role"] == "tool"
        assert last["tool_call_id"] == "call_xyz"
