---
# gstack: design-md-format=spec
name: Braevity
description: Industrial-utilitarian CLI monitoring console; orange signal lamp against quiet terminal, fast and no-nonsense
colors:
  primary: "#E85C2C"
  on-primary: "#1A1A1A"
  surface: terminal-default
  text: terminal-default
  text-muted: "#85807A"
  text-muted-on-header: "#9A948C"
  accent: "#F0A868"
  success: "#5AA469"
  warning: "#D19A2E"
  error: "#D4605A"
  border: "#3A3A3A"
typography:
  display:
    fontFamily: terminal-monospace
    fontWeight: bold
    fontSize: terminal-default
    letterSpacing: terminal-default
  body:
    fontFamily: terminal-monospace
    fontSize: terminal-default
    lineHeight: terminal-default
  label:
    fontFamily: terminal-monospace
    fontSize: terminal-default
    letterSpacing: terminal-default
    textTransform: uppercase
  mono:
    fontFamily: terminal-monospace
    fontFeature: tnum
rounded:
  sm: n/a
  md: n/a
  lg: n/a
  full: n/a
spacing:
  xs: 0-lines
  sm: 0-lines
  md: 1-line
  lg: 2-lines
  indent: 2-spaces
  max-indent-depth: 2
components:
  prompt:
    text: "braevity>"
    style: bold-primary
  banner:
    style: primary
    show: repl-launch-only
  section-label:
    style: uppercase-bold-primary
  table-header:
    style: bold-primary
    borderStyle: dim
  scan-success:
    marker: "✓"
    style: success
  scan-failure:
    marker: "✗"
    style: error
  scan-degraded:
    style: warning
  status-pair:
    separator: "··"
    valueStyle: text
    labelStyle: dim
---

# Braevity

## Overview

**Creative North Star:** A precise monitoring console where orange acts as a signal lamp against a quiet terminal, delivering job data with zero ceremony.
**Product context:** CLI job monitor for developers tracking openings across 4 ATS platforms and 4 aggregator APIs. Solo developer tool, run from personal terminal.
**Mode per surface:** Operate (the only surface; this is a task-execution tool)
**Reference sites:** gh CLI, cargo, npm, pip (competitive research, not visual references)
**Key characteristics:**
- Fast and no-nonsense: open terminal, get jobs
- Information density over decoration
- Color is signal, not decoration
- One branded moment (banner), then pure data
- Terminal-native: works on dark terminals, degrades gracefully on light

## Colors

**Strategy:** Restrained — orange is the single brand accent, semantic colors handle state, gray handles everything secondary.
**Light or dark:** Dark terminal is the primary use scene (developer workstations). Colors chosen for legibility on #1C1C1C to #2D2D2D backgrounds. No dedicated light-mode palette; dim colors degrade gracefully on light backgrounds.

Orange (`#E85C2C`) owns identity: the `braevity>` prompt, section labels, table headers, and active selections. It never appears on data content. Accent (`#F0A868`) marks input focus, matched query terms, and keyboard hints — warm enough to pair with primary without competing.

Semantic colors are strict: green (`#5AA469`) means success and nothing else. Yellow (`#D19A2E`) means degraded — rate-limited, stale, partial result — the state between healthy and broken that most CLIs ignore. Red (`#D4605A`) means failure and nothing else.

Gray (`#85807A`) is everything secondary: timestamps, file paths, metadata, hints. Border gray (`#3A3A3A`) appears only on table rules, used sparingly. On a `#2A2A2A` header/status-bar background, use the lighter `#9A948C` instead of the body's `#85807A` — the darker gray fails WCAG AA (3.7:1) against that background.

## Typography

Terminal monospace is fixed by the medium. Hierarchy comes from formatting, not font choice:

- **UPPERCASE** for section labels: `WATCHES`, `SCAN REPORT`, `STATUS`. Short — max two words. These are the loudest elements and the structural anchors.
- **Bold** for the prompt, table headers, job counts, and source names. Bold marks actionable or identity-bearing text.
- **Dim** for timestamps, metadata, file paths, and hints. Dim marks contextual text the user can skip when scanning.
- **Normal** for all data content. The information is quiet; the structure is loud.

No italic (terminal italic is unreliable across platforms). No underline except for errors that need attention.

## Layout

