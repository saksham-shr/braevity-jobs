# Braevity Interactive TUI — Design Spec

**Goal:** Replace plain Click prompts with a branded interactive terminal UI using `rich` + `prompt_toolkit`, while keeping subcommands for scripting.

**Architecture:** TUI layer wraps existing CLI logic. No core business logic changes except widened experience filter and progress hooks in scheduler. `braevity` with no subcommand enters interactive mode; subcommands remain unchanged.

**Tech Stack:** `rich>=13.0` (output), `prompt_toolkit>=3.0` (input), existing Click (subcommands).

**Spec:** `docs/superpowers/specs/2026-10-15-braevity-tui-design.md`

## Global Constraints

- Python >=3.10
- No new dependencies beyond `rich` and `prompt_toolkit`
- Existing Click subcommands must keep working unchanged for scripting/cron
- Terminal must work on Windows 11 (primary) and Linux/macOS
- All colors derived from Braevity branding kit orange `#E84A1E`

---

## 1. Color Scheme & Theme

From Braevity Branding Kit (`D:\Braevity Branding Kit`):

| Token        | Hex       | Usage                              |
|-------------|-----------|-------------------------------------|
| `primary`    | `#E84A1E` | Banner, headers, active menu items  |
| `secondary`  | `#FFFFFF` | Text on dark terminals              |
| `accent`     | `#F0A868` | Muted orange for secondary text     |
| `success`    | `#44CC44` | Checkmarks, success messages        |
| `error`      | `#FF4444` | Failures, error messages            |
| `dim`        | `#888888` | Status lines, timestamps            |

Defined in `braevity/cli/theme.py` as a `rich.theme.Theme` and plain constants for `prompt_toolkit` styles.

## 2. ASCII Banner

Displayed on interactive mode launch:

```
 ____  ____   _   _______     _____ _______   __
| __ )|  _ \ / \ | ____\ \   / /_ _|_   _\ \ / /
|  _ \| |_) / _ \|  _|  \ \ / / | |  | |  \ V /
| |_) |  _ / ___ \ |___  \ V /  | |  | |   | |
|____/|_| /_/   \_\_____|  \_/  |___| |_|   |_|

  Job Monitor v0.1.0
```

Rendered in `primary` orange via `rich.console.Console`. Version read from `pyproject.toml` or hardcoded.

## 3. Interactive REPL

On `braevity` (no subcommand):

1. Print banner in primary orange
2. Show status line: `3 watches · 469 jobs tracked · last scan: 10:03`
3. If first run (no config.yaml): show `Welcome! Type 'init' to set up, or 'help' for commands.`
4. Show `braevity>` prompt (bold primary orange `#E84A1E`) with command autocomplete

### REPL Commands

Type commands at `braevity>` prompt. `prompt_toolkit` provides inline autocomplete.

| Command    | Description                |
|-----------|----------------------------|
| `init`     | Set up Braevity config     |
| `watch`    | Add a new job watch        |
| `list`     | View all configured watches|
| `remove`   | Remove a watch by number   |
| `start`    | Start monitoring           |
| `status`   | Show current status        |
| `discover` | Run board discovery cycle  |
| `boards`   | Manage board registry      |
| `help`     | Show available commands    |
| `exit`     | Exit Braevity              |

### Keyboard Shortcuts

- **Ctrl+C** during sub-prompt (e.g. watch flow): cancel current action, return to `braevity>` prompt
- **Ctrl+C** at main prompt: exit REPL
- **Ctrl+D** at main prompt: exit REPL (EOF, standard REPL convention)
- **Tab**: trigger autocomplete for commands

### Unknown Commands

```
braevity> foo
Unknown command 'foo'. Type 'help' for available commands.
braevity>
```

### Help Output

```
braevity> help

  Commands:
    init      Set up Braevity config
    watch     Add a new job watch
    list      View all configured watches
    remove    Remove a watch by number
    start     Start monitoring
    status    Show current status
    discover  Run board discovery cycle
    boards    Manage board registry
    help      Show this help
    exit      Exit Braevity
```

Status line does NOT refresh on every prompt. Shown once on launch.

## 4. Smart Inputs with Autocomplete

### Role Input

`prompt_toolkit` `WordCompleter` with built-in suggestions:

```
Software Engineer, Software Developer, Backend Engineer, Frontend Engineer,
Full Stack Developer, DevOps Engineer, SRE, Data Engineer, Data Scientist,
ML Engineer, Product Manager, SDE, SDE-2, QA Engineer, Mobile Developer,
Cloud Engineer, Security Engineer, Platform Engineer, iOS Developer,
Android Developer, Engineering Manager
```

User types freely; dropdown appears with matching suggestions. Custom input accepted.

### Location Input

Separate autocomplete for cities and countries.

**Cities:** Top 50 tech hub cities + "Remote":
Bangalore, Mumbai, Delhi, Hyderabad, Chennai, Pune, Kolkata, New York,
San Francisco, Seattle, Austin, Boston, Chicago, Los Angeles, Denver,
London, Berlin, Amsterdam, Paris, Dublin, Stockholm, Zurich, Singapore,
Tokyo, Sydney, Melbourne, Toronto, Vancouver, Sao Paulo, Dubai,
Tel Aviv, Warsaw, Prague, Lisbon, Barcelona, Madrid, Helsinki, Oslo,
Copenhagen, Bucharest, Krakow, Budapest, Tallinn, Riga, Vilnius,
Manila, Ho Chi Minh City, Jakarta, Kuala Lumpur, Bangkok, Remote

