from braevity.core.registry import BoardRegistry


def test_register_new_board(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    assert reg.register("greenhouse", "stripe", "Stripe", "seed") is True
    assert reg.board_count() == 1
    reg.close()


def test_register_duplicate_ignored(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "stripe", "Stripe", "seed")
    assert reg.register("greenhouse", "stripe", "Stripe", "seed") is False
    assert reg.board_count() == 1
    reg.close()


def test_get_active_boards(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "stripe", "Stripe", "seed")
    reg.register("lever", "figma", "Figma", "seed")
    boards = reg.get_active_boards()
    assert len(boards) == 2
    gh_boards = reg.get_active_boards("greenhouse")
    assert len(gh_boards) == 1
    assert gh_boards[0]["token"] == "stripe"
    reg.close()


def test_update_after_fetch(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "stripe", "Stripe", "seed")
    reg.update_after_fetch("greenhouse:stripe", 42)
    boards = reg.get_active_boards()
    assert boards[0]["job_count"] == 42
    assert boards[0]["last_fetched"] is not None
    reg.close()


def test_record_failure_deactivates_at_three(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "gone", "Gone Co", "seed")
    reg.record_failure("greenhouse:gone")
    reg.record_failure("greenhouse:gone")
    assert len(reg.get_active_boards()) == 1
    reg.record_failure("greenhouse:gone")
    assert len(reg.get_active_boards()) == 0
    reg.close()


def test_update_after_fetch_resets_fail_count(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "flaky", "Flaky", "seed")
    reg.record_failure("greenhouse:flaky")
    reg.record_failure("greenhouse:flaky")
    reg.update_after_fetch("greenhouse:flaky", 10)
    reg.record_failure("greenhouse:flaky")
    assert len(reg.get_active_boards()) == 1
    reg.close()
