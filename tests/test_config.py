import os
from pathlib import Path
from braevity.config import load_config, save_config, config_dir


def test_config_dir_uses_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    d = config_dir()
    assert d == tmp_path / ".braevity"


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    data = {
        "excel_path": "D:/Jobs",
        "notification": {
            "email": "u@g.com",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "u@g.com",
            "smtp_password": "p@ss:word#1",
        },
        "watches": [],
    }
    save_config(data)
    loaded = load_config()
    assert loaded == data
    assert loaded["notification"]["smtp_password"] == "p@ss:word#1"


def test_load_config_returns_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    result = load_config()
    assert result == {}
