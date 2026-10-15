import asyncio
import click
import logging
from braevity.config import load_config, save_config, config_dir


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Braevity — CLI job monitor for ATS platforms."""
    if ctx.invoked_subcommand is None:
        from braevity.cli.tui import main_repl
        main_repl()


@cli.command()
def init():
    """Set up Braevity config (Excel path, notifications)."""
    excel_path = click.prompt("Where should Excel files be saved?", default="./jobs")

    data = load_config()
    data["excel_path"] = excel_path

    use_smtp = click.confirm("Set up email notifications via SMTP?", default=False)
    if use_smtp:
        email = click.prompt("Notification email")
        smtp_host = click.prompt("SMTP host", default="smtp.gmail.com")
        smtp_port = click.prompt("SMTP port", default=587, type=int)
        smtp_user = click.prompt("SMTP user (email)")
        smtp_password = click.prompt("SMTP password (app password)", hide_input=True)
        data["notification"] = {
            "email": email,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_user": smtp_user,
            "smtp_password": smtp_password,
        }
    else:
        click.echo("Desktop toast notifications enabled (default).")

    data.setdefault("watches", [])
    save_config(data)
    click.echo(f"Config saved to {config_dir() / 'config.yaml'}")


@cli.command()
def watch():
    """Add a new job watch (role, experience, locations)."""
    config = load_config()
    if not config:
        click.echo("Run 'braevity init' first.")
        return

    role = click.prompt("Role to track")
    experience = click.prompt(
        "Experience level (junior/mid/senior/any)", default="any"
    )
    countries_raw = click.prompt("Countries (comma-separated)")
    cities_raw = click.prompt("Cities (comma-separated)")
    poll_interval = click.prompt("Poll interval in minutes", default=30, type=int)

    countries = [c.strip() for c in countries_raw.split(",") if c.strip()]
    cities = [c.strip() for c in cities_raw.split(",") if c.strip()]

    watch_entry = {
        "role": role,
        "experience": experience,
        "locations": {"countries": countries, "cities": cities},
        "poll_interval": poll_interval,
    }
    config.setdefault("watches", []).append(watch_entry)
    save_config(config)
    click.echo(
        f"Watch added: \"{role}\" | {experience} | "
        f"{len(countries)} countries, {len(cities)} cities"
    )


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


@cli.command()
@click.argument("index", type=int)
def remove(index):
    """Remove a watch by its index number."""
    config = load_config()
    watches = config.get("watches", [])
    if index < 1 or index > len(watches):
        click.echo(f"Invalid index. You have {len(watches)} watches.")
        return
    removed = watches.pop(index - 1)
    save_config(config)
    click.echo(f"Removed watch: \"{removed['role']}\"")


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


@cli.command()
def status():
    """Show current status."""
    config = load_config()
    watches = config.get("watches", [])
    excel_path = config.get("excel_path", "not set")
    click.echo(f"Watches: {len(watches)}")
    click.echo(f"Excel path: {excel_path}")
    db_path = config_dir() / "seen.db"
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
        conn.close()
        click.echo(f"Total jobs tracked: {count}")
    else:
        click.echo("No jobs tracked yet.")


@cli.command()
def discover():
    """Import seed boards and run one cross-reference discovery cycle."""
    from braevity.core.registry import BoardRegistry
    from braevity.core.migration import seed_registry, migrate_catalog

    config = load_config()
    db_path = config_dir() / "seen.db"
    registry_path = config_dir() / "registry.db"

    registry = BoardRegistry(registry_path)
    migrated = migrate_catalog(registry)
    seeded = seed_registry(registry)
    click.echo(f"Migrated {migrated} boards from catalog, seeded {seeded} new boards.")
    click.echo(f"Total boards: {registry.board_count()}")
    registry.close()

    from braevity.core.scheduler import run_fast_cycle

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M")

    count, _ = asyncio.run(run_fast_cycle(config, db_path, registry_path))
    click.echo(f"Discovery complete. {count} new jobs found via aggregators.")


@cli.group()
def boards():
    """Manage the board registry."""
    pass


@boards.command("list")
@click.option("--ats", default=None, help="Filter by ATS (greenhouse, lever, workday, ashby)")
def boards_list(ats):
    """List all registered boards."""
    from braevity.core.registry import BoardRegistry

    registry_path = config_dir() / "registry.db"
    registry = BoardRegistry(registry_path)
    board_list = registry.get_active_boards(ats)

    if not board_list:
        click.echo("No boards registered. Run 'braevity discover' first.")
        registry.close()
        return

    click.echo(f"{'ATS':<12} {'Token':<25} {'Company':<20} {'Jobs':<6} {'Last Fetched':<22} {'From'}")
    click.echo("-" * 95)
    for b in board_list:
        click.echo(
            f"{b['ats']:<12} {b['token']:<25} {(b['company_name'] or ''):<20} "
            f"{b['job_count']:<6} {(b['last_fetched'] or 'never'):<22} {b['discovered_from'] or ''}"
        )

    click.echo(f"\nTotal: {len(board_list)} active boards")
    registry.close()


@boards.command("add")
@click.argument("ats")
@click.argument("token")
@click.option("--name", default=None, help="Company name")
def boards_add(ats, token, name):
    """Manually add a board to the registry."""
    from braevity.core.registry import BoardRegistry

    if ats not in ("greenhouse", "lever", "workday", "ashby"):
        click.echo(f"Unknown ATS: {ats}. Use greenhouse, lever, workday, or ashby.")
        return

    registry_path = config_dir() / "registry.db"
    registry = BoardRegistry(registry_path)
    if registry.register(ats, token, company_name=name, discovered_from="manual"):
        click.echo(f"Added {ats}:{token}")
    else:
        click.echo(f"Already registered: {ats}:{token}")
    registry.close()
