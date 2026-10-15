from unittest.mock import patch


@patch("braevity.cli.tui.load_config", return_value={
    "watches": [
        {"role": "SDE", "experience": "junior",
         "locations": {"countries": ["India"], "cities": ["Bangalore"]},
         "poll_interval": 30},
    ]
})
def test_tui_list_renders_table(mock_config):
    from braevity.cli.tui import tui_list
    tui_list()


@patch("braevity.cli.tui.load_config", return_value={"watches": []})
def test_tui_list_empty(mock_config):
    from braevity.cli.tui import tui_list
    tui_list()


@patch("braevity.cli.tui.load_config", return_value={"watches": []})
def test_tui_start_no_watches(mock_config):
    from braevity.cli.tui import tui_start
    tui_start()


@patch("braevity.cli.tui.load_config", return_value={})
def test_tui_status_no_db(mock_config):
    from braevity.cli.tui import tui_status
    tui_status()
