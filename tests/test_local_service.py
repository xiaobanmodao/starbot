from __future__ import annotations

from types import SimpleNamespace

from comms.local_service import LocalClientService


class FakeController:
    def __init__(self):
        self.is_busy = False
        self._has_session = False
        self._events = []
        self.sent = []
        self.cancel_called = False
        self.reset_called = False

    def send_message(self, text: str) -> bool:
        self.sent.append(text)
        self._has_session = True
        self._events.append({"type": "user", "time": 1.0, "text": text})
        return True

    def drain_events(self, limit: int = 200):
        out = self._events[:limit]
        self._events = self._events[limit:]
        return out

    def has_session(self) -> bool:
        return self._has_session

    def usage_snapshot(self):
        return {"input": 12, "output": 34, "calls": 2}

    def cancel(self):
        self.cancel_called = True

    def reset_session(self):
        self.reset_called = True
        self._has_session = False
        return True


class FakeMemory:
    def __init__(self):
        self.deleted = []

    def list_by_category(self, category="", limit=20):
        return [{"id": 1, "category": category or "knowledge", "content": "abc", "importance": 5}]

    def search_multi(self, query, limit=8):
        return [{"id": 2, "category": "knowledge", "content": f"hit:{query}", "score": 1.2}]

    def delete_by_id(self, memory_id: int):
        self.deleted.append(memory_id)
        return True

    def stats(self):
        return {"knowledge": 3}


class FakeSkillManager:
    def __init__(self):
        self._skills = [{"name": "Demo", "version": "1.0", "kind": "skillmd", "managed": True, "tools": ["skillmd_demo"]}]
        self.reloaded = False

    def list_skills(self):
        return list(self._skills)

    def reload(self):
        self.reloaded = True

    def install(self, source):
        return True, f"installed {source}"

    def remove(self, name):
        return True, f"removed {name}"

    def get_skill_info(self, name):
        if name == "Demo":
            return {"name": "Demo", "kind": "skillmd", "tools": ["skillmd_demo"], "managed": True}
        return None

    def update(self, name):
        return True, f"updated {name}"


class FakeTaskMgr:
    def __init__(self):
        self._tasks = [SimpleNamespace(id=1, name="T1", status="running", result="", steps=2, created_at=0.0)]

    def list_all(self):
        return list(self._tasks)

    def summary(self):
        return "#1 running"


class FakeConfigModule:
    def __init__(self):
        self.writes = []
        self.state_updates = []

    def _write_env(self, key, value):
        self.writes.append((key, value))

    def _save_state(self, data):
        self.state_updates.append(dict(data))


def make_service():
    cfg = SimpleNamespace(
        LLM_API_BASE="https://api.openai.com/v1",
        LLM_API_KEY="sk-test-abcdef1234",
        LLM_MODEL="gpt-4o-mini",
        LLM2_API_BASE="",
        LLM2_API_KEY="",
        LLM2_MODEL="",
        DISCORD_BOT_TOKEN="discord-token-value",
        DISCORD_OWNER_ID="123",
        DISCORD_CHANNEL_ID=456,
        DISCORD_PROXY="",
    )
    return LocalClientService(
        controller=FakeController(),
        memory=FakeMemory(),
        skill_manager=FakeSkillManager(),
        task_mgr=FakeTaskMgr(),
        config_obj=cfg,
        config_module=FakeConfigModule(),
        screenshot_provider=lambda: (True, "ok", "abc123"),
    )


def test_local_service_chat_and_command_router():
    svc = make_service()
    r1 = svc.send_chat("hello")
    assert r1["ok"] is True
    r2 = svc.poll_chat_events()
    assert r2["ok"] is True
    assert r2["data"]["events"][0]["type"] == "user"

    r3 = svc.exec_command("/memory stats")
    assert r3["ok"] is True
    assert r3["data"]["stats"]["knowledge"] == 3

    r4 = svc.exec_command("/skill list")
    assert r4["ok"] is True
    assert r4["data"]["items"][0]["name"] == "Demo"


def test_local_service_config_set_and_bulk_update():
    svc = make_service()
    mod = svc._config_module

    r = svc.config_set("DISCORD_OWNER_ID", "999")
    assert r["ok"] is True
    assert svc.config.DISCORD_OWNER_ID == "999"
    assert ("DISCORD_OWNER_ID", "999") in mod.writes

    r2 = svc.config_set("LLM_MODEL", "claude-sonnet-x")
    assert r2["ok"] is True
    assert svc.config.LLM_MODEL == "claude-sonnet-x"
    assert {"LLM_MODEL": "claude-sonnet-x"} in mod.state_updates

    r3 = svc.config_update_many({"DISCORD_PROXY": "http://127.0.0.1:7890", "NOPE": "x"})
    assert r3["ok"] is True
    assert "DISCORD_PROXY" in r3["data"]["updated"]


def test_local_service_doctor_and_screenshot_shapes():
    svc = make_service()
    d = svc.doctor()
    assert d["ok"] is True
    assert "checks" in d["data"]
    assert "runtime" in d["data"]
    assert d["data"]["config"]["LLM_API_KEY"].startswith("sk-t")

    s = svc.screenshot()
    assert s["ok"] is True
    assert s["data"]["jpeg_base64"] == "abc123"


def test_local_service_command_config_get_and_rollback():
    svc = make_service()
    # monkeypatch rollback path via method override on instance for unit isolation
    svc.rollback = lambda n=1: {"ok": True, "message": "rolled", "data": {"messages": ["x"]}, "code": ""}

    r1 = svc.exec_command("/config LLM_MODEL")
    assert r1["ok"] is True
    assert "LLM_MODEL" in r1["data"]

    r2 = svc.exec_command("/rollback 2")
    assert r2["ok"] is True
    assert r2["message"] == "rolled"

