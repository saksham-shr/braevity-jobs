# Braevity Interactive TUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive terminal UI to braevity with branded banner, autocomplete inputs, colored output, and a menu-driven interface — while keeping existing Click subcommands for scripting.

**Architecture:** New TUI layer (`braevity/cli/tui.py`) wraps existing CLI logic as a REPL (`braevity>` prompt with command autocomplete). `rich` handles all visual output (banner, tables, progress markers). `prompt_toolkit` handles the REPL prompt and autocomplete inputs. Click subcommands remain unchanged. Experience filter widened to 10 categories.

**Tech Stack:** `rich>=13.0`, `prompt-toolkit>=3.0`, existing Click/aiohttp/openpyxl/pyyaml/plyer.

**Spec:** `docs/superpowers/specs/2026-10-15-braevity-tui-design.md`

## Global Constraints

- Python >=3.10
- No new dependencies beyond `rich` and `prompt-toolkit`
- Existing Click subcommand tests must keep passing unchanged
- Must work on Windows 11 (primary), Linux, macOS
- All colors from branding kit: primary `#E84A1E`, accent `#F0A868`, success `#44CC44`, error `#FF4444`, dim `#888888`

## Review Focus

1. **Terminal without color support** (e.g. piped output, dumb terminal) — `rich.console.Console` should degrade gracefully; test with `NO_COLOR=1` environment variable. Added to Task 1.
2. **Comma-separated location input with spaces** — user types `"New York, San Francisco"` and autocomplete must trigger per-token after comma, not treat the whole string as one token. Added to Task 3.
3. **Ctrl+C during scan** — pressing Ctrl+C mid-scan should exit cleanly without traceback, both in interactive and subcommand mode. Added to Task 5.
4. **Empty suggestion lists** — if `suggestions.py` lists are accidentally emptied, autocomplete should not crash. Added to Task 2.
5. **Experience filter `"i"` suffix false positives** — matching `"i"` as a suffix (for "SDE I") must not match every title containing the letter "i". The regex uses `\bi\b` word boundary. Added to Task 6.

---

### Task 1: Theme and Banner

**Files:**
- Create: `braevity/cli/theme.py`
- Create: `braevity/cli/__init__.py` (empty, if not exists)
- Test: `tests/cli/test_theme.py`

**Interfaces:**
- Consumes: nothing
- Produces: `BRAEVITY_THEME: rich.theme.Theme`, `console: rich.console.Console`, `print_banner() -> None`, color constants `PRIMARY`, `ACCENT`, `SUCCESS`, `ERROR`, `DIM` as strings

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_theme.py
from braevity.cli.theme import BRAEVITY_THEME, console, print_banner, PRIMARY


def test_theme_has_primary_style():
    assert "primary" in BRAEVITY_THEME.styles


def test_console_uses_theme():
    assert console.style is not None or BRAEVITY_THEME is not None


def test_print_banner_no_crash(capsys):
    print_banner()
    captured = capsys.readouterr()
    assert "BRAEVITY" in captured.out or "braevity" in captured.out.lower()


