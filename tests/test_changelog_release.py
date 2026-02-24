from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from tools.changelog_release import ChangelogError, archive_changelog_file, archive_changelog_text


SAMPLE = """# Changelog

Intro text.

## [Unreleased]

### Added
- New command

### Changed

### Fixed
- Bug fix

### Tests

## [2026-02-24]

### Added
- Old stuff
"""


@pytest.fixture
def local_tmp_dir():
    base = Path.cwd() / "test_tmp_work"
    base.mkdir(exist_ok=True)
    tmp = base / f"changelog_{uuid.uuid4().hex[:8]}"
    tmp.mkdir(parents=True, exist_ok=False)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_archive_changelog_text_moves_unreleased_into_version():
    result = archive_changelog_text(SAMPLE, version="0.1.1", release_date="2026-02-24")

    assert "## [0.1.1] - 2026-02-24" in result.text
    assert "## [Unreleased]" in result.text
    assert "## [Unreleased]\n\n### Added\n\n### Changed\n\n### Fixed\n\n### Tests\n" in result.text
    assert result.text.index("## [0.1.1] - 2026-02-24") < result.text.index("## [2026-02-24]")
    assert result.content_lines == 2


def test_archive_changelog_text_rejects_empty_unreleased():
    text = """# Changelog

## [Unreleased]

### Added

### Changed

### Fixed

### Tests
"""
    with pytest.raises(ChangelogError, match="empty"):
        archive_changelog_text(text, version="0.1.2", release_date="2026-02-24")


def test_archive_changelog_text_rejects_duplicate_version():
    text = SAMPLE + "\n## [0.1.1] - 2026-02-24\n\n### Added\n- dup\n"
    with pytest.raises(ChangelogError, match="already exists"):
        archive_changelog_text(text, version="0.1.1", release_date="2026-02-24")


def test_archive_changelog_file_writes_output(local_tmp_dir: Path):
    p = local_tmp_dir / "CHANGELOG.md"
    p.write_text(SAMPLE, encoding="utf-8")

    result = archive_changelog_file(p, version="0.1.3", release_date="2026-02-25")

    saved = p.read_text(encoding="utf-8")
    assert result.text == saved
    assert "## [0.1.3] - 2026-02-25" in saved
