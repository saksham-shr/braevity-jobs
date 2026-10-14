from click.testing import CliRunner
from braevity.cli.commands import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "braevity" in result.output.lower() or "Usage" in result.output


def test_init_creates_config(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    runner = CliRunner()
    result = runner.invoke(cli, ["init"], input="D:/Jobs\nY\nuser@gmail.com\nsmtp.gmail.com\n587\nuser@gmail.com\npassword123\n")
    assert result.exit_code == 0
    assert (tmp_path / ".braevity" / "config.yaml").exists()


def test_list_no_watches(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "No watches" in result.output


def test_watch_adds_config(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    runner = CliRunner()
    runner.invoke(cli, ["init"], input="D:/Jobs\nN\n")
    result = runner.invoke(cli, ["watch"], input="Backend Engineer\nmid\nIndia, US\nBangalore, Remote\n30\n")
    assert result.exit_code == 0
    assert "Watch added" in result.output


def test_remove_watch(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    runner = CliRunner()
    runner.invoke(cli, ["init"], input="D:/Jobs\nN\n")
    runner.invoke(cli, ["watch"], input="SDE\nany\nIndia\nBangalore\n30\n")
    result = runner.invoke(cli, ["remove", "1"])
    assert result.exit_code == 0
    assert "Removed" in result.output