Left edge is sacred. Banner, status line, prompt, and section labels all start at column 1. Nothing floats or centers.

**Interaction model: continuous scrollback, not pages.** Every command appends its output below whatever is already on screen — it never clears or replaces prior output. Running `/watch` after a scan leaves the scan output scrolled up, still visible, with the watch form printed underneath it. This is the single structural rule everything else in this section serves: a REPL is a terminal history the user scrolls through, not a stack of full-screen views. A command that wipes what came before is always wrong, no matter how cluttered the result looks — fix the clutter by trimming output, never by hiding history.

**Persistent status line.** One line, always in the same position directly above the prompt box, in the same field order on every single screen regardless of what command is active: `watches ·· N  ··  tracked ·· N  ··  last scan ·· HH:MM`. This is the one thing that's never allowed to change shape — it's the user's constant answer to "where am I, what's the state of things," even mid-wizard, even mid-scan. Contrast with the per-view header line (`braevity › /watch`, bold-primary breadcrumb showing the active command) which does change — that line says *what you're doing*; the status line says *what's true regardless*. They are two different lines and both are always present.

**Back is visible, not buried.** Any multi-field flow (`/watch`, `/init`) shows its escape hatch as a normal-weight line directly under the active field, not folded into 11pt dim footer text nobody reads: `shift+tab back · esc cancel`, same visual weight as the field label itself. Multi-field flows also show a breadcrumb of step labels, not just "field N of 4" — `Role › Location › Level › Confirm`, current step bold-primary, done steps dim, upcoming steps default — so the user can see where they are in the sequence and that going back is a real, named place to land, not just an undo.

**Commands don't take over the screen.** `/help` and command autocomplete are never a full-screen destination. Typing `/` opens a small inline menu anchored directly above the prompt box — live-filtered as you type, 4-6 rows max, dismissible with `esc` — floating over the last couple of lines of scrollback without clearing it. `/help` with no filter opens the same menu, full command list, same anchored position. Nothing the user was looking at before typing `/` ever disappears.

**Scans stream, they don't batch.** A running scan prints one source's result the instant that source finishes, in top-to-bottom order as they complete — never all sources appearing together after the whole scan finishes. A source still in flight shows as `···` in place of a result until it resolves.

Tables use fixed-width columns: numeric and status columns are fixed, the role/name column gets remaining space. Right-align numbers, left-align text. Truncate long location lists with `+N` rather than wrapping.

Two indentation levels maximum (2 spaces each). Source-level detail nests under scan output; nothing nests further.

Status key-value pairs use dot leaders for visual alignment:
```
watches ·· 3
tracked ·· 469
last scan · 10:03
```

One blank line between sections. No blank lines within compact scan output. Two blank lines only before major mode transitions (banner to prompt, scan cycle end).

Narrow terminals: collapse locations and interval into two-line rows rather than wrapping tables into unreadable grids.

## Elevation & Depth

Not applicable. Terminal has no z-axis. Visual separation uses blank lines, dim borders, and color hierarchy.

## Shapes

Not applicable. Terminal has no border-radius. Table borders use Rich's built-in dim style.

## Components

**Prompt:** `braevity>` in bold `#E85C2C`, followed by one space. The product signature in every interaction.

**Banner:** ASCII art in `#E85C2C`, displayed once at REPL launch. Version line in dim below it. Never repeated during a session.

**Section labels:** UPPERCASE, bold, `#E85C2C`. Two words max. Examples: `WATCHES`, `SCAN REPORT`, `STATUS`, `HEALTH`.

**Watch table:** Dim borders (`#3A3A3A`). Orange header text. Columns: `#` (4w), `Role` (flex), `Exp` (12w), `Locations` (20w min), `Interval` (10w).

**Scan markers:**
- `✓` in `#5AA469` — source completed successfully, followed by job count
- `✗` in `#D4605A` — source failed, followed by error reason in dim
- No marker, `#D19A2E` text — source degraded (rate-limited, timeout, partial)

**Summary line:** `N/M sources OK, X new jobs` after scan. Export path in dim if applicable.

**Status pairs:** Label in dim, dot leader, value in normal. Fixed-width label column.

**Experience picker:** Numbered inline list (1-10), normal text. Selected number echoed back. No color on options; number input only.

**Error messages:** `#D4605A` text, no prefix icon. Invalid input re-prompts without clearing.

