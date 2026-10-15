from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import radiolist_dialog
from braevity.cli.suggestions import ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS
from braevity.cli.theme import console


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
    result = radiolist_dialog(
        title="Experience Level",
        text="Select experience level:",
        values=EXPERIENCE_LEVELS,
    ).run()
    return result or "any"


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
