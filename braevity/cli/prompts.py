from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter
from braevity.cli.suggestions import ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS
from braevity.cli.theme import console


def _comma_completer(suggestions: list[str]) -> WordCompleter:
    return WordCompleter(suggestions, ignore_case=True, sentence=True)


def prompt_role() -> str:
    completer = WordCompleter(ROLES, ignore_case=True)
    console.print("  Role:", style="primary", end=" ")
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
    console.print()
    console.print("  Experience level:", style="primary")
    for i, (value, label) in enumerate(EXPERIENCE_LEVELS, 1):
        console.print(f"  {i:>2}. {label}")
    console.print()

    while True:
        console.print("  Pick [1-10]:", style="primary", end=" ")
        raw = pt_prompt("").strip()
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
