from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


DEFAULT_CHANGELOG = Path("CHANGELOG.md")
DEFAULT_SECTIONS = ["Added", "Changed", "Fixed", "Tests"]
UNRELEASED_RE = re.compile(r"(?ms)^## \[Unreleased\]\s*\n(?P<body>.*?)(?=^## \[|\Z)")


class ChangelogError(ValueError):
    pass


@dataclass
class ArchiveResult:
    text: str
    archived_heading: str
    content_lines: int


def _normalize_version(version: str) -> str:
    v = (version or "").strip()
    if not v:
        raise ChangelogError("version is required")
    if any(ch in v for ch in "[]\r\n"):
        raise ChangelogError("version contains invalid characters")
    return v


def _extract_unreleased_sections(body: str) -> list[str]:
    sections: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line.strip())
        if m:
            sections.append(m.group(1))
    deduped: list[str] = []
    seen: set[str] = set()
    for sec in sections:
        key = sec.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sec)
    return deduped or DEFAULT_SECTIONS[:]


def _unreleased_has_content(body: str) -> bool:
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("### "):
            continue
        return True
    return False


def _reset_unreleased_template(sections: list[str]) -> str:
    parts = ["## [Unreleased]", ""]
    for sec in sections:
        parts.append(f"### {sec}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def archive_changelog_text(
    text: str,
    *,
    version: str,
    release_date: str | None = None,
    allow_empty: bool = False,
) -> ArchiveResult:
    version = _normalize_version(version)
    if release_date is None:
        release_date = date.today().isoformat()

    if re.search(rf"(?m)^## \[{re.escape(version)}\](?:\s*-\s*\d{{4}}-\d{{2}}-\d{{2}})?\s*$", text):
        raise ChangelogError(f"version already exists in changelog: {version}")

    m = UNRELEASED_RE.search(text)
    if not m:
        raise ChangelogError("missing '## [Unreleased]' section")

    body = m.group("body")
    sections = _extract_unreleased_sections(body)
    if not allow_empty and not _unreleased_has_content(body):
        raise ChangelogError("Unreleased section is empty; nothing to archive")

    archived_body = body.strip("\n")
    heading = f"## [{version}] - {release_date}"

    prefix = text[: m.start()]
    suffix = text[m.end() :]
    if suffix.startswith("\n"):
        suffix = suffix[1:]

    parts = [prefix.rstrip("\n")]
    if parts[0]:
        parts.append("")
    parts.append(_reset_unreleased_template(sections).rstrip("\n"))
    parts.append("")
    parts.append(heading)
    parts.append("")
    if archived_body:
        parts.append(archived_body)
        parts.append("")
    if suffix:
        parts.append(suffix.rstrip("\n"))
        parts.append("")

    new_text = "\n".join(parts)
    if not new_text.endswith("\n"):
        new_text += "\n"

    content_lines = sum(
        1
        for line in archived_body.splitlines()
        if line.strip() and not line.strip().startswith("### ")
    )
    return ArchiveResult(text=new_text, archived_heading=heading, content_lines=content_lines)


def archive_changelog_file(
    changelog_path: Path,
    *,
    version: str,
    release_date: str | None = None,
    allow_empty: bool = False,
) -> ArchiveResult:
    text = changelog_path.read_text(encoding="utf-8")
    result = archive_changelog_text(
        text,
        version=version,
        release_date=release_date,
        allow_empty=allow_empty,
    )
    changelog_path.write_text(result.text, encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Archive CHANGELOG.md 'Unreleased' into a versioned section."
    )
    p.add_argument("version", help="Release version, e.g. 0.2.0")
    p.add_argument("--date", dest="release_date", help="Release date (YYYY-MM-DD). Defaults to today.")
    p.add_argument("--file", dest="file", default=str(DEFAULT_CHANGELOG), help="Changelog path (default: CHANGELOG.md)")
    p.add_argument("--dry-run", action="store_true", help="Validate and print summary without writing file")
    p.add_argument("--allow-empty", action="store_true", help="Allow archiving even if Unreleased has no entries")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = Path(args.file)
    if not path.exists():
        parser.error(f"changelog not found: {path}")

    try:
        if args.dry_run:
            text = path.read_text(encoding="utf-8")
            result = archive_changelog_text(
                text,
                version=args.version,
                release_date=args.release_date,
                allow_empty=args.allow_empty,
            )
        else:
            result = archive_changelog_file(
                path,
                version=args.version,
                release_date=args.release_date,
                allow_empty=args.allow_empty,
            )
    except ChangelogError as e:
        print(f"ERROR: {e}")
        return 2

    mode = "dry-run" if args.dry_run else "updated"
    print(f"{mode}: {path}")
    print(f"archived: {result.archived_heading}")
    print(f"entries: {result.content_lines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