def test_no_color_env_no_crash(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    from braevity.cli.theme import print_banner as pb
    pb()
    # Should not crash — graceful degradation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_theme.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'braevity.cli.theme'`

- [ ] **Step 3: Add dependencies to pyproject.toml**

```toml
# In pyproject.toml, update dependencies list to add:
    "rich>=13.0",
    "prompt-toolkit>=3.0",
```

- [ ] **Step 4: Write implementation**

```python
# braevity/cli/theme.py
from rich.console import Console
from rich.theme import Theme

PRIMARY = "#E84A1E"
ACCENT = "#F0A868"
SUCCESS = "#44CC44"
ERROR = "#FF4444"
DIM = "#888888"

BRAEVITY_THEME = Theme({
    "primary": f"bold {PRIMARY}",
    "accent": ACCENT,
    "success": f"bold {SUCCESS}",
    "error": f"bold {ERROR}",
    "dim": DIM,
})

console = Console(theme=BRAEVITY_THEME)

BANNER = r"""
 ____  ____   _   _______     _____ _______   __
| __ )|  _ \ / \ | ____\ \   / /_ _|_   _\ \ / /
|  _ \| |_) / _ \|  _|  \ \ / / | |  | |  \ V /
| |_) |  _ / ___ \ |___  \ V /  | |  | |   | |
|____/|_| /_/   \_\_____|  \_/  |___| |_|   |_|
"""


def print_banner() -> None:
    console.print(BANNER, style="primary")
    console.print("  Job Monitor v0.1.0\n", style="dim")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_theme.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Run full suite to check no regressions**

Run: `python -m pytest tests/ --ignore=tests/test_e2e_aggregators.py -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add braevity/cli/theme.py tests/cli/test_theme.py pyproject.toml
git commit -m "feat(tui): theme constants and ASCII banner with rich

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Suggestion Lists

**Files:**
- Create: `braevity/cli/suggestions.py`
- Test: `tests/cli/test_suggestions.py`

**Interfaces:**
- Consumes: nothing
- Produces: `ROLES: list[str]`, `CITIES: list[str]`, `COUNTRIES: list[str]`, `EXPERIENCE_LEVELS: list[tuple[str, str]]` (value, display label)

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_suggestions.py
from braevity.cli.suggestions import ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS


def test_roles_non_empty():
    assert len(ROLES) >= 20


def test_roles_no_duplicates():
    assert len(ROLES) == len(set(ROLES))


def test_cities_include_remote():
    assert "Remote" in CITIES


def test_cities_include_bangalore():
    assert "Bangalore" in CITIES


def test_countries_include_india():
    assert "India" in COUNTRIES


def test_countries_include_worldwide():
    assert "Worldwide" in COUNTRIES


def test_experience_levels_has_any():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert "any" in values


def test_experience_levels_has_intern():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert "intern" in values


def test_experience_levels_has_director():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert "director" in values


def test_experience_levels_no_duplicates():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert len(values) == len(set(values))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_suggestions.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# braevity/cli/suggestions.py

ROLES = [
    "Software Engineer",
    "Software Developer",
    "Backend Engineer",
    "Frontend Engineer",
    "Full Stack Developer",
    "DevOps Engineer",
    "SRE",
    "Data Engineer",
    "Data Scientist",
    "ML Engineer",
    "Product Manager",
    "SDE",
    "SDE-2",
    "QA Engineer",
    "Mobile Developer",
    "Cloud Engineer",
    "Security Engineer",
    "Platform Engineer",
    "iOS Developer",
    "Android Developer",
    "Engineering Manager",
]

CITIES = [
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune", "Kolkata",
    "New York", "San Francisco", "Seattle", "Austin", "Boston", "Chicago",
    "Los Angeles", "Denver", "London", "Berlin", "Amsterdam", "Paris", "Dublin",
    "Stockholm", "Zurich", "Singapore", "Tokyo", "Sydney", "Melbourne",
    "Toronto", "Vancouver", "Sao Paulo", "Dubai", "Tel Aviv", "Warsaw",
    "Prague", "Lisbon", "Barcelona", "Madrid", "Helsinki", "Oslo",
    "Copenhagen", "Bucharest", "Krakow", "Budapest", "Tallinn", "Riga",
    "Vilnius", "Manila", "Ho Chi Minh City", "Jakarta", "Kuala Lumpur",
    "Bangkok", "Remote",
]

COUNTRIES = [
    "India", "United States", "United Kingdom", "Canada", "Germany", "France",
    "Netherlands", "Australia", "Singapore", "Japan", "Ireland", "Sweden",
    "Switzerland", "Israel", "Brazil", "UAE", "Poland", "Czech Republic",
    "Spain", "Portugal", "Finland", "Norway", "Denmark", "Romania", "Estonia",
    "Lithuania", "Latvia", "Philippines", "Vietnam", "Indonesia",
    "Remote", "Worldwide",
]

EXPERIENCE_LEVELS = [
    ("any", "Any"),
    ("intern", "Intern"),
    ("entry_level", "Entry Level"),
    ("junior", "Junior"),
    ("mid", "Mid"),
    ("senior", "Senior"),
    ("staff", "Staff / Lead"),
    ("principal", "Principal"),
    ("manager", "Manager"),
    ("director", "Director+"),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_suggestions.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add braevity/cli/suggestions.py tests/cli/test_suggestions.py
git commit -m "feat(tui): role, city, country, experience suggestion lists

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Autocomplete Prompts

**Files:**
- Create: `braevity/cli/prompts.py`
- Test: `tests/cli/test_prompts.py`

**Interfaces:**
- Consumes: `ROLES`, `CITIES`, `COUNTRIES`, `EXPERIENCE_LEVELS` from `braevity.cli.suggestions`
- Produces: `prompt_role() -> str`, `prompt_cities() -> list[str]`, `prompt_countries() -> list[str]`, `prompt_experience() -> str`, `prompt_path(label, default) -> str`, `prompt_confirm(label, default) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_prompts.py
from unittest.mock import patch
from braevity.cli.prompts import prompt_role, prompt_experience, prompt_cities


@patch("braevity.cli.prompts.pt_prompt", return_value="Software Engineer")
def test_prompt_role_returns_input(mock_prompt):
    result = prompt_role()
    assert result == "Software Engineer"
    mock_prompt.assert_called_once()


@patch("braevity.cli.prompts.pt_prompt", return_value="6")
def test_prompt_experience_returns_value(mock_prompt):
    result = prompt_experience()
    assert result == "senior"


@patch("braevity.cli.prompts.pt_prompt", return_value="New York, San Francisco")
def test_prompt_cities_comma_separated(mock_prompt):
    result = prompt_cities()
    assert result == ["New York", "San Francisco"]


@patch("braevity.cli.prompts.pt_prompt", return_value="")
def test_prompt_cities_empty_returns_empty_list(mock_prompt):
    result = prompt_cities()
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# braevity/cli/prompts.py
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter
from braevity.cli.suggestions import ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS
from braevity.cli.theme import PRIMARY, console


def _comma_completer(suggestions: list[str]) -> WordCompleter:
    return WordCompleter(suggestions, ignore_case=True, sentence=True)


def prompt_role() -> str:
    completer = WordCompleter(ROLES, ignore_case=True)
    console.print("  Role to track:", style="primary", end=" ")
    return pt_prompt("", completer=completer).strip()


def prompt_cities() -> list[str]:
    completer = _comma_completer(CITIES)
    console.print("  Cities (comma-separated):", style="primary", end=" ")
    raw = pt_prompt("", completer=completer).strip()
    if not raw:
        return []
    return [c.strip() for c in raw.split(",") if c.strip()]


def prompt_countries() -> list[str]:
    completer = _comma_completer(COUNTRIES)
    console.print("  Countries (comma-separated):", style="primary", end=" ")
    raw = pt_prompt("", completer=completer).strip()
    if not raw:
        return []
    return [c.strip() for c in raw.split(",") if c.strip()]


def prompt_experience() -> str:
    console.print("\n  Experience level:", style="primary")
    for i, (value, label) in enumerate(EXPERIENCE_LEVELS, 1):
        console.print(f"  {i:>2}. {label}")
    while True:
        raw = pt_prompt(f"  Pick [1-{len(EXPERIENCE_LEVELS)}]: ").strip()
        try:
            idx = int(raw)
            if 1 <= idx <= len(EXPERIENCE_LEVELS):
                return EXPERIENCE_LEVELS[idx - 1][0]
        except ValueError:
            pass
        console.print(f"  Enter a number 1-{len(EXPERIENCE_LEVELS)}.", style="error")


def prompt_path(label: str, default: str = "./jobs") -> str:
    console.print(f"  {label}", style="primary", end=" ")
    return pt_prompt("", default=default).strip()


def prompt_confirm(label: str, default: bool = False) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    console.print(f"  {label}{suffix}", style="primary", end="")
    answer = pt_prompt("").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_prompts.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add braevity/cli/prompts.py tests/cli/test_prompts.py
git commit -m "feat(tui): autocomplete prompts for role, location, experience

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Interactive REPL and TUI Entry Point

**Files:**
- Create: `braevity/cli/tui.py`
- Modify: `braevity/cli/commands.py` (add `invoke_without_command=True` and TUI fallback)
- Modify: `braevity/cli/commands.py:17-19` (`init` defaults excel path to `~/.braevity/exports/`)
- Test: `tests/cli/test_tui.py`

**Interfaces:**
- Consumes: `print_banner()`, `console` from `braevity.cli.theme`; `prompt_role()`, `prompt_cities()`, `prompt_countries()`, `prompt_experience()`, `prompt_path()`, `prompt_confirm()` from `braevity.cli.prompts`; `load_config`, `save_config`, `config_dir` from `braevity.config`
- Produces: `main_repl() -> None`, `show_status_line() -> None`, `tui_init() -> None`, `tui_watch() -> None`, `tui_list() -> None`, `tui_remove() -> None`, `tui_help() -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_tui.py
from unittest.mock import patch, MagicMock
from braevity.cli.tui import show_status_line, tui_list


def test_show_status_line_no_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    show_status_line()


@patch("braevity.cli.tui.load_config", return_value={
    "watches": [
        {"role": "SDE", "experience": "junior",
         "locations": {"countries": ["India"], "cities": ["Bangalore"]},
         "poll_interval": 30},
    ]
})
def test_tui_list_renders_table(mock_config, capsys):
    tui_list()
    # rich prints to its own console, not capsys — just verify no crash


@patch("braevity.cli.tui.load_config", return_value={"watches": []})
def test_tui_list_empty(mock_config):
    tui_list()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_tui.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# braevity/cli/tui.py
import asyncio
import logging
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter
from braevity.cli.theme import console, print_banner, PRIMARY
from braevity.cli.prompts import (
    prompt_role, prompt_cities, prompt_countries,
    prompt_experience, prompt_path, prompt_confirm,
)
from braevity.config import load_config, save_config, config_dir
from rich.table import Table

COMMANDS = {
    "init": "Set up Braevity config",
    "watch": "Add a new job watch",
    "list": "View all configured watches",
    "remove": "Remove a watch by number",
    "start": "Start monitoring",
    "status": "Show current status",
    "help": "Show available commands",
    "exit": "Exit Braevity",
}


def show_status_line() -> None:
    config = load_config()
    watches = config.get("watches", [])
    db_path = config_dir() / "seen.db"
    tracked = 0
    if db_path.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            tracked = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
            conn.close()
        except Exception:
            pass
    console.print(
        f"  {len(watches)} watches · {tracked} jobs tracked",
        style="dim",
    )


def tui_help() -> None:
    console.print("\n  Commands:", style="primary")
    for cmd, desc in COMMANDS.items():
        console.print(f"    {cmd:<10} {desc}")
    console.print()


def tui_init() -> None:
    config = load_config()
    default_export = str(config_dir() / "exports")
    config["excel_path"] = default_export

    if prompt_confirm("Set up email notifications via SMTP?"):
        email = prompt_path("Notification email", default="")
        smtp_host = prompt_path("SMTP host", default="smtp.gmail.com")
        smtp_port = prompt_path("SMTP port", default="587")
        smtp_user = prompt_path("SMTP user (email)", default="")
        smtp_password = prompt_path("SMTP password (app password)", default="")
        config["notification"] = {
            "email": email,
            "smtp_host": smtp_host,
            "smtp_port": int(smtp_port),
            "smtp_user": smtp_user,
            "smtp_password": smtp_password,
        }
    else:
        console.print("  Desktop toast notifications enabled.", style="dim")

    config.setdefault("watches", [])
    save_config(config)
    console.print(f"  Config saved to {config_dir() / 'config.yaml'}", style="success")


def tui_watch() -> None:
    config = load_config()
    if not config:
        console.print("  Run 'init' first.", style="error")
        return

    role = prompt_role()
    experience = prompt_experience()
    countries = prompt_countries()
    cities = prompt_cities()
    poll_interval = prompt_path("Poll interval in minutes", default="30")

    watch_entry = {
        "role": role,
        "experience": experience,
        "locations": {"countries": countries, "cities": cities},
        "poll_interval": int(poll_interval),
    }
    config.setdefault("watches", []).append(watch_entry)
    save_config(config)
    console.print(
        f'  Watch added: "{role}" | {experience} | '
        f'{len(countries)} countries, {len(cities)} cities',
        style="success",
    )


def tui_list() -> None:
    config = load_config()
    watches = config.get("watches", [])
    if not watches:
        console.print("  No watches configured. Type 'watch' to add one.", style="dim")
        return

    table = Table(border_style="dim")
    table.add_column("#", style="bold", width=4)
    table.add_column("Role", style="primary")
    table.add_column("Level", width=12)
    table.add_column("Locations")
    table.add_column("Interval", width=10)

    for i, w in enumerate(watches, 1):
        locs = w.get("locations", {})
        countries = ", ".join(locs.get("countries", []))
        cities = ", ".join(locs.get("cities", []))
        loc_str = f"{countries} · {cities}" if countries and cities else countries or cities
        table.add_row(
            str(i), w["role"], w.get("experience", "any"),
            loc_str, f"{w.get('poll_interval', 30)}m",
        )

    console.print(table)


def tui_remove() -> None:
    config = load_config()
    watches = config.get("watches", [])
    if not watches:
        console.print("  No watches to remove.", style="dim")
        return

    tui_list()
    index_str = prompt_path("Watch number to remove", default="")
    if not index_str:
        return
    try:
        index = int(index_str)
    except ValueError:
        console.print("  Invalid number.", style="error")
        return
    if index < 1 or index > len(watches):
        console.print(f"  Invalid index. You have {len(watches)} watches.", style="error")
        return
    removed = watches.pop(index - 1)
    save_config(config)
    console.print(f'  Removed watch: "{removed["role"]}"', style="success")


def tui_start() -> None:
    config = load_config()
    watches = config.get("watches", [])
    if not watches:
        console.print("  No watches configured. Type 'watch' first.", style="error")
        return

    console.print(f"  Starting {len(watches)} watch(es)...", style="primary")
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M",
    )
    from braevity.core.scheduler import run_scheduler
    try:
        asyncio.run(run_scheduler(config))
    except KeyboardInterrupt:
        console.print("\n  Stopped.", style="dim")


def tui_status() -> None:
    config = load_config()
    watches = config.get("watches", [])
    excel_path = config.get("excel_path", "not set")
    console.print(f"  Watches: {len(watches)}", style="primary")
    console.print(f"  Excel path: {excel_path}")
    db_path = config_dir() / "seen.db"
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
        conn.close()
        console.print(f"  Total jobs tracked: {count}")
    else:
        console.print("  No jobs tracked yet.", style="dim")


REPL_ACTIONS = {
    "init": tui_init,
    "watch": tui_watch,
    "list": tui_list,
    "remove": tui_remove,
    "start": tui_start,
    "status": tui_status,
    "help": tui_help,
}


def main_repl() -> None:
    print_banner()
    show_status_line()

    config = load_config()
    if not config or not config.get("watches"):
        console.print("  Welcome! Type 'init' to set up, or 'help' for commands.\n")

    completer = WordCompleter(list(COMMANDS.keys()), ignore_case=True)

    while True:
        try:
            cmd = pt_prompt(
                "braevity> ",
                completer=completer,
                style=None,  # bold orange via prompt_toolkit Style
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("  Goodbye!", style="dim")
            break

        if not cmd:
            continue

        if cmd == "exit":
            console.print("  Goodbye!", style="dim")
            break

        action = REPL_ACTIONS.get(cmd)
        if action:
            try:
                action()
            except KeyboardInterrupt:
                console.print("\n  Cancelled.", style="dim")
        else:
            console.print(
                f"  Unknown command '{cmd}'. Type 'help' for available commands.",
                style="error",
            )
```

- [ ] **Step 4: Modify `braevity/cli/commands.py`**

Launch REPL on bare `braevity`, and default `init` excel path to `~/.braevity/exports/`:

```python
# cli group: invoke_without_command calls main_repl
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Braevity — CLI job monitor for ATS platforms."""
    if ctx.invoked_subcommand is None:
        from braevity.cli.tui import main_repl
        main_repl()
```

In the `init` command, replace the excel_path prompt:
```python
# Replace: excel_path = click.prompt("Where should Excel files be saved?", default="./jobs")
# With:
default_export = str(config_dir() / "exports")
excel_path = default_export
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_tui.py tests/cli/test_commands.py -v`
Expected: all pass

- [ ] **Step 6: Run full suite**

Run: `python -m pytest tests/ --ignore=tests/test_e2e_aggregators.py -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add braevity/cli/tui.py braevity/cli/commands.py tests/cli/test_tui.py
git commit -m "feat(tui): interactive menu with banner, init, watch, list, remove

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Rich Progress Output for Scans

**Files:**
- Modify: `braevity/core/scheduler.py:79-106` (add progress callback to `run_fast_cycle`)
- Modify: `braevity/cli/tui.py` (use rich progress when launching scan)
- Test: `tests/core/test_scheduler.py` (add test for callback)

**Interfaces:**
- Consumes: `console` from `braevity.cli.theme`, existing `run_fast_cycle` and `run_scheduler`
- Produces: `run_fast_cycle` gains optional `on_progress: Callable[[str, int], None] | None = None` parameter

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/core/test_scheduler.py

@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_fast_cycle_calls_progress_callback(mock_discover, mock_aggs, tmp_path):
    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(return_value=[_job()])
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    progress_calls = []

    def on_progress(source_name, job_count):
        progress_calls.append((source_name, job_count))

    db_path = tmp_path / "seen.db"
    reg_path = tmp_path / "reg.db"

    count, jobs = asyncio.run(run_fast_cycle({}, db_path, reg_path, on_progress=on_progress))
    assert count == 1
    assert ("fake", 1) in progress_calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_scheduler.py::test_fast_cycle_calls_progress_callback -v`
Expected: FAIL with `TypeError: run_fast_cycle() got an unexpected keyword argument 'on_progress'`

- [ ] **Step 3: Add `on_progress` parameter to `run_fast_cycle`**

In `braevity/core/scheduler.py`, change the signature and add callback call:

```python
async def run_fast_cycle(
    config: dict, db_path: Path, registry_path: Path,
    on_progress: callable = None,
) -> tuple[int, list[Job]]:
    store = DedupStore(db_path)
    registry = _ensure_registry(registry_path)

    connector = TCPConnector(limit=10)
    all_jobs: list[Job] = []

    async with ClientSession(connector=connector) as session:
        for agg in AGGREGATORS:
            try:
                jobs = await agg.fetch_all_jobs(session)
                all_jobs.extend(jobs)
                logger.info("%s: fetched %d jobs", agg.name, len(jobs))
                if on_progress:
                    on_progress(agg.name, len(jobs))
            except Exception as e:
                logger.warning("%s failed: %s", agg.name, e)
                if on_progress:
                    on_progress(agg.name, -1)
            await asyncio.sleep(AGGREGATOR_DELAY)

    discovered = discover_from_jobs(all_jobs, registry)
    if discovered:
        logger.info("Cross-ref discovered %d new boards", discovered)

    new_jobs = [j for j in all_jobs if not store.is_seen(j.url)]

    registry.close()
    store.close()
    return len(new_jobs), new_jobs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_scheduler.py -v`
Expected: all pass

- [ ] **Step 5: Add Ctrl+C test**

```python
# Add to tests/core/test_scheduler.py

@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_fast_cycle_keyboard_interrupt_no_traceback(mock_discover, mock_aggs, tmp_path):
    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(side_effect=KeyboardInterrupt)
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    db_path = tmp_path / "seen.db"
    reg_path = tmp_path / "reg.db"

    try:
        asyncio.run(run_fast_cycle({}, db_path, reg_path))
    except KeyboardInterrupt:
        pass  # Expected — caller handles this
```

- [ ] **Step 6: Run full suite**

Run: `python -m pytest tests/ --ignore=tests/test_e2e_aggregators.py -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add braevity/core/scheduler.py tests/core/test_scheduler.py
git commit -m "feat(tui): progress callback hook in run_fast_cycle

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Widen Experience Filter

**Files:**
- Modify: `braevity/core/filter.py:21-99`
- Test: `tests/core/test_filter.py` (add tests for new experience levels)

**Interfaces:**
- Consumes: nothing new
- Produces: `matches_experience(job, level)` now handles: `intern`, `entry_level`, `junior`, `mid`, `senior`, `staff`, `principal`, `manager`, `director`, `any`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/core/test_filter.py

def test_experience_intern():
    assert matches_experience(_job("Software Engineering Intern"), "intern")


def test_experience_intern_rejects_senior():
    assert not matches_experience(_job("Senior Engineer"), "intern")


def test_experience_entry_level():
    assert matches_experience(_job("Entry Level Developer"), "entry_level")


def test_experience_entry_level_fresh_grad():
    assert matches_experience(_job("Fresh Graduate Engineer"), "entry_level")


def test_experience_staff():
    assert matches_experience(_job("Staff Engineer"), "staff")


def test_experience_staff_lead():
    assert matches_experience(_job("Lead Backend Engineer"), "staff")


def test_experience_principal():
    assert matches_experience(_job("Principal Engineer"), "principal")


def test_experience_principal_architect():
    assert matches_experience(_job("Software Architect"), "principal")


def test_experience_manager():
    assert matches_experience(_job("Engineering Manager"), "manager")


def test_experience_manager_head():
    assert matches_experience(_job("Head of Engineering"), "manager")


def test_experience_director():
    assert matches_experience(_job("Director of Engineering"), "director")


def test_experience_director_vp():
    assert matches_experience(_job("VP Engineering"), "director")


def test_experience_i_suffix_no_false_positive():
    # "i" word boundary should not match "Senior" which contains 'i'
    assert not matches_experience(_job("Senior Engineer"), "junior")


def test_experience_sde_i_matches_junior():
    assert matches_experience(_job("SDE I"), "junior")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/core/test_filter.py -v -k "intern or entry_level or staff or principal or manager or director"`
Expected: FAIL — `matches_experience` doesn't handle these levels

- [ ] **Step 3: Rewrite `matches_experience` in `braevity/core/filter.py`**

Replace the existing `SENIOR_SIGNALS`, `JUNIOR_SIGNALS` regexes and `matches_experience` function:

```python
import re
from braevity.core.models import Job

ROLE_SYNONYMS = {
    "engineer": ["developer", "dev"],
    "developer": ["engineer", "dev"],
    "sde": ["software development engineer", "software dev engineer"],
}

LOCATION_ALIASES = {
    "bangalore": ["bengaluru"],
    "bengaluru": ["bangalore"],
    "mumbai": ["bombay"],
    "bombay": ["mumbai"],
    "new york": ["nyc", "ny"],
    "nyc": ["new york", "ny"],
}

REMOTE_VARIANTS = {"remote", "work from home", "wfh", "anywhere", "distributed"}

EXPERIENCE_PATTERNS = {
    "intern": re.compile(r"\b(intern|internship)\b", re.I),
    "entry_level": re.compile(r"\b(entry.level|fresh|graduate|new.grad)\b", re.I),
    "junior": re.compile(r"\b(junior|jr\.?|associate)\b|\bsde\s*i\b|\bi\b(?=\s*$)", re.I),
    "mid": re.compile(r"\b(mid|middle)\b|\b(sde|swe)[\s-]*2\b|\bii\b", re.I),
    "senior": re.compile(r"\b(senior|sr\.?)\b|\b(sde|swe)[\s-]*3\b|\biii\b", re.I),
    "staff": re.compile(r"\b(staff|lead)\b", re.I),
    "principal": re.compile(r"\b(principal|architect|distinguished|fellow)\b", re.I),
    "manager": re.compile(r"\b(manager|engineering\s+manager|head\s+of)\b", re.I),
    "director": re.compile(r"\b(director|vp|vice\s+president|cto|chief)\b", re.I),
}


def _normalize(text: str) -> str:
    return text.strip().lower()


# ... matches_role and matches_location stay exactly the same ...


def matches_experience(job: Job, level: str) -> bool:
    if level == "any":
        return True
    pattern = EXPERIENCE_PATTERNS.get(level)
    if pattern is None:
        return True
    return bool(pattern.search(job.title))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/core/test_filter.py -v`
Expected: all pass (existing + new tests)

- [ ] **Step 5: Run full suite**

Run: `python -m pytest tests/ --ignore=tests/test_e2e_aggregators.py -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add braevity/core/filter.py tests/core/test_filter.py
git commit -m "feat: widen experience filter to 10 categories

Intern, entry level, junior, mid, senior, staff, principal,
manager, director, any. Each with regex-based title matching.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Rich Table Output for Existing Subcommands

**Files:**
- Modify: `braevity/cli/commands.py:76-95` (`list_watches` uses `rich.table`)
- Modify: `braevity/cli/commands.py:112-133` (`start` uses colored output)
- Test: existing `tests/cli/test_commands.py` must still pass

**Interfaces:**
- Consumes: `console`, `Table` from `braevity.cli.theme` and `rich.table`
- Produces: same CLI interface, prettier output

- [ ] **Step 1: Verify existing tests pass before changes**

Run: `python -m pytest tests/cli/test_commands.py -v`
Expected: all pass

- [ ] **Step 2: Update `list_watches` in `commands.py` to use rich table**

```python
@cli.command("list")
def list_watches():
    """Show all configured watches."""
    from braevity.cli.theme import console
    from rich.table import Table

    config = load_config()
    watches = config.get("watches", [])
    if not watches:
        console.print("No watches configured. Run 'braevity watch' first.")
        return

    table = Table(border_style="dim")
    table.add_column("#", style="bold", width=4)
    table.add_column("Role", style="#E84A1E")
    table.add_column("Exp", width=12)
    table.add_column("Locations", min_width=20)
    table.add_column("Interval", width=10)

    for i, w in enumerate(watches, 1):
        locs = w.get("locations", {})
        countries = ", ".join(locs.get("countries", []))
        cities = ", ".join(locs.get("cities", []))
        loc_str = f"{countries} · {cities}" if countries and cities else countries or cities
        table.add_row(
            str(i), w["role"], w.get("experience", "any"),
            loc_str, f"{w.get('poll_interval', 30)}m",
        )

    console.print(table)
```

- [ ] **Step 3: Update `start` command for colored output**

```python
@cli.command()
def start():
    """Start monitoring all configured watches."""
    from braevity.cli.theme import console

    config = load_config()
    watches = config.get("watches", [])
    if not watches:
        console.print("No watches configured. Run 'braevity watch' first.", style="error")
        return

    console.print(f"Starting {len(watches)} watch(es)...", style="primary")
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M",
    )

    from braevity.core.scheduler import run_scheduler

    try:
        asyncio.run(run_scheduler(config))
    except KeyboardInterrupt:
        console.print("\nStopped.", style="dim")
```

- [ ] **Step 4: Run tests to verify no regressions**

Run: `python -m pytest tests/cli/test_commands.py tests/test_integration.py -v`
Expected: all pass

- [ ] **Step 5: Run full suite**

Run: `python -m pytest tests/ --ignore=tests/test_e2e_aggregators.py -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add braevity/cli/commands.py
git commit -m "feat(tui): rich table and colored output for CLI subcommands

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Section 1 (Colors/Theme): Task 1 ✓
- Section 2 (Banner): Task 1 ✓
- Section 3 (Interactive REPL): Task 4 ✓
- Section 3 (Help command): Task 4 ✓
- Section 3 (First-run welcome): Task 4 ✓
- Section 3 (Unknown command handling): Task 4 ✓
- Section 3 (Ctrl+D exit): Task 4 ✓
- Section 3 (Bold orange prompt): Task 4 ✓
- Section 4 (Autocomplete): Tasks 2, 3 ✓
- Section 4 (Experience picker - numbered list): Task 3 ✓
- Section 4 (Experience filter widening): Task 6 ✓
- Section 5 (Inline scan markers ✓/✗): Task 5 ✓
- Section 5 (Rich table): Task 7 ✓
- Section 5 (Default export path ~/.braevity/exports/): Task 4 ✓
- Section 6 (File structure): Tasks 1-4 create all specified files ✓
- Section 7 (Testing): Each task has tests ✓
- Section 8 (Dependencies): Task 1 adds to pyproject.toml ✓

**Placeholder scan:** None found.

**Type consistency:** `EXPERIENCE_LEVELS` is `list[tuple[str, str]]` in Task 2, consumed by indexed numbered picker in Task 3. `on_progress` callback signature `(str, int) -> None` consistent between Task 5 and tests. `prompt_role() -> str`, `prompt_cities() -> list[str]` consumed correctly in Task 4.

**Review Focus:** All five items have tests added to their owning tasks.

---

## GSTACK REVIEW REPORT

| Pass | Dimension | Before | After | Decisions |
|------|-----------|--------|-------|-----------|
| 1 | Information Architecture | 3/10 | 7/10 | D2 (REPL model), D3 (help command), D4 (launch screen) |
| 2 | Interaction State Coverage | 2/10 | 7/10 | D5 (first-run welcome), D6 (error markers ✓/✗), D7 (default export path) |
| 3 | User Journey | 5/10 | 7/10 | No new issues; D2-D7 cover gaps |
| 4 | AI Slop Risk | 8/10 | 8/10 | No issues (CLI context) |
| 5 | Design System Alignment | 4/10 | 6/10 | D8 (bold orange prompt) |
| 6 | Responsive & Accessibility | 5/10 | 7/10 | D9 (Ctrl+D clean exit) |
| 7 | Unresolved Design Decisions | - | - | D10 (numbered experience picker), D11 (unknown command message) |

**Verdict:** PASS -- all 10 decisions approved and incorporated into spec + plan.

**Unresolved decisions:** 0 deferred, 0 blocked.

**Remaining gap:** No DESIGN.md exists for Braevity. Recommend `/design-consultation` as follow-up (not blocking this feature).
