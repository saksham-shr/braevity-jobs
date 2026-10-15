import pytest
from unittest.mock import patch
from braevity.cli.tui import BraevityApp, _dot_line, _tracked_count


def test_dot_line_format():
    result = _dot_line("watches", "3")
    assert "watches" in result
    assert "3" in result
    assert "·" in result


def test_tracked_count_no_db(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    assert _tracked_count() == 0


@pytest.mark.asyncio
async def test_app_mounts(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    app = BraevityApp()
    async with app.run_test() as pilot:
        assert app.query_one("#prompt-input") is not None
        assert app.query_one("#header-bar") is not None
        assert app.query_one("#content") is not None


@pytest.mark.asyncio
async def test_help_command(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    app = BraevityApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/help"
        await pilot.press("enter")
        await pilot.pause()
        content = app.query_one("#content")
        children = list(content.children)
        assert len(children) > 0


@pytest.mark.asyncio
async def test_list_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    app = BraevityApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/list"
        await pilot.press("enter")
        await pilot.pause()
        children = list(app.query_one("#content").children)
        assert len(children) > 0


@pytest.mark.asyncio
async def test_status_command(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    app = BraevityApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/status"
        await pilot.press("enter")
        await pilot.pause()
        children = list(app.query_one("#content").children)
        assert len(children) > 0


@pytest.mark.asyncio
async def test_unknown_command(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    app = BraevityApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/badcommand"
        await pilot.press("enter")
        await pilot.pause()
        children = list(app.query_one("#content").children)
        assert len(children) > 0


@pytest.mark.asyncio
async def test_exit_command(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    app = BraevityApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/exit"
        await pilot.press("enter")
        await pilot.pause()


@pytest.mark.asyncio
async def test_init_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    app = BraevityApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/init"
        await pilot.press("enter")
        await pilot.pause()
        assert app._mode == "init_excel"

        await pilot.press("enter")
        await pilot.pause()
        assert app._mode == "init_smtp_confirm"

        await pilot.press("enter")
        await pilot.pause()
        assert app._mode is None

        from braevity.config import load_config
        config = load_config()
        assert "excel_path" in config


@pytest.mark.asyncio
async def test_watch_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    from braevity.config import save_config
    (tmp_path / ".braevity").mkdir(parents=True, exist_ok=True)
    save_config({"excel_path": str(tmp_path), "watches": []})

    app = BraevityApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")

        input_widget.value = "/watch"
        await pilot.press("enter")
        await pilot.pause()
        assert app._mode == "watch_role"

        input_widget.value = "Backend Engineer"
        await pilot.press("enter")
        await pilot.pause()
        assert app._mode == "watch_experience"

        input_widget.value = "6"
        await pilot.press("enter")
        await pilot.pause()
        assert app._mode == "watch_location"

        input_widget.value = "Remote, Bengaluru"
        await pilot.press("enter")
        await pilot.pause()
        assert app._mode == "watch_interval"

        input_widget.value = "30"
        await pilot.press("enter")
        await pilot.pause()
        assert app._mode is None

        from braevity.config import load_config
        config = load_config()
        assert len(config["watches"]) == 1
        assert config["watches"][0]["role"] == "Backend Engineer"
        assert config["watches"][0]["experience"] == "senior"


def test_suggestions_imports():
    from braevity.cli.suggestions import ROLES, CITIES, COUNTRIES, EXPERIENCE_MAP
    assert len(ROLES) > 0
    assert "Remote" in CITIES
    assert "India" in COUNTRIES
    assert EXPERIENCE_MAP["6"] == "senior"
