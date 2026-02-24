import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from core.skill_manager import SkillManager


def _write_skillmd(root: Path, name: str = "Demo Skill", desc: str = "Helps with demo tasks.") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {name}\n"
            f"description: {desc}\n"
            "version: 1.0.0\n"
            "author: test\n"
            "---\n\n"
            "# Demo Skill\n\n"
            "Follow `scripts/run.py` and use `templates/output.txt`.\n"
        ),
        encoding="utf-8",
    )
    (root / "scripts").mkdir(exist_ok=True)
    (root / "scripts" / "run.py").write_text("print('hello')\n", encoding="utf-8")
    (root / "templates").mkdir(exist_ok=True)
    (root / "templates" / "output.txt").write_text("template", encoding="utf-8")
    return root


@pytest.fixture
def local_tmp_dir():
    base = Path.cwd() / "test_tmp_work"
    base.mkdir(exist_ok=True)
    tmp = base / f"skillmgr_{uuid.uuid4().hex[:8]}"
    tmp.mkdir(parents=True, exist_ok=False)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_discovers_external_skillmd_and_exposes_tool(local_tmp_dir):
    py_dir = local_tmp_dir / "skills"
    ext_dir = local_tmp_dir / "skills_ext"
    discovery_root = local_tmp_dir / "codex_skills"
    skill_dir = _write_skillmd(discovery_root / "demo_skill")

    mgr = SkillManager(skills_dir=py_dir, ext_skills_dir=ext_dir, discovery_roots=[discovery_root])

    skills = mgr.list_skills()
    assert len(skills) == 1
    skill = skills[0]
    assert skill["kind"] == "skillmd"
    assert skill["managed"] is False
    assert Path(skill["path"]) == skill_dir

    schema = mgr.tools_schema
    assert len(schema) == 1
    tool_name = schema[0]["function"]["name"]
    assert tool_name.startswith("skillmd_")

    result = mgr.execute(tool_name, {"task": "Use the skill"})
    assert result and result["ok"] is True
    text = result["result"]
    assert "SKILL.md" in text
    assert "scripts/run.py" in text
    assert "templates/output.txt" in text


def test_install_local_skillmd_dir_copies_into_managed_store_and_remove(local_tmp_dir):
    py_dir = local_tmp_dir / "skills"
    ext_dir = local_tmp_dir / "skills_ext"
    source_skill = _write_skillmd(local_tmp_dir / "downloaded" / "my_skill", name="My External Skill")

    mgr = SkillManager(skills_dir=py_dir, ext_skills_dir=ext_dir, discovery_roots=[])
    ok, msg = mgr.install(str(source_skill))
    assert ok is True, msg

    skills = mgr.list_skills()
    assert len(skills) == 1
    skill = skills[0]
    assert skill["kind"] == "skillmd"
    assert skill["managed"] is True
    managed_path = Path(skill["path"])
    assert managed_path.exists()
    assert ext_dir in managed_path.parents

    ok_rm, msg_rm = mgr.remove(skill["name"])
    assert ok_rm is True, msg_rm
    assert not managed_path.exists()
    assert mgr.list_skills() == []


def test_remove_discovered_external_skill_is_blocked(local_tmp_dir):
    py_dir = local_tmp_dir / "skills"
    ext_dir = local_tmp_dir / "skills_ext"
    discovery_root = local_tmp_dir / "claude_skills"
    _write_skillmd(discovery_root / "demo")

    mgr = SkillManager(skills_dir=py_dir, ext_skills_dir=ext_dir, discovery_roots=[discovery_root])
    skill = mgr.list_skills()[0]

    ok, msg = mgr.remove(skill["name"])
    assert ok is False
    assert "外部发现项" in msg


def test_python_skill_loading_still_works(local_tmp_dir):
    py_dir = local_tmp_dir / "skills"
    ext_dir = local_tmp_dir / "skills_ext"
    py_dir.mkdir(parents=True, exist_ok=True)
    (py_dir / "mini.py").write_text(
        (
            "META={'name':'mini_py','version':'1.0.0','description':'mini','author':'t'}\n"
            "TOOLS=[{'type':'function','function':{'name':'mini_tool','description':'x','parameters':{'type':'object','properties':{},'required':[]}}}]\n"
            "def execute(name,args):\n"
            "    return {'ok': True, 'result': 'done'}\n"
        ),
        encoding="utf-8",
    )

    mgr = SkillManager(skills_dir=py_dir, ext_skills_dir=ext_dir, discovery_roots=[])
    skills = mgr.list_skills()
    assert len(skills) == 1
    assert skills[0]["kind"] == "python"
    assert skills[0]["tools"] == ["mini_tool"]
    assert mgr.execute("mini_tool", {})["ok"] is True


def test_skillsmp_page_install_resolves_github_link(monkeypatch, local_tmp_dir):
    py_dir = local_tmp_dir / "skills"
    ext_dir = local_tmp_dir / "skills_ext"
    mgr = SkillManager(skills_dir=py_dir, ext_skills_dir=ext_dir, discovery_roots=[])

    html = """
    <html><body>
      "repository": <a href="https://github.com/example/repo/tree/main/skills/demo">repo</a>
    </body></html>
    """

    def fake_get(url, timeout=0):
        return SimpleNamespace(text=html, raise_for_status=lambda: None)

    seen = {}

    def fake_install_from_github(url):
        seen["url"] = url
        return True, "ok"

    monkeypatch.setattr("core.skill_manager.requests.get", fake_get)
    monkeypatch.setattr(mgr, "_install_skillmd_from_github", fake_install_from_github)

    ok, msg = mgr.install("https://skillsmp.com/skills/some-skill")
    assert ok is True
    assert "skillsmp" in msg
    assert seen["url"] == "https://github.com/example/repo/tree/main/skills/demo"
