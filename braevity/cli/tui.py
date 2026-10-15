import asyncio
import logging
import sqlite3
from pathlib import Path
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Input, Header, Footer, DataTable
from textual.screen import Screen
from braevity.config import load_config, save_config, config_dir
from braevity.cli.theme import (
    PRIMARY, SUCCESS, WARNING, ERROR, DIM, DIM_HEADER, FAINT, BG, FG, SURFACE, BORDER,
)
from braevity.cli.suggestions import (
    ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS, EXPERIENCE_MAP,
)

logger = logging.getLogger(__name__)

DOT_LEADER = " ·· "

# Signal-lamp mark, drawn from the same box-drawing glyphs used throughout the
# UI (the prompt box, watch table) rather than an image asset. Shown once at
# launch (first-run and launch screens only) per DESIGN.md: never repeated.
BANNER_LINES = [
    f"  [{PRIMARY}]┌─┐[/{PRIMARY}]",
    f"  [{PRIMARY}]│●│[/{PRIMARY}]  [bold]braevity[/bold]",
    f"  [{PRIMARY}]└─┘[/{PRIMARY}]  [dim]job monitor[/dim]",
]

# Step order reflects the app's actual field sequence (Role, then
# Experience/Level, then Location, then Interval) -- not the sequence a
# visual mockup may have shown, since reordering real fields is a behavior
# change, not a redesign.
WATCH_STEPS = ["Role", "Level", "Location", "Interval"]
INIT_STEPS = ["Export", "SMTP", "Review"]


def _tracked_count() -> int:
    db_path = config_dir() / "seen.db"
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _dot_line(label: str, value: str, width: int = 30) -> str:
    dots = "·" * max(1, width - len(label) - len(str(value)) - 2)
    return f"  {label} {dots} {value}"


def _breadcrumb(steps: list[str], current: str) -> str:
    parts = []
    for step in steps:
        if step == current:
            parts.append(f"[{PRIMARY}][bold]{step}[/bold][/{PRIMARY}]")
        else:
            parts.append(f"[dim]{step}[/dim]")
    return "  " + " [dim]›[/dim] ".join(parts)


APP_CSS = f"""
Screen {{
    background: {BG};
    color: {FG};
}}

#header-bar {{
    dock: top;
    height: 1;
    width: 100%;
    background: {SURFACE};
    color: {FG};
    layout: horizontal;
}}
#header-left {{
    width: 1fr;
    padding: 0 1;
    content-align: left middle;
}}
#header-right {{
    width: auto;
    padding: 0 1;
    color: {DIM_HEADER};
    content-align: right middle;
}}

#content {{
    height: 1fr;
    padding: 1 2;
    overflow-y: auto;
}}

#bottom-bar {{
    dock: bottom;
    height: auto;
    width: 100%;
}}
#command-menu {{
    height: auto;
    width: 100%;
    background: {SURFACE};
    padding: 0 2;
    display: none;
}}
#command-menu.visible {{
    display: block;
}}
#command-menu Static {{
    color: {DIM_HEADER};
}}
#status-line {{
    height: 1;
    width: 100%;
    padding: 0 2;
    color: {DIM};
}}

#prompt-box {{
    height: 3;
    border: round {PRIMARY};
    padding: 0 0;
    margin: 0 1;
    background: {BG};
}}
#prompt-label {{
    width: auto;
    padding: 0 1;
    color: {PRIMARY};
    text-style: bold;
    content-align: left middle;
}}
#prompt-input {{
    width: 1fr;
    background: {BG};
    color: {FG};
    border: none;
}}
#prompt-input:focus {{
    border: none;
}}

#footer-bar {{
    height: 1;
    color: {DIM};
    padding: 0 2;
    background: {BG};
}}

.section-header {{
    color: {PRIMARY};
    text-style: bold;
    margin-top: 1;
}}
.muted {{
    color: {DIM};
}}
.faint {{
    color: {FAINT};
}}
.accent {{
    color: {PRIMARY};
}}
.ok {{
    color: {SUCCESS};
}}
.warn {{
    color: {WARNING};
}}
.err {{
    color: {ERROR};
}}
.bold {{
    text-style: bold;
}}

DataTable {{
    background: {BG};
    height: auto;
    max-height: 20;
}}
DataTable > .datatable--header {{
    background: {BG};
    color: {PRIMARY};
    text-style: bold;
}}
DataTable > .datatable--cursor {{
    background: {SURFACE};
}}
"""

