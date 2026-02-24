import re


def is_numeric_spam_text(text: str) -> bool:
    """Detect pathological numeric spam like 1..100 line-by-line or whitespace-separated."""
    if not text:
        return False
    s = text.strip()
    if len(s) < 16:
        return False

    # Case 1: most lines are pure integers and form a near-consecutive sequence.
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if len(lines) >= 8:
        digit_lines = [ln for ln in lines if ln.isdigit()]
        if len(digit_lines) / max(1, len(lines)) >= 0.8:
            nums = [int(x) for x in digit_lines[:80]]
            if len(nums) >= 8:
                consecutive = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
                if consecutive >= max(6, len(nums) - 3):
                    return True

    # Case 2: "1 2 3 ... 100" style output with almost no non-numeric content.
    ints = re.findall(r"\b\d+\b", s)
    if len(ints) >= 12:
        nums = [int(x) for x in ints[:120]]
        consecutive = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
        if consecutive >= max(10, len(nums) - 5):
            non_num = re.sub(r"[\d\s,.;:()\[\]\-]+", "", s)
            if len(non_num) <= 8:
                return True

    return False


def should_preserve_stream_text_on_tool_switch(text: str) -> bool:
    """Return True when streamed text should remain visible after model switches to tools."""
    if not text or not text.strip():
        return False
    return not is_numeric_spam_text(text)
