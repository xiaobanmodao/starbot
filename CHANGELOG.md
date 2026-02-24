# Changelog

User-facing feature updates and behavior changes.

Format:
- `Added`: new features
- `Changed`: behavior changes or refactors
- `Fixed`: bug fixes
- `Tests`: test coverage updates

## [Unreleased]

### Added
- `/skill info <name>` to inspect skill details (kind, source, path, tools, keywords)
- `/skill update <name>` for managed external skills (updates from recorded source)
- External skill keyword indexing and auto recommendations for better tool routing

### Changed
- `Brain` now injects a `[Skill Recommendations]` hint on the first user message
- `SkillManager` records `source` and `source_kind` metadata for installed skills
- `SkillManager.list_skills()` now includes source metadata fields

### Fixed
- `SkillManager.update()` no longer depends on system temp directories on Windows
- Uses project-local temp directories to avoid temp ACL/permission failures

### Tests
- Extended `tests/test_skill_manager_external.py` for:
- `get_skill_info()` and recommendation results
- `update()` behavior for managed `SKILL.md` skills
- `skillsmp.com` source passthrough regression

## [2026-02-24]

### Added
- External `SKILL.md` ecosystem support (discover + install)
- Install sources: `skillsmp.com`, GitHub repo/tree, local dir, local `SKILL.md`, local/remote `.zip`
- External `SKILL.md` skills are exposed as callable tools for the model
- Standalone config wizard module (`config_wizard.py`)
- CLI re-run setup entrypoints (`start.py setup/config/--setup/--setup-only`, `python config_wizard.py`)
- `/doctor` command for dependency checks and capability diagnostics

### Changed
- Config wizard supports per-step `Skip / Modify`
- `/config` masks sensitive fields (API keys, bot token)
- Startup warnings (`warning`) are no longer collapsed away too quickly
- Extracted `actions/web_helpers.py` from `actions/executor.py` (small refactor)

### Fixed
- Filtered numeric spam output (`1..100+`) in AI streaming responses
- Preserved valid AI text while filtering non-answer tool-call noise patterns

### Tests
- Added `tests/test_text_safety.py`
- Added `tests/test_web_helpers.py`
- Extended `tests/test_skill_manager_external.py`