COMMANDS = {
    "/init": "set up Excel export path and SMTP",
    "/watch": "add a watch: role, location, level, interval",
    "/list": "show all watches",
    "/remove": "delete watch number N",
    "/start": "begin monitoring, one scan per watch interval",
    "/status": "dashboard: watches, source health, export",
    "/help": "this screen",
    "/exit": "quit braevity",
}


class BraevityApp(App):
    CSS = APP_CSS
    BINDINGS = [
        Binding("ctrl+c", "quit", "Exit", show=False),
        Binding("escape", "cancel_or_close", "Cancel", show=False),
        Binding("shift+tab", "step_back", "Back", show=False, priority=True),
        Binding("tab", "accept_menu", "Accept", show=False, priority=True),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._mode: str | None = None
        self._flow_stack: list[tuple[str | None, str, bool]] = []
        self._last_scan: str | None = None
        self._watch_data: dict = {}
        self._init_data: dict = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            yield Static(" [bold]braevity[/bold] [dim]· job monitor[/dim]", id="header-left")
            yield Static("", id="header-right")

        yield Vertical(id="content")

        with Vertical(id="bottom-bar"):
            yield Vertical(id="command-menu")
            yield Static("", id="status-line")
            with Horizontal(id="prompt-box"):
                yield Static("braevity>", id="prompt-label")
                yield Input(placeholder="/help for commands", id="prompt-input")
            yield Static("", id="footer-bar")

    def on_mount(self) -> None:
        self._update_header()
        self._update_status_line()
        config = load_config()
        config_path = config_dir() / "config.yaml"
        if not config_path.exists() or not config.get("watches"):
            self._show_first_run()
        else:
            self._show_launch(config)

    # ------------------------------------------------------------------
    # Chrome: header breadcrumb, persistent status line, command menu
    # ------------------------------------------------------------------

    def _set_breadcrumb(self, command: str | None) -> None:
        header_left = self.query_one("#header-left", Static)
        if command is None:
            header_left.update(" [bold]braevity[/bold] [dim]· job monitor[/dim]")
        else:
            header_left.update(
                f" [bold]braevity[/bold] [dim]›[/dim] [{PRIMARY}]{command}[/{PRIMARY}]"
            )

    def _update_header(self) -> None:
        config = load_config()
        watches = config.get("watches", [])
        tracked = _tracked_count()
        header_right = self.query_one("#header-right", Static)
        header_right.update(f"idle · {len(watches)} watches · {tracked} tracked ")

    def _update_status_line(self) -> None:
        config = load_config()
        watches = config.get("watches", [])
        tracked = _tracked_count()
        last_scan = self._last_scan or "never"
        status = self.query_one("#status-line", Static)
        status.update(
            f"  watches [{PRIMARY}]··[/{PRIMARY}] {len(watches)}"
            f"   tracked [{PRIMARY}]··[/{PRIMARY}] {tracked}"
            f"   last scan [{PRIMARY}]··[/{PRIMARY}] {last_scan}"
        )

    def _matching_commands(self, typed: str) -> list[tuple[str, str]]:
        prefix = typed.lower()
        if prefix in ("", "/"):
            return list(COMMANDS.items())
        return [(c, d) for c, d in COMMANDS.items() if c.startswith(prefix)]

    def _show_menu(self, matches: list[tuple[str, str]]) -> None:
        menu = self.query_one("#command-menu", Vertical)
        menu.remove_children()
        menu.mount(Static(f"  [dim]matching commands[/dim]"))
        for cmd, desc in matches:
            menu.mount(Static(f"  [bold]{cmd:<13}[/bold] [dim]{desc}[/dim]"))
        menu.add_class("visible")

    def _hide_menu(self) -> None:
        menu = self.query_one("#command-menu", Vertical)
        menu.remove_children()
        menu.remove_class("visible")

    @on(Input.Changed, "#prompt-input")
    def handle_input_changed(self, event: Input.Changed) -> None:
        if self._mode is not None:
            self._hide_menu()
            return
        value = event.value
        if value.startswith("/"):
            matches = self._matching_commands(value)
            if matches:
                self._show_menu(matches)
            else:
                self._hide_menu()
        else:
            self._hide_menu()

    def action_accept_menu(self) -> None:
        menu = self.query_one("#command-menu", Vertical)
        if not menu.has_class("visible"):
            return
        prompt_input = self.query_one("#prompt-input", Input)
        matches = self._matching_commands(prompt_input.value)
        if matches:
            prompt_input.value = matches[0][0] + " "
            prompt_input.cursor_position = len(prompt_input.value)
        self._hide_menu()

    def action_cancel_or_close(self) -> None:
        menu = self.query_one("#command-menu", Vertical)
        if menu.has_class("visible"):
            self._hide_menu()
            return
        if self._mode is not None:
            self._cancel_flow()

    def action_step_back(self) -> None:
        if self._mode is None or not self._flow_stack:
            return
        mode, placeholder, password = self._flow_stack.pop()
        self._mode = mode
        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.value = ""
        prompt_input.placeholder = placeholder
        prompt_input.password = password
        content = self.query_one("#content", Vertical)
        content.mount(Static(f"  [dim]‹ back[/dim]"))
        content.scroll_end(animate=False)

    def _cancel_flow(self) -> None:
        self._mode = None
        self._flow_stack = []
        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.value = ""
        prompt_input.placeholder = "/help for commands"
        prompt_input.password = False
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static("  [dim]Cancelled.[/dim]"))
        content.scroll_end(animate=False)
        self._set_breadcrumb(None)

    def _append_header(self, command: str, markup: str) -> None:
        """Append a new command's section header into the scrollback,
        preceded by a mode-transition gap -- commands never clear the
        screen, they print below whatever is already there."""
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static(""))
        content.mount(Static(markup))
        self._set_breadcrumb(command)

    def _scroll_to_end(self) -> None:
        self.query_one("#content", Vertical).scroll_end(animate=False)

    def _set_footer(self, text: str) -> None:
        self.query_one("#footer-bar", Static).update(text)

    def _show_first_run(self) -> None:
        content = self.query_one("#content", Vertical)
        for line in BANNER_LINES:
            content.mount(Static(line))
        content.mount(Static(""))
        content.mount(Static(_dot_line("watches", "0")))
        content.mount(Static(_dot_line("tracked", "0")))
        content.mount(Static(_dot_line("last scan", "never")))
        content.mount(Static(""))
        content.mount(Static(f"  [{PRIMARY}][bold]LAST SCAN[/bold][/{PRIMARY}] ──── [dim]none yet[/dim]"))
        content.mount(Static(""))
        content.mount(Static("  [dim]Nothing tracked yet. Three steps to get going:[/dim]"))
        content.mount(Static(""))
        content.mount(Static("  [dim]1[/dim]  [bold]/init[/bold]     [dim]export path and email setup[/dim]"))
        content.mount(Static("  [dim]2[/dim]  [bold]/watch[/bold]    [dim]follow a role, place and level[/dim]"))
        content.mount(Static("  [dim]3[/dim]  [bold]/start[/bold]    [dim]begin monitoring[/dim]"))
        self._set_footer(" Type /help for commands                              ctrl+c to exit ")

    def _show_launch(self, config: dict) -> None:
        content = self.query_one("#content", Vertical)
        watches = config.get("watches", [])
        tracked = _tracked_count()

        for line in BANNER_LINES:
            content.mount(Static(line))
        content.mount(Static(""))
        content.mount(Static(_dot_line("watches", str(len(watches)))))
        content.mount(Static(_dot_line("tracked", str(tracked))))
        content.mount(Static(_dot_line("last scan", self._last_scan or "—")))
        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]WATCHES[/bold][/{PRIMARY}] "
            f"──────────── [dim]{len(watches)}[/dim]"
        ))

        if watches:
            for i, w in enumerate(watches, 1):
                locs = w.get("locations", {})
                countries = ", ".join(locs.get("countries", []))
                cities_list = ", ".join(locs.get("cities", []))
                loc_str = f"{countries} · {cities_list}" if countries and cities_list else countries or cities_list
                content.mount(Static(
                    f"  [dim]{i}[/dim]  {w['role']:<22} "
                    f"{w.get('experience', 'any'):<8} {loc_str:<20} "
                    f"[dim]{w.get('poll_interval', 30)}m[/dim]"
                ))
        else:
            content.mount(Static("  [dim]No watches. Type /watch to add one.[/dim]"))

        self._set_footer(" /start to resume · /status for the dashboard          /help for commands ")

    @on(Input.Submitted, "#prompt-input")
    def handle_command(self, event: Input.Submitted) -> None:
        self._hide_menu()
        if self._mode is not None:
            self._handle_modal_input(event)
            return

        cmd = event.value.strip().lower()
        with event.input.prevent(Input.Changed):
            event.input.value = ""
        if not cmd:
            return

        if not cmd.startswith("/"):
            cmd = "/" + cmd

        parts = cmd.split(None, 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if command == "/exit":
            self.exit()
        elif command == "/help":
            self._show_help()
        elif command == "/init":
            self._show_init()
        elif command == "/watch":
            self._show_watch()
        elif command == "/list":
            self._show_list()
        elif command == "/remove":
            self._handle_remove(args)
        elif command == "/start":
            self._show_start()
        elif command == "/status":
            self._show_status()
        else:
            content = self.query_one("#content", Vertical)
            content.mount(Static(""))
            content.mount(Static(f"  Unknown command '{command}'. Type /help for commands."))
            self._scroll_to_end()

    def _show_help(self) -> None:
        self._show_menu(list(COMMANDS.items()))

    def _show_init(self) -> None:
        self._flow_stack = []
        self._init_data = {}
        self._append_header(
            "/init",
            f"  [{PRIMARY}][bold]Setup[/bold][/{PRIMARY}]  "
            f"[dim]braevity needs an export path before it can scan[/dim]"
            f"             [bold]1/3[/bold]",
        )
        content = self.query_one("#content", Vertical)
        content.mount(Static(_breadcrumb(INIT_STEPS, "Export")))
        content.mount(Static(""))
        content.mount(Static(f"  [{PRIMARY}]❯[/{PRIMARY}] [bold]Excel path[/bold]"))
        content.mount(Static("  [dim]Where should exported job files be saved?[/dim]"))
        content.mount(Static(""))
        content.mount(Static("  [dim]esc cancel[/dim]"))
        self._scroll_to_end()

        prompt_input = self.query_one("#prompt-input", Input)
        default_path = str(config_dir() / "exports")
        prompt_input.placeholder = f"Excel path (default: {default_path})"
        self._mode = "init_excel"
        self._set_footer(" enter to accept default · type a path to override          esc cancel ")

    def _show_watch(self) -> None:
        self._flow_stack = []
        self._watch_data = {}
        self._append_header(
            "/watch",
            _breadcrumb(WATCH_STEPS, "Role"),
        )
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static(f"  [{PRIMARY}]❯[/{PRIMARY}] [bold][{PRIMARY}]Role[/{PRIMARY}][/bold]"))
        content.mount(Static(""))

        suggestions_text = "  [dim]Suggestions: " + ", ".join(ROLES[:8]) + "...[/dim]"
        content.mount(Static(suggestions_text))
        content.mount(Static(""))

        exp_lines = "  [dim]"
        for num, label in EXPERIENCE_LEVELS:
            exp_lines += f" {num:>2} {label:<12}"
            if num == "5":
                exp_lines += "[/dim]\n  [dim]"
        exp_lines += "[/dim]"
        content.mount(Static(
            f"  [{PRIMARY}][bold]EXPERIENCE[/bold][/{PRIMARY}] ──── [dim]1–10[/dim]"
        ))
        content.mount(Static(exp_lines))
        content.mount(Static(""))
        content.mount(Static("  [dim]shift+tab back · esc cancel[/dim]"))
        self._scroll_to_end()

        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.placeholder = "Role to track (e.g. Backend Engineer)"
        self._mode = "watch_role"
        self._set_footer(" ↑↓ choose · tab accept · esc cancel                      1-10 pick level ")

    def _show_list(self) -> None:
        self._update_header()
        self._update_status_line()
        self._set_breadcrumb("/list")
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static(""))
        config = load_config()
        watches = config.get("watches", [])

        content.mount(Static(
            f"  [{PRIMARY}][bold]WATCHES[/bold][/{PRIMARY}] "
            f"──────────── [dim]{len(watches)}[/dim]"
        ))

        if not watches:
            content.mount(Static(""))
            content.mount(Static("  [dim]No watches configured. Type /watch to add one.[/dim]"))
            self._set_footer(" /watch to add a watch                                    /help for commands ")
            self._scroll_to_end()
            return

        table = DataTable()
        table.add_columns("#", "Role", "Experience", "Locations", "Interval")
        for i, w in enumerate(watches, 1):
            locs = w.get("locations", {})
            countries = ", ".join(locs.get("countries", []))
            cities_list = ", ".join(locs.get("cities", []))
            loc_str = f"{countries} · {cities_list}" if countries and cities_list else countries or cities_list
            table.add_row(
                str(i), w["role"], w.get("experience", "any"),
                loc_str, f"{w.get('poll_interval', 30)}m",
            )
        content.mount(Static(""))
        content.mount(table)
        content.mount(Static(""))

        tracked = _tracked_count()
        content.mount(Static(
            f"  [bold]{len(watches)}[/bold] [dim]watches ·[/dim] "
            f"[bold]{tracked}[/bold] [dim]jobs tracked[/dim]"
            f"                    "
            f"[bold]/remove N[/bold] [dim]to delete ·[/dim] "
            f"[bold]/watch[/bold] [dim]to add[/dim]"
        ))
        self._set_footer(" /remove N to delete a watch                              /help for commands ")
        self._scroll_to_end()

    def _handle_remove(self, args: str) -> None:
        config = load_config()
        watches = config.get("watches", [])
        content = self.query_one("#content", Vertical)

        if not args:
            content.mount(Static(""))
            content.mount(Static("  Usage: /remove N (where N is watch number)"))
            self._scroll_to_end()
            return

        try:
            index = int(args)
        except ValueError:
            content.mount(Static(""))
            content.mount(Static(f"  [{ERROR}]Invalid number: {args}[/{ERROR}]"))
            self._scroll_to_end()
            return

        if index < 1 or index > len(watches):
            content.mount(Static(""))
            content.mount(Static(
                f"  [{ERROR}]Invalid index. You have {len(watches)} watches.[/{ERROR}]"
            ))
            self._scroll_to_end()
            return

        removed = watches.pop(index - 1)
        save_config(config)
        self._update_header()
        self._update_status_line()
        self._show_list()
        content.mount(Static(""))
        content.mount(Static(
            f"  [{SUCCESS}]✓ Removed watch: \"{removed['role']}\"[/{SUCCESS}]"
        ))
        self._scroll_to_end()

    def _show_start(self) -> None:
        content = self.query_one("#content", Vertical)
        config = load_config()
        watches = config.get("watches", [])

        if not watches:
            content.mount(Static(""))
            content.mount(Static(
                f"  [{ERROR}]No watches configured. Type /watch to add one.[/{ERROR}]"
            ))
            self._scroll_to_end()
            return

        self._append_header("/start", f"  [{PRIMARY}][bold]SCANNING[/bold][/{PRIMARY}] ──────────── [dim]starting...[/dim]")

        header_right = self.query_one("#header-right", Static)
        header_right.update(
            f"[{SUCCESS}]●[/{SUCCESS}] monitoring · {len(watches)} watches "
        )

        content.mount(Static(""))

        for agg_name in ["RemoteOK", "Jobicy", "Arbeitnow", "Himalayas"]:
            content.mount(Static(
                f"  [dim]·[/dim] {agg_name:<13} [dim]scanning…[/dim]",
                id=f"source-{agg_name.lower()}",
            ))

        content.mount(Static("", id="scan-summary"))
        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]ctrl+c[/bold][/{PRIMARY}] [dim]stops monitoring[/dim]"
        ))
        self._set_footer(" ctrl+c stop monitoring                                   /status dashboard ")
        self._scroll_to_end()

        self._run_scan(config)

    @work(thread=True)
    def _run_scan(self, config: dict) -> None:
        import asyncio as _asyncio
        from braevity.core.scheduler import AGGREGATORS

        db_path = config_dir() / "seen.db"
        results = {}

        async def scan():
            from aiohttp import ClientSession, TCPConnector
            from braevity.core.dedup import DedupStore
            from braevity.core.filter import filter_jobs
            from braevity.core.exporter import export_jobs

            connector = TCPConnector(limit=10)
            store = DedupStore(db_path)
            all_jobs = []

            async with ClientSession(connector=connector) as session:
                for agg in AGGREGATORS:
                    try:
                        jobs = await agg.fetch_all_jobs(session)
                        results[agg.name] = ("ok", len(jobs))
                        all_jobs.extend(jobs)
                        self.call_from_thread(
                            self._update_source, agg.name, "ok", len(jobs)
                        )
                    except Exception as e:
                        err_msg = str(e)[:30]
                        results[agg.name] = ("error", err_msg)
                        self.call_from_thread(
                            self._update_source, agg.name, "error", err_msg
                        )
                    await _asyncio.sleep(1.0)

            new_jobs = [j for j in all_jobs if not store.is_seen(j.url)]
            if new_jobs:
                store.mark_seen_batch(new_jobs)

            watches = config.get("watches", [])
            total_matched = 0
            for watch in watches:
                filtered = filter_jobs(new_jobs, watch)
                if filtered:
                    excel_path = config.get("excel_path", ".")
                    export_jobs(filtered, excel_path)
                    total_matched += len(filtered)

            store.close()

            ok_count = sum(1 for v in results.values() if v[0] == "ok")
            total = len(results)
            self.call_from_thread(
                self._update_scan_summary,
                ok_count, total, len(new_jobs), total_matched
            )

        _asyncio.run(scan())

    def _update_source(self, name: str, status: str, detail) -> None:
        try:
            widget = self.query_one(f"#source-{name.lower()}", Static)
        except Exception:
            return
        if status == "ok":
            widget.update(
                f"  [{SUCCESS}]✓[/{SUCCESS}] {name:<13} "
                f"[{SUCCESS}]{detail} jobs[/{SUCCESS}]"
            )
        else:
            widget.update(
                f"  [{ERROR}]✗[/{ERROR}] {name:<13} "
                f"[{ERROR}]{detail}[/{ERROR}]"
            )

    def _update_scan_summary(
        self, ok_count: int, total: int, new_jobs: int, matched: int
    ) -> None:
        import datetime as _dt
        self._last_scan = _dt.datetime.now().strftime("%H:%M")
        self._update_status_line()
        try:
            widget = self.query_one("#scan-summary", Static)
        except Exception:
            return
        widget.update(
            f"\n  [bold]{ok_count}/{total}[/bold] sources OK, "
            f"[bold]{new_jobs}[/bold] new jobs, "
            f"[bold]{matched}[/bold] matched watches"
        )
        header_right = self.query_one("#header-right", Static)
        header_right.update(
            f"scan done · {new_jobs} new "
        )
        self._scroll_to_end()

    def _show_status(self) -> None:
        self._update_header()
        self._update_status_line()
        self._append_header("/status", f"  [{PRIMARY}][bold]WATCHES[/bold][/{PRIMARY}] ──────────── [dim]—[/dim]")
        content = self.query_one("#content", Vertical)
        config = load_config()
        watches = config.get("watches", [])
        tracked = _tracked_count()
        excel_path = config.get("excel_path", "not set")

        content.mount(Static(_dot_line("watches", str(len(watches)))))
        content.mount(Static(_dot_line("tracked", str(tracked))))
        content.mount(Static(_dot_line("last scan", self._last_scan or "—")))
        content.mount(Static(_dot_line("new today", "—")))

        if watches:
            content.mount(Static(""))
            for i, w in enumerate(watches, 1):
                locs = w.get("locations", {})
                countries = ", ".join(locs.get("countries", []))
                cities_list = ", ".join(locs.get("cities", []))
                loc = f"{countries} · {cities_list}" if countries and cities_list else countries or cities_list
                content.mount(Static(
                    f"  [dim]{i}[/dim]  {w['role']:<19} "
                    f"{w.get('experience', 'any'):<8} "
                    f"[dim]{w.get('poll_interval', 30)}m[/dim]"
                ))

        content.mount(Static(""))

        content.mount(Static(
            f"  [{PRIMARY}][bold]HEALTH[/bold][/{PRIMARY}] "
            f"──────────── [dim]—[/dim]"
        ))
        content.mount(Static("  [dim]No scan data yet. Run /start to begin monitoring.[/dim]"))

        content.mount(Static(""))

        content.mount(Static(
            f"  [{PRIMARY}][bold]EXPORT[/bold][/{PRIMARY}] "
            f"────────────"
        ))
        content.mount(Static(_dot_line("path", excel_path)))
        content.mount(Static(_dot_line("jobs", str(tracked))))

        notification = config.get("notification", {})
        email = notification.get("email", "—")
        content.mount(Static(_dot_line("emailed", email)))

        self._set_footer(" /start to resume monitoring                              /help for commands ")
        self._scroll_to_end()

    def _handle_modal_input(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        prompt_input = event.input
        self._flow_stack.append((self._mode, prompt_input.placeholder, prompt_input.password))
        content = self.query_one("#content", Vertical)

        if self._mode == "init_excel":
            default_path = str(config_dir() / "exports")
            self._init_data["excel_path"] = value if value else default_path
            prompt_input.value = ""

            content.mount(Static(""))
            content.mount(Static(
                f"  [{PRIMARY}][bold]Setup[/bold][/{PRIMARY}]  "
                f"[dim]SMTP configuration[/dim]"
                f"                              [bold]2/3[/bold]"
            ))
            content.mount(Static(_breadcrumb(INIT_STEPS, "SMTP")))
            content.mount(Static(""))
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] [dim]Excel path[/dim]  "
                f"{self._init_data['excel_path']}"
            ))
            content.mount(Static(""))
            content.mount(Static(
                f"  [{PRIMARY}]❯[/{PRIMARY}] [bold]Set up email notifications?[/bold] "
                f"[dim](y/n, default: n)[/dim]"
            ))
            content.mount(Static(""))
            content.mount(Static("  [dim]shift+tab back · esc cancel[/dim]"))
            prompt_input.placeholder = "y/n (default: n)"
            self._mode = "init_smtp_confirm"
            self._set_footer(" y for SMTP setup · n or enter to skip                    shift+tab back · esc cancel ")

        elif self._mode == "init_smtp_confirm":
            prompt_input.value = ""
            if value.lower() in ("y", "yes"):
                self._mode = "init_smtp_host"
                prompt_input.placeholder = "SMTP host (default: smtp.gmail.com)"
                content.mount(Static(""))
                content.mount(Static(
                    f"  [{PRIMARY}][bold]SMTP[/bold][/{PRIMARY}] "
                    f"──── [dim]email digest of new matches[/dim]"
                ))
                content.mount(Static(""))
                content.mount(Static(
                    f"  [{PRIMARY}]❯[/{PRIMARY}] [bold]Host[/bold]"
                ))
            else:
                self._finish_init(smtp=False)

        elif self._mode == "init_smtp_host":
            self._init_data["smtp_host"] = value if value else "smtp.gmail.com"
            prompt_input.value = ""
            prompt_input.placeholder = "SMTP port (default: 587)"
            self._mode = "init_smtp_port"

        elif self._mode == "init_smtp_port":
            self._init_data["smtp_port"] = int(value) if value else 587
            prompt_input.value = ""
            prompt_input.placeholder = "SMTP username (email)"
            self._mode = "init_smtp_user"

        elif self._mode == "init_smtp_user":
            self._init_data["smtp_user"] = value
            prompt_input.value = ""
            prompt_input.placeholder = "SMTP password (app password)"
            prompt_input.password = True
            self._mode = "init_smtp_pass"

        elif self._mode == "init_smtp_pass":
            self._init_data["smtp_password"] = value
            prompt_input.value = ""
            prompt_input.password = False
            prompt_input.placeholder = "Send notifications to (default: same as username)"
            self._mode = "init_smtp_email"

        elif self._mode == "init_smtp_email":
            self._init_data["send_to"] = value if value else self._init_data.get("smtp_user", "")
            prompt_input.value = ""
            self._finish_init(smtp=True)

        elif self._mode == "watch_role":
            if not value:
                self._flow_stack.pop()
                return
            self._watch_data["role"] = value
            prompt_input.value = ""
            prompt_input.placeholder = "Experience level (1-10, default: 1=Any)"

            content.mount(Static(_breadcrumb(WATCH_STEPS, "Level")))
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] Role: [bold]{value}[/bold]"
            ))
            self._mode = "watch_experience"

        elif self._mode == "watch_experience":
            level_key = value if value in EXPERIENCE_MAP else "1"
            self._watch_data["experience"] = EXPERIENCE_MAP[level_key]
            prompt_input.value = ""
            prompt_input.placeholder = "Locations (comma-separated cities/countries, e.g. Remote, Bengaluru)"

            content.mount(Static(_breadcrumb(WATCH_STEPS, "Location")))
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] Experience: "
                f"[bold]{self._watch_data['experience']}[/bold]"
            ))
            self._mode = "watch_location"

        elif self._mode == "watch_location":
            locations = [loc.strip() for loc in value.split(",") if loc.strip()] if value else []
            cities = []
            countries = []
            country_set = {c.lower() for c in COUNTRIES}
            for loc in locations:
                if loc.lower() in country_set:
                    countries.append(loc)
                else:
                    cities.append(loc)
            self._watch_data["locations"] = {"countries": countries, "cities": cities}
            prompt_input.value = ""
            prompt_input.placeholder = "Poll interval in minutes (default: 30)"

            loc_display = ", ".join(locations) if locations else "any"
            content.mount(Static(_breadcrumb(WATCH_STEPS, "Interval")))
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] Locations: [bold]{loc_display}[/bold]"
            ))
            self._mode = "watch_interval"

        elif self._mode == "watch_interval":
            try:
                interval = int(value) if value else 30
            except ValueError:
                interval = 30
            self._watch_data["poll_interval"] = interval
            prompt_input.value = ""
            self._finish_watch()

        self._scroll_to_end()

    def _finish_init(self, smtp: bool) -> None:
        config = load_config()
        config["excel_path"] = self._init_data.get("excel_path", str(config_dir() / "exports"))

        if smtp:
            config["notification"] = {
                "email": self._init_data.get("send_to", ""),
                "smtp_host": self._init_data.get("smtp_host", "smtp.gmail.com"),
                "smtp_port": self._init_data.get("smtp_port", 587),
                "smtp_user": self._init_data.get("smtp_user", ""),
                "smtp_password": self._init_data.get("smtp_password", ""),
            }

        config.setdefault("watches", [])
        save_config(config)

        self._mode = None
        self._flow_stack = []
        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.placeholder = "Type /help for commands"
        prompt_input.password = False

        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static(_breadcrumb(INIT_STEPS, "Review")))
        content.mount(Static(
            f"  [{SUCCESS}]✓ Config saved to "
            f"{config_dir() / 'config.yaml'}[/{SUCCESS}]"
        ))
        content.mount(Static(""))
        if smtp:
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] Excel: {config['excel_path']}"
            ))
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] SMTP: "
                f"{self._init_data.get('smtp_host')}:{self._init_data.get('smtp_port')}"
            ))
        else:
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] Excel: {config['excel_path']}"
            ))
            content.mount(Static("  [dim]Desktop toast notifications enabled.[/dim]"))

        content.mount(Static(""))
        content.mount(Static("  [dim]Next: type /watch to add your first job watch.[/dim]"))
        self._set_footer(" /watch to add a watch                                    /help for commands ")
        self._update_header()
        self._update_status_line()
        self._set_breadcrumb(None)
        self._scroll_to_end()

    def _finish_watch(self) -> None:
        config = load_config()
        watch_entry = {
            "role": self._watch_data["role"],
            "experience": self._watch_data["experience"],
            "locations": self._watch_data["locations"],
            "poll_interval": self._watch_data["poll_interval"],
        }
        config.setdefault("watches", []).append(watch_entry)
        save_config(config)

        self._mode = None
        self._flow_stack = []
        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.placeholder = "Type /help for commands"

        locs = self._watch_data["locations"]
        countries = ", ".join(locs.get("countries", []))
        cities_list = ", ".join(locs.get("cities", []))
        loc_str = f"{countries} · {cities_list}" if countries and cities_list else countries or cities_list or "any"

        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static(_breadcrumb(WATCH_STEPS, "Interval")))
        content.mount(Static(
            f"  [{SUCCESS}]✓ Watch added[/{SUCCESS}]"
        ))
        content.mount(Static(""))
        content.mount(Static(
            f"  [bold]{self._watch_data['role']}[/bold] · "
            f"{self._watch_data['experience']} · "
            f"{loc_str} · "
            f"every {self._watch_data['poll_interval']}m"
        ))
        content.mount(Static(""))
        content.mount(Static(
            "  [dim]Type /start to begin monitoring, or /watch to add another.[/dim]"
        ))
        self._set_footer(" /start to begin · /watch to add another                  /help for commands ")
        self._update_header()
        self._update_status_line()
        self._set_breadcrumb(None)
        self._scroll_to_end()


def main_tui() -> None:
    app = BraevityApp()
    app.run()
