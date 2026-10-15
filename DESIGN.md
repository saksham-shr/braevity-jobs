---
# gstack: design-md-format=spec
name: Braevity
description: Industrial-utilitarian CLI monitoring console; orange signal lamp against quiet terminal, fast and no-nonsense
colors:
  primary: "#E84A1E"
  on-primary: "#FFFFFF"
  surface: terminal-default
  text: terminal-default
  text-muted: "#888888"
  accent: "#F0A868"
  success: "#44CC44"
  warning: "#F2C94C"
  error: "#FF4444"
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

Orange (`#E84A1E`) owns identity: the `braevity>` prompt, section labels, table headers, and active selections. It never appears on data content. Accent (`#F0A868`) marks input focus, matched query terms, and keyboard hints — warm enough to pair with primary without competing.

Semantic colors are strict: green (`#44CC44`) means success and nothing else. Yellow (`#F2C94C`) means degraded — rate-limited, stale, partial result — the state between healthy and broken that most CLIs ignore. Red (`#FF4444`) means failure and nothing else.

Gray (`#888888`) is everything secondary: timestamps, file paths, metadata, hints. Border gray (`#3A3A3A`) appears only on table rules, used sparingly.

## Typography

Terminal monospace is fixed by the medium. Hierarchy comes from formatting, not font choice:

- **UPPERCASE** for section labels: `WATCHES`, `SCAN REPORT`, `STATUS`. Short — max two words. These are the loudest elements and the structural anchors.
- **Bold** for the prompt, table headers, job counts, and source names. Bold marks actionable or identity-bearing text.
- **Dim** for timestamps, metadata, file paths, and hints. Dim marks contextual text the user can skip when scanning.
- **Normal** for all data content. The information is quiet; the structure is loud.

No italic (terminal italic is unreliable across platforms). No underline except for errors that need attention.

## Layout

Left edge is sacred. Banner, status line, prompt, and section labels all start at column 1. Nothing floats or centers.

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

**Prompt:** `braevity>` in bold `#E84A1E`, followed by one space. The product signature in every interaction.

**Banner:** ASCII art in `#E84A1E`, displayed once at REPL launch. Version line in dim below it. Never repeated during a session.

**Section labels:** UPPERCASE, bold, `#E84A1E`. Two words max. Examples: `WATCHES`, `SCAN REPORT`, `STATUS`, `HEALTH`.

**Watch table:** Dim borders (`#3A3A3A`). Orange header text. Columns: `#` (4w), `Role` (flex), `Exp` (12w), `Locations` (20w min), `Interval` (10w).

**Scan markers:**
- `✓` in `#44CC44` — source completed successfully, followed by job count
- `✗` in `#FF4444` — source failed, followed by error reason in dim
- No marker, `#F2C94C` text — source degraded (rate-limited, timeout, partial)

**Summary line:** `N/M sources OK, X new jobs` after scan. Export path in dim if applicable.

**Status pairs:** Label in dim, dot leader, value in normal. Fixed-width label column.

**Experience picker:** Numbered inline list (1-10), normal text. Selected number echoed back. No color on options; number input only.

**Error messages:** `#FF4444` text, no prefix icon. Invalid input re-prompts without clearing.

**First-run welcome:** Normal text: `Welcome! Type 'init' to set up, or 'help' for commands.`

**Unknown command:** Normal text: `Unknown command 'foo'. Type 'help' for available commands.`

## Do's and Don'ts

- Do: Use orange only for identity elements (prompt, headers, labels)
- Do: Use semantic colors strictly (green=success, yellow=degraded, red=failure)
- Do: Show per-source health on every scan — users need to know which source failed
- Do: Keep scan output compact — one line per source, no blank lines within
- Do: Align to left edge — banner, prompt, labels all start column 1
- Don't: Use color for emphasis or decoration — color is state signal only
- Don't: Use emoji in output — `✓` and `✗` are Unicode symbols, not emoji
- Don't: Add Rich panels, trees, or progress bars — inline markers and tables only
- Don't: Nest indentation more than 2 levels deep
- Don't: Show the banner more than once per REPL session

## Motion

- **Approach:** Minimal-functional
- **Easing:** n/a (terminal has no animation easing)
- **Duration:** n/a (all output is immediate)
- **The one authored moment:** The ASCII banner printing in orange on REPL launch — the single moment of visual flourish before the tool becomes pure information.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-15 | Initial design system created | Created by /design-consultation based on competitive CLI research (gh/npm/cargo/pip), user memorable-thing "fast and no-nonsense", and two independent design proposals (Codex "Signal Console", Claude subagent "Shortwave Station") |
| 2026-10-15 | Warning color #F2C94C added | Adopted from Codex proposal — job monitors need a state between success and failure for rate limits, stale scans, partial results |
| 2026-10-15 | Dot leaders for status pairs | Adopted from Claude subagent proposal — cleaner alignment than tab stops for key-value display |
| 2026-10-15 | UPPERCASE section labels | Both outside voices independently proposed this pattern — strong signal it's the right hierarchy tool for CLI |
