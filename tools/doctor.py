"""NOXbot doctor — find and repair modules that cannot be imported.

Why
---
A project that has been edited over time often ends up with handler modules
that nobody imports any more (``customer_info.py``, ``admin_backup.py`` ...).
Because nothing imported them, a broken ``from bot.states import XStates``
inside them stayed invisible — the feature was simply dead. As soon as the
loader started auto-discovering handler modules, those latent errors surfaced.

What this does
--------------
1. Imports every module under ``bot/handlers`` and reports the ones that fail.
2. For the common case "cannot import name 'XStates' from 'bot.states'", it
   reads the module and collects every ``XStates.<attr>`` it uses, so the
   missing :class:`StatesGroup` can be recreated **with the exact state names
   the code expects**.
3. ``--fix`` appends those generated classes to ``bot/states/__init__.py`` and
   re-checks, so the feature comes back to life instead of staying disabled.

Usage
-----
    python tools/doctor.py            # report only
    python tools/doctor.py --fix      # report + write the missing state groups
"""

from __future__ import annotations

import argparse
import ast
import importlib
import pkgutil
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATES_FILE = ROOT / "bot" / "states" / "__init__.py"
MISSING_NAME_RE = re.compile(r"cannot import name '(?P<name>\w+)' from '(?P<module>[\w.]+)'")


def iter_handler_modules() -> list[tuple[str, Path]]:
    """Every ``bot.handlers[.admin].<module>`` on disk."""
    found: list[tuple[str, Path]] = []
    for package in ("bot.handlers", "bot.handlers.admin"):
        pkg = importlib.import_module(package)
        for info in pkgutil.iter_modules(list(pkg.__path__)):
            if info.ispkg or info.name.startswith("_"):
                continue
            path = Path(list(pkg.__path__)[0]) / f"{info.name}.py"
            found.append((f"{package}.{info.name}", path))
    return found


def collect_failures() -> dict[str, tuple[str, Path]]:
    """module -> (error message, source path)."""
    failures: dict[str, tuple[str, Path]] = {}
    for module_name, path in iter_handler_modules():
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - the whole point of the tool
            failures[module_name] = (f"{type(exc).__name__}: {exc}", path)
    return failures


def used_attributes(path: Path, class_name: str) -> list[str]:
    """Every ``ClassName.attr`` referenced in the file, in first-seen order."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    seen: dict[str, None] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == class_name
        ):
            seen.setdefault(node.attr, None)
    return list(seen)


def render_states_group(class_name: str, states: list[str], source: Path) -> str:
    body = "\n".join(f"    {state} = State()" for state in states) or "    pass"
    return (
        f"\n\nclass {class_name}(StatesGroup):\n"
        f'    """Restored by tools/doctor.py from the usage in {source.name}.\n\n'
        f"    The class was referenced by that module but missing from this file,\n"
        f"    which made the whole feature fail to import.\n"
        f'    """\n\n'
        f"{body}\n"
    )


def check_orm() -> list[str]:
    """Configure the ORM and report anything that is out of sync.

    A relationship whose ``back_populates`` counterpart is missing breaks
    *every* query in the bot, so it is checked explicitly. bot.models.compat
    repairs those automatically; whatever it could not repair shows up here.
    """
    problems: list[str] = []
    try:
        import bot.models  # noqa: F401 - registers every model
        from sqlalchemy.orm import configure_mappers

        configure_mappers()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"{type(exc).__name__}: {exc}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="write the missing state groups")
    args = parser.parse_args()

    orm_problems = check_orm()
    from bot.models.compat import HEALED_RELATIONSHIPS

    if HEALED_RELATIONSHIPS:
        print("Relationships completed automatically (declare them for clarity):")
        for missing, needed_by in sorted(HEALED_RELATIONSHIPS.items()):
            print(f"  ~ {missing}  (required by {needed_by})")
        print()
    if orm_problems:
        print("Database models are out of sync:")
        for problem in orm_problems:
            print(f"  X {problem}")
        print()

    failures = collect_failures()
    if not failures:
        if orm_problems:
            return 1
        print("OK - every handler module imports cleanly and the ORM is consistent.")
        return 0

    print(f"{len(failures)} handler module(s) cannot be imported:\n")
    fixes: list[tuple[str, list[str], Path]] = []
    unfixable: list[tuple[str, str]] = []

    for module_name, (error, path) in sorted(failures.items()):
        print(f"  X {module_name}")
        print(f"      {error}")
        match = MISSING_NAME_RE.search(error)
        if match and match.group("module") == "bot.states":
            class_name = match.group("name")
            states = used_attributes(path, class_name)
            print(f"      -> missing StatesGroup {class_name} with: {', '.join(states) or '(no state used)'}")
            fixes.append((class_name, states, path))
        else:
            unfixable.append((module_name, error))
        print()

    if fixes and not args.fix:
        print("Run  python tools/doctor.py --fix  to recreate the missing state groups.")
    elif fixes:
        text = STATES_FILE.read_text(encoding="utf-8")
        added: list[str] = []
        for class_name, states, source in fixes:
            if re.search(rf"^class {class_name}\(", text, re.M):
                continue
            text += render_states_group(class_name, states, source)
            added.append(class_name)
        if added:
            STATES_FILE.write_text(text, encoding="utf-8")
            print(f"Added to {STATES_FILE.relative_to(ROOT)}: {', '.join(added)}")
            print("Re-checking...\n")
            for mod in list(sys.modules):
                if mod.startswith("bot."):
                    del sys.modules[mod]
            remaining = collect_failures()
            if not remaining:
                print("OK - every handler module imports cleanly now.")
                return 0
            print(f"{len(remaining)} module(s) still failing:")
            for name, (err, _) in sorted(remaining.items()):
                print(f"  X {name}: {err}")
            return 1

    if unfixable:
        print("These need a manual look (the doctor only restores missing state groups):")
        for name, err in unfixable:
            print(f"  - {name}: {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
