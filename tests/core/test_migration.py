from braevity.core.migration import seed_registry, migrate_catalog
from braevity.core.registry import BoardRegistry


def test_seed_registry(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    count = seed_registry(reg)
    assert count > 30
    boards = reg.get_active_boards()
    assert len(boards) > 30
    gh = reg.get_active_boards("greenhouse")
    assert any(b["token"] == "stripe" for b in gh)
    reg.close()


def test_seed_registry_idempotent(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    count1 = seed_registry(reg)
    count2 = seed_registry(reg)
    assert count2 == 0
    reg.close()


def test_migrate_catalog(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    count = migrate_catalog(reg)
    assert count > 0
    boards = reg.get_active_boards("greenhouse")
    assert any(b["token"] == "razorpay" for b in boards)
    assert any(b["company_name"] == "Razorpay" for b in boards)
    reg.close()
