from comms.text_safety import (
    is_numeric_spam_text,
    should_preserve_stream_text_on_tool_switch,
)


def test_detects_line_by_line_numeric_spam():
    text = "\n".join(str(i) for i in range(1, 40))
    assert is_numeric_spam_text(text) is True


def test_detects_whitespace_separated_numeric_spam():
    text = " ".join(str(i) for i in range(1, 80))
    assert is_numeric_spam_text(text) is True


def test_does_not_flag_normal_plan_with_numbers():
    text = "1. Open browser\n2. Search docs\n3. Read the top result and summarize."
    assert is_numeric_spam_text(text) is False


def test_does_not_flag_normal_sentence_with_some_numbers():
    text = "Python 3.12 and Windows 11 are supported. Retry at most 3 times."
    assert is_numeric_spam_text(text) is False


def test_preserve_stream_text_for_normal_plan():
    text = "1. Inspect files\n2. Fix the issue\n3. Verify the result"
    assert should_preserve_stream_text_on_tool_switch(text) is True


def test_do_not_preserve_stream_text_for_numeric_spam():
    text = "\n".join(str(i) for i in range(1, 120))
    assert should_preserve_stream_text_on_tool_switch(text) is False


def test_empty_text_not_preserved():
    assert should_preserve_stream_text_on_tool_switch("") is False