**First-run welcome:** Normal text: `Welcome! Type 'init' to set up, or 'help' for commands.`

**Unknown command:** Normal text: `Unknown command 'foo'. Type 'help' for available commands.`

**Status line:** One fixed-order line directly above the prompt box: `watches ·· N  ··  tracked ·· N  ··  last scan ·· HH:MM`, dim labels, normal values, dot leaders between pairs. Same position, same field order, on every screen without exception — it is the one element immune to whatever command is active.

**Command menu (slash autocomplete):** Anchored directly above the prompt box, not full-screen. Opens on `/`, live-filters as the user types, 4-6 rows max, each row `/command  one-line description`. Dismiss with `esc` or a non-matching keystroke. Scrollback above it stays visible and unobstructed below the menu's top edge.

**Flow breadcrumb:** For multi-field flows (`/watch`, `/init`): a one-line sequence of step names — `Role › Location › Level › Confirm` — current step bold `#E85C2C`, completed steps dim, upcoming steps normal. Printed once per flow, directly under the flow's command-breadcrumb header line.

**Back affordance:** `shift+tab back · esc cancel`, normal weight, directly under the active field. Same visual weight as the field label — never folded into dim footer text.

## Do's and Don'ts

- Do: Use orange only for identity elements (prompt, headers, labels)
- Do: Use semantic colors strictly (green=success, yellow=degraded, red=failure)
- Do: Show per-source health on every scan — users need to know which source failed
- Do: Keep scan output compact — one line per source, no blank lines within
- Do: Align to left edge — banner, prompt, labels all start column 1
- Do: Append every command's output below what's already on screen — never clear or replace prior output
- Do: Keep the status line in the same position and field order on every screen, no exceptions
- Do: Stream scan results source-by-source as they complete, with `···` for sources still in flight
- Don't: Use color for emphasis or decoration — color is state signal only
- Don't: Use emoji in output — `✓` and `✗` are Unicode symbols, not emoji
- Don't: Add Rich panels, trees, or progress bars — inline markers and tables only
- Don't: Nest indentation more than 2 levels deep
- Don't: Show the banner more than once per REPL session
- Don't: Let any command take over the full screen — `/help` and autocomplete are anchored overlays, not destinations
- Don't: Bury a flow's back/cancel affordance in dim footer text nobody reads

## Motion

- **Approach:** Minimal-functional
- **Easing:** n/a (terminal has no animation easing)
- **Duration:** n/a (all output is immediate)
- **The one authored moment:** The ASCII banner printing in orange on REPL launch — the single moment of visual flourish before the tool becomes pure information.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-15 | Initial design system created | Created by /design-consultation based on competitive CLI research (gh/npm/cargo/pip), user memorable-thing "fast and no-nonsense", and two independent design proposals (Codex "Signal Console", Claude subagent "Shortwave Station") |
| 2026-10-15 | Warning color #D19A2E added | Adopted from Codex proposal — job monitors need a state between success and failure for rate limits, stale scans, partial results |
| 2026-10-15 | Dot leaders for status pairs | Adopted from Claude subagent proposal — cleaner alignment than tab stops for key-value display |
| 2026-10-15 | UPPERCASE section labels | Both outside voices independently proposed this pattern — strong signal it's the right hierarchy tool for CLI |
| 2026-10-15 | Palette retuned to muted tones (#E85C2C/#5AA469/#D19A2E/#D4605A, was #E84A1E/#44CC44/#F2C94C/#FF4444); header-row gray split out as #9A948C | Critique of the 9-screen mockup found every screen built against a more muted palette than the original spec — muted reads better on the dark terminal background than the brighter originals, so the mockup's values became canonical. The muted body gray (#85807A) also failed AA (3.7:1) on the #2A2A2A header/status-bar background, so that context gets its own lighter token |
| 2026-10-15 | Switched from full-screen "pages" per command to one continuous scrollback, with a persistent status line, anchored slash-autocomplete overlay, visible flow breadcrumbs/back affordance, and streaming scan output | User feedback on the 9-screen mockup: flow felt cluttered, state was unclear, and there was no way to navigate back — all three traced to the same root cause, each command wiping the screen and replacing it with a new "page." Rebuilt on Claude Code's own interaction model (continuous log + fixed input + transient overlays) instead of patching each symptom separately |
