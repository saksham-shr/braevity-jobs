import asyncio
import logging
from prompt_toolkit.shortcuts import radiolist_dialog
from braevity.cli.theme import console, print_banner
from braevity.cli.prompts import (
    prompt_role, prompt_cities, prompt_countries,
    prompt_experience, prompt_path, prompt_confirm,
)
from braevity.config import load_config, save_config, config_dir
from rich.table import Table


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
    console.print()


def tui_init() -> None:
    config = load_config()
    excel_path = prompt_path("Where should Excel files be saved?", default="./jobs")
    config["excel_path"] = excel_path

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
        console.print("  Run init first.", style="error")
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
        console.print("  No watches configured. Select 'Add a watch' first.", style="dim")
        return

    table = Table(title="Watches", border_style="dim")
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

    console.print()
    console.print(table)
    console.print()


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
        console.print("  No watches configured. Add a watch first.", style="error")
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


MENU_CHOICES = [
    ("init", "Set up Braevity (init)"),
    ("watch", "Add a watch"),
    ("list", "View watches"),
    ("remove", "Remove a watch"),
    ("start", "Start monitoring"),
    ("status", "View status"),
    ("exit", "Exit"),
]

MENU_ACTIONS = {
    "init": tui_init,
    "watch": tui_watch,
    "list": tui_list,
    "remove": tui_remove,
    "start": tui_start,
    "status": tui_status,
}


def main_menu() -> None:
    print_banner()

    while True:
        show_status_line()
        try:
            choice = radiolist_dialog(
                title="Braevity",
                text="What would you like to do?",
                values=MENU_CHOICES,
            ).run()
        except KeyboardInterrupt:
            break

        if choice is None or choice == "exit":
            console.print("  Goodbye!", style="dim")
            break

        action = MENU_ACTIONS.get(choice)
        if action:
            try:
                action()
            except KeyboardInterrupt:
                console.print("\n  Cancelled.", style="dim")
        console.print()
