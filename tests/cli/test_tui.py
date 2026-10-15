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


def test_show_help_no_crash():
    from braevity.cli.tui import show_help
    show_help()


def test_commands_dict_has_all_entries():
    from braevity.cli.tui import COMMANDS, REPL_ACTIONS
    for cmd in REPL_ACTIONS:
        assert cmd in COMMANDS, f"{cmd} in REPL_ACTIONS but not in COMMANDS"


@patch("braevity.cli.tui.pt_prompt", side_effect=["help", "exit"])
@patch("braevity.cli.tui.load_config", return_value={"watches": []})
def test_main_repl_help_then_exit(mock_config, mock_prompt):
    from braevity.cli.tui import main_repl
    main_repl()


@patch("braevity.cli.tui.pt_prompt", return_value="badcommand")
@patch("braevity.cli.tui.load_config", return_value={"watches": []})
def test_main_repl_unknown_command(mock_config, mock_prompt):
    call_count = [0]
    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return "badcommand"
        return "exit"
    mock_prompt.side_effect = side_effect
    from braevity.cli.tui import main_repl
    main_repl()


@patch("braevity.cli.tui.pt_prompt", side_effect=EOFError)
@patch("braevity.cli.tui.load_config", return_value={"watches": []})
def test_main_repl_ctrl_d_exits(mock_config, mock_prompt):
    from braevity.cli.tui import main_repl
    main_repl()
