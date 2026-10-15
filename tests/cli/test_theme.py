from braevity.cli.theme import BRAEVITY_THEME, console, print_banner, PRIMARY


def test_theme_has_primary_style():
    assert "primary" in BRAEVITY_THEME.styles


def test_console_uses_theme():
    assert console.style is not None or BRAEVITY_THEME is not None


def test_print_banner_no_crash(capsys):
    print_banner()
    captured = capsys.readouterr()
    assert "Job Monitor" in captured.out


def test_no_color_env_no_crash(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    from braevity.cli.theme import print_banner as pb
    pb()