**Countries:** Top 30 + "Remote", "Worldwide":
India, United States, United Kingdom, Canada, Germany, France, Netherlands,
Australia, Singapore, Japan, Ireland, Sweden, Switzerland, Israel, Brazil,
UAE, Poland, Czech Republic, Spain, Portugal, Finland, Norway, Denmark,
Romania, Estonia, Lithuania, Latvia, Philippines, Vietnam, Indonesia,
Remote, Worldwide

Comma-separated input supported. Autocomplete triggers per token after comma.

### Experience Picker

Inline numbered list (not radiolist_dialog, not autocomplete):

```
braevity> watch
Role: backend engineer
Location: India, Bangalore

  Experience level:
   1. Any
   2. Intern
   3. Entry Level
   4. Junior
   5. Mid
   6. Senior
   7. Staff / Lead
   8. Principal
   9. Manager
  10. Director+

Pick [1-10]: 4
```

User types number, Enter. Invalid input re-prompts.

### Experience Filter Logic Update

Current `braevity/core/filter.py` handles: junior, mid, senior, any.

New mapping for matching job titles/descriptions:

| Level         | Matches (substring, case-insensitive)                         |
|--------------|---------------------------------------------------------------|
| `intern`      | intern, internship                                            |
| `entry_level` | entry level, entry-level, fresh, graduate, new grad           |
| `junior`      | junior, jr, associate, i (as suffix like "SDE I")             |
| `mid`         | mid, middle, ii, SDE-2, SDE2 (no senior/junior/lead prefix)  |
| `senior`      | senior, sr, iii, SDE-3, SDE3, lead (when not "lead manager") |
| `staff`       | staff, lead, principal (shared with principal)                |
| `principal`   | principal, architect, distinguished, fellow                   |
| `manager`     | manager, engineering manager, em, head of                     |
| `director`    | director, vp, vice president, cto, chief                     |
| `any`         | matches everything                                            |

## 5. Colored Output

### Scan Progress

During `start` (both interactive and subcommand), inline markers per source:

```
  Scanning...
  ✓ RemoteOK          99 jobs
  ✓ Jobicy             50 jobs
  ✗ Arbeitnow          (timeout)
  ✓ Himalayas          20 jobs

  3/4 sources OK, 26 new jobs · exported to ~/.braevity/exports/jobs.xlsx
  ⏰ Next scan in 10 min
```

- Green `✓` on success, red `✗` on failure (uses existing `on_progress` callback)
- Summary line: `N/M sources OK, X new jobs`
- No progress bars (YAGNI for CLI)

### Watch List Table

`rich.table.Table` replaces plain-text output:

```
┌───┬─────────────────────┬──────────┬──────────────────┬──────────┐
│ # │ Role                │ Level    │ Locations        │ Interval │
├───┼─────────────────────┼──────────┼──────────────────┼──────────┤
│ 1 │ SDE                 │ Junior   │ India · Bangalore│ 30m      │
│ 2 │ Full Stack Developer│ Any      │ India · Remote   │ 10m      │
│ 3 │ Software Engineer   │ Any      │ India · Bangalore│ 60m      │
└───┴─────────────────────┴──────────┴──────────────────┴──────────┘
```

Orange header row, clean borders.

### Terminal Notification

Alongside toast, print in terminal:

```
  🔔 26 new jobs: Backend Engineer @ Stripe, SDE-2 @ Microsoft, ...
```

## 6. File Structure

### New Files

| File                         | Purpose                                        |
|-----------------------------|------------------------------------------------|
| `braevity/cli/tui.py`       | Banner, menu loop, interactive mode entry point |
| `braevity/cli/prompts.py`   | Autocomplete inputs, experience picker          |
| `braevity/cli/theme.py`     | Color constants, `rich` Theme                   |
| `braevity/cli/suggestions.py`| Role, city, country, experience lists           |

### Modified Files

| File                         | Change                                         |
|-----------------------------|------------------------------------------------|
| `braevity/cli/commands.py`   | Bare `braevity` invokes TUI; subcommands stay  |
| `braevity/core/filter.py`   | Widen experience matching (10 categories)       |
| `braevity/core/scheduler.py`| Progress callback hook for `rich` bars          |
| `pyproject.toml`            | Add `rich>=13.0`, `prompt-toolkit>=3.0`         |

### Flow

```
braevity (no args) → tui.py:main_repl()
  ├── banner + status line
  ├── first-run check → "Welcome! Type 'init'..." if no config
  ├── REPL loop (prompt_toolkit.prompt with WordCompleter)
  │   ├── init → prompts.py (styled inputs, excel defaults to ~/.braevity/exports/)
  │   ├── watch → prompts.py (autocomplete role/location, numbered experience picker)
  │   ├── list → rich.table
  │   ├── remove → numbered select
  │   ├── start → scheduler with inline ✓/✗ markers
  │   ├── status → rich panel
  │   ├── help → command list
  │   ├── exit → clean exit
  │   └── <unknown> → "Unknown command 'foo'. Type 'help'..."
  ├── Ctrl+C → exit REPL
  └── Ctrl+D → exit REPL (EOFError)

braevity start  → commands.py (Click, with rich output)
braevity watch  → commands.py (Click, plain prompts)
```

TUI wraps existing logic. No core business logic changes except filter widening and progress hooks.

## 7. Testing

- Unit tests for `suggestions.py` (lists are non-empty, no duplicates)
- Unit tests for widened `filter.py` experience matching
- Integration test for TUI menu (mock `prompt_toolkit` input, verify correct function called)
- Existing Click subcommand tests remain unchanged

## 8. Dependencies

```toml
dependencies = [
    "click>=8.0",
    "aiohttp>=3.9",
    "openpyxl>=3.1",
    "pyyaml>=6.0",
    "plyer>=2.1",
    "rich>=13.0",
    "prompt-toolkit>=3.0",
]
```
