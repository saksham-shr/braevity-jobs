from rich.console import Console
from rich.theme import Theme

PRIMARY = "#E84A1E"
ACCENT = "#F0A868"
SUCCESS = "#44CC44"
WARNING = "#F2C94C"
ERROR = "#FF4444"
DIM = "#888888"
BORDER = "#3A3A3A"

BRAEVITY_THEME = Theme({
    "primary": f"bold {PRIMARY}",
    "accent": ACCENT,
    "success": f"bold {SUCCESS}",
    "warning": f"bold {WARNING}",
    "error": f"bold {ERROR}",
    "dim": DIM,
    "border": BORDER,
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
