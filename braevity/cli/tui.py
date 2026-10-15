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
    PRIMARY, SUCCESS, WARNING, ERROR, DIM, FAINT, BG, FG, SURFACE, BORDER,
)
from braevity.cli.suggestions import (
    ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS, EXPERIENCE_MAP,
)

logger = logging.getLogger(__name__)

DOT_LEADER = " ·· "


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


APP_CSS = f"""
Screen {{
    background: {BG};
    color: {FG};
}}
#header-bar {{
    dock: top;
    height: 1;
    background: {SURFACE};
    color: {FG};
    padding: 0 1;
}}
#header-bar .header-left {{
    width: auto;
}}
#header-bar .header-right {{
    width: auto;
    color: {DIM};
    text-align: right;
}}
#content {{
    height: 1fr;
    padding: 1 2;
    overflow-y: auto;
}}
#prompt-box {{
    dock: bottom;
    height: 3;
    border: round {BORDER};
    padding: 0 1;
}}
#prompt-input {{
    background: {BG};
    color: {FG};
    border: none;
}}
#prompt-input:focus {{
    border: none;
}}
#footer-bar {{
    dock: bottom;
    height: 1;
    color: {DIM};
    padding: 0 1;
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
    ]

    def compose(self) -> ComposeResult:
        config = load_config()
        watches = config.get("watches", [])
        tracked = _tracked_count()

        with Horizontal(id="header-bar"):
            yield Static(
                " [bold]braevity[/bold] [dim]· job monitor[/dim]",
                classes="header-left",
            )
            yield Static(
                f"idle · {len(watches)} watches · {tracked} tracked ",
                classes="header-right",
                id="header-right",
            )

        yield Vertical(id="content")
        yield Static("", id="footer-bar")
        yield Input(
            placeholder="Type /help for commands",
            id="prompt-input",
        )

    def on_mount(self) -> None:
        self._update_header()
        config = load_config()
        config_path = config_dir() / "config.yaml"
        if not config_path.exists() or not config.get("watches"):
            self._show_first_run()
        else:
            self._show_launch(config)

    def _update_header(self) -> None:
        config = load_config()
        watches = config.get("watches", [])
        tracked = _tracked_count()
        header_right = self.query_one("#header-right", Static)
        header_right.update(f"idle · {len(watches)} watches · {tracked} tracked ")

    def _clear_content(self) -> None:
        content = self.query_one("#content", Vertical)
        content.remove_children()

    def _set_footer(self, text: str) -> None:
        self.query_one("#footer-bar", Static).update(text)

    def _show_first_run(self) -> None:
        self._clear_content()
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static("  [bold]braevity[/bold]  [dim]job monitor[/dim]"))
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
        self._clear_content()
        content = self.query_one("#content", Vertical)
        watches = config.get("watches", [])
        tracked = _tracked_count()

        content.mount(Static(""))
        content.mount(Static("  [bold]braevity[/bold]  [dim]job monitor[/dim]"))
        content.mount(Static(_dot_line("watches", str(len(watches)))))
        content.mount(Static(_dot_line("tracked", str(tracked))))
        content.mount(Static(_dot_line("last scan", "—")))
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
        if hasattr(self, "_mode") and self._mode is not None:
            self._handle_modal_input(event)
            return

        cmd = event.value.strip().lower()
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
            self._clear_content()
            content = self.query_one("#content", Vertical)
            content.mount(Static(f"  Unknown command '{command}'. Type /help for commands."))

    def _show_help(self) -> None:
        self._clear_content()
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]COMMANDS[/bold][/{PRIMARY}] "
            f"──────────── [dim]type / to autocomplete[/dim]"
        ))
        for cmd, desc in COMMANDS.items():
            content.mount(Static(f"  [bold]{cmd:<13}[/bold] [dim]{desc}[/dim]"))

        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]KEYBOARD[/bold][/{PRIMARY}] "
            f"────────────"
        ))
        keys = [
            ("enter", "run command / next field", "ctrl+c", "stop monitoring / cancel"),
            ("tab", "autocomplete / next field", "shift+tab", "previous field"),
            ("↑ ↓", "history / pick suggestion", "esc", "close menu / go back"),
        ]
        for left_key, left_desc, right_key, right_desc in keys:
            content.mount(Static(
                f"  [bold]{left_key:<9}[/bold] [dim]{left_desc:<25}[/dim]"
                f"  [bold]{right_key:<11}[/bold] [dim]{right_desc}[/dim]"
            ))
        content.mount(Static(""))
        content.mount(Static("  [dim]braevity.com[/dim]"))
        self._set_footer(" esc close help                                           / to see commands ")

    def _show_init(self) -> None:
        self._clear_content()
        content = self.query_one("#content", Vertical)
        self._init_step = 1
        self._init_data = {}

        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]Setup[/bold][/{PRIMARY}]  "
            f"[dim]braevity needs an export path before it can scan[/dim]"
            f"             [bold]1/3[/bold]"
        ))
        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}]❯[/{PRIMARY}] [bold]Excel path[/bold]"
        ))
        content.mount(Static("  [dim]Where should exported job files be saved?[/dim]"))
        content.mount(Static(""))

        prompt_input = self.query_one("#prompt-input", Input)
        default_path = str(config_dir() / "exports")
        prompt_input.placeholder = f"Excel path (default: {default_path})"
        self._mode = "init_excel"
        self._set_footer(" enter to accept default · type a path to override          ctrl+c cancel ")

    def _show_watch(self) -> None:
        self._clear_content()
        content = self.query_one("#content", Vertical)
        self._watch_data = {}

        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]New watch[/bold][/{PRIMARY}]  "
            f"[dim]field 1 of 4[/dim]"
        ))
        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}]❯[/{PRIMARY}] [bold][{PRIMARY}]Role[/{PRIMARY}][/bold]"
        ))
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

        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.placeholder = "Role to track (e.g. Backend Engineer)"
        self._mode = "watch_role"
        self._set_footer(" ↑↓ choose · tab accept · esc cancel                      1-10 pick level ")

    def _show_list(self) -> None:
        self._clear_content()
        self._update_header()
        content = self.query_one("#content", Vertical)
        config = load_config()
        watches = config.get("watches", [])

        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]WATCHES[/bold][/{PRIMARY}] "
            f"──────────── [dim]{len(watches)}[/dim]"
        ))

        if not watches:
            content.mount(Static(""))
            content.mount(Static("  [dim]No watches configured. Type /watch to add one.[/dim]"))
            self._set_footer(" /watch to add a watch                                    /help for commands ")
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

    def _handle_remove(self, args: str) -> None:
        config = load_config()
        watches = config.get("watches", [])

        if not args:
            self._clear_content()
            content = self.query_one("#content", Vertical)
            content.mount(Static("  Usage: /remove N (where N is watch number)"))
            return

        try:
            index = int(args)
        except ValueError:
            self._clear_content()
            content = self.query_one("#content", Vertical)
            content.mount(Static(f"  [{ERROR}]Invalid number: {args}[/{ERROR}]"))
            return

        if index < 1 or index > len(watches):
            self._clear_content()
            content = self.query_one("#content", Vertical)
            content.mount(Static(
                f"  [{ERROR}]Invalid index. You have {len(watches)} watches.[/{ERROR}]"
            ))
            return

        removed = watches.pop(index - 1)
        save_config(config)
        self._update_header()
        self._show_list()

        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
        content.mount(Static(
            f"  [{SUCCESS}]✓ Removed watch: \"{removed['role']}\"[/{SUCCESS}]"
        ))

    def _show_start(self) -> None:
        self._clear_content()
        content = self.query_one("#content", Vertical)
        config = load_config()
        watches = config.get("watches", [])

        if not watches:
            content.mount(Static(
                f"  [{ERROR}]No watches configured. Type /watch to add one.[/{ERROR}]"
            ))
            return

        header_right = self.query_one("#header-right", Static)
        header_right.update(
            f"[{SUCCESS}]●[/{SUCCESS}] monitoring · {len(watches)} watches "
        )

        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]SCANNING[/bold][/{PRIMARY}] "
            f"──────────── [dim]starting...[/dim]"
        ))
        content.mount(Static(""))

        for agg_name in ["RemoteOK", "Jobicy", "Arbeitnow", "Himalayas"]:
            content.mount(Static(
                f"  [dim]…[/dim] {agg_name:<13} [dim]waiting...[/dim]",
                id=f"source-{agg_name.lower()}",
            ))

        content.mount(Static("", id="scan-summary"))
        content.mount(Static(""))
        content.mount(Static(
            f"  [{PRIMARY}][bold]ctrl+c[/bold][/{PRIMARY}] [dim]stops monitoring[/dim]"
        ))
        self._set_footer(" ctrl+c stop monitoring                                   /status dashboard ")

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

    def _show_status(self) -> None:
        self._clear_content()
        self._update_header()
        content = self.query_one("#content", Vertical)
        config = load_config()
        watches = config.get("watches", [])
        tracked = _tracked_count()
        excel_path = config.get("excel_path", "not set")

        content.mount(Static(""))

        content.mount(Static(
            f"  [{PRIMARY}][bold]WATCHES[/bold][/{PRIMARY}] "
            f"──────────── [dim]{len(watches)}[/dim]"
        ))
        content.mount(Static(_dot_line("watches", str(len(watches)))))
        content.mount(Static(_dot_line("tracked", str(tracked))))
        content.mount(Static(_dot_line("last scan", "—")))
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

    def _handle_modal_input(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        prompt_input = event.input

        if self._mode == "init_excel":
            default_path = str(config_dir() / "exports")
            self._init_data["excel_path"] = value if value else default_path
            prompt_input.value = ""

            self._clear_content()
            content = self.query_one("#content", Vertical)
            content.mount(Static(""))
            content.mount(Static(
                f"  [{PRIMARY}][bold]Setup[/bold][/{PRIMARY}]  "
                f"[dim]SMTP configuration[/dim]"
                f"                              [bold]2/3[/bold]"
            ))
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
            prompt_input.placeholder = "y/n (default: n)"
            self._mode = "init_smtp_confirm"
            self._set_footer(" y for SMTP setup · n or enter to skip                    ctrl+c cancel ")

        elif self._mode == "init_smtp_confirm":
            prompt_input.value = ""
            if value.lower() in ("y", "yes"):
                self._mode = "init_smtp_host"
                prompt_input.placeholder = "SMTP host (default: smtp.gmail.com)"
                content = self.query_one("#content", Vertical)
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
                return
            self._watch_data["role"] = value
            prompt_input.value = ""
            prompt_input.placeholder = "Experience level (1-10, default: 1=Any)"

            content = self.query_one("#content", Vertical)
            content.mount(Static(""))
            content.mount(Static(
                f"  [{SUCCESS}]✓[/{SUCCESS}] Role: [bold]{value}[/bold]"
            ))
            self._mode = "watch_experience"

        elif self._mode == "watch_experience":
            level_key = value if value in EXPERIENCE_MAP else "1"
            self._watch_data["experience"] = EXPERIENCE_MAP[level_key]
            prompt_input.value = ""
            prompt_input.placeholder = "Locations (comma-separated cities/countries, e.g. Remote, Bengaluru)"

            content = self.query_one("#content", Vertical)
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

            content = self.query_one("#content", Vertical)
            loc_display = ", ".join(locations) if locations else "any"
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
        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.placeholder = "Type /help for commands"
        prompt_input.password = False

        self._clear_content()
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
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
        prompt_input = self.query_one("#prompt-input", Input)
        prompt_input.placeholder = "Type /help for commands"

        locs = self._watch_data["locations"]
        countries = ", ".join(locs.get("countries", []))
        cities_list = ", ".join(locs.get("cities", []))
        loc_str = f"{countries} · {cities_list}" if countries and cities_list else countries or cities_list or "any"

        self._clear_content()
        content = self.query_one("#content", Vertical)
        content.mount(Static(""))
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


def main_tui() -> None:
    app = BraevityApp()
    app.run()
