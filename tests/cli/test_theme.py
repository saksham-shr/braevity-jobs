from braevity.cli.theme import PRIMARY, SUCCESS, WARNING, ERROR, DIM, BG, FG


def test_theme_imports():
    assert PRIMARY == "#e85c2c"
    assert BG == "#1a1a1a"
    assert FG == "#f5f4f0"


def test_success_color():
    assert SUCCESS == "#5aa469"


def test_warning_color():
    assert WARNING == "#d19a2e"


def test_error_color():
    assert ERROR == "#d4605a"


def test_dim_color():
    assert DIM == "#85807a"
