"""Static audit of inline-button callback_data vs registered callback handlers.

Why this exists
---------------
Most "دکمه کار نمی‌کنه" bugs in an aiogram project come from three causes:

1. A button emits ``callback_data`` that **no handler filter matches**
   (typo, renamed prefix, handler never registered / router never included).
2. The generated ``callback_data`` is **longer than 64 bytes**, which Telegram
   rejects with ``BUTTON_DATA_INVALID`` — the whole message fails to send/edit,
   so *every* button of that keyboard disappears.
3. A handler exists but its module's router is never attached to the
   dispatcher, so the callback is silently "not handled".

This script parses the source tree with ``ast`` (no bot token, no network) and
reports all three. Run it in CI or before a release:

    python tools/audit_buttons.py            # human report, exit 1 on errors
    python tools/audit_buttons.py --json     # machine readable
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOT_DIR = ROOT / "bot"

# Telegram hard limit for callback_data (bytes, UTF-8).
CALLBACK_DATA_LIMIT = 64

# Worst-case rendered length for a dynamic f-string part, by heuristic.
UUID_LEN = 36  # models use 36-char string UUID primary keys
INT_LEN = 12
SHORT_LEN = 16


@dataclass
class ButtonData:
    """A callback_data value produced somewhere in the source tree."""

    pattern: str  # literal text, with '{...}' for dynamic parts
    literal_prefix: str  # static text before the first dynamic part
    worst_case_len: int
    file: str
    line: int
    is_dynamic: bool
    safe_builder: bool = False  # built through cb(), which cannot exceed the limit


@dataclass
class HandlerFilter:
    """A callback filter registered by a handler."""

    kind: str  # eq | prefix | in | regexp | contains | unknown
    value: str
    file: str
    line: int
    func: str


@dataclass
class Report:
    buttons: list[ButtonData] = field(default_factory=list)
    filters: list[HandlerFilter] = field(default_factory=list)
    orphan_buttons: list[ButtonData] = field(default_factory=list)
    oversized: list[ButtonData] = field(default_factory=list)
    unused_filters: list[HandlerFilter] = field(default_factory=list)
    unreachable_buttons: list[str] = field(default_factory=list)


def _iter_py_files() -> list[Path]:
    return sorted(p for p in BOT_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _dyn_len(node: ast.AST) -> int:
    """Worst-case rendered length of a dynamic f-string slot."""
    src = ast.unparse(node).lower()
    if "id" in src or "uuid" in src:
        return UUID_LEN
    if any(k in src for k in ("count", "page", "offset", "index", "qty", "amount")):
        return INT_LEN
    return SHORT_LEN


def _render_pattern(node: ast.AST) -> tuple[str, str, int, bool] | None:
    """Return (pattern, literal_prefix, worst_case_len, is_dynamic)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        v = node.value
        return v, v, len(v.encode()), False
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        prefix_done = False
        prefix = ""
        length = 0
        dynamic = False
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                length += len(value.value.encode())
                if not prefix_done:
                    prefix += value.value
            else:
                dynamic = True
                prefix_done = True
                parts.append("{" + ast.unparse(value.value if isinstance(value, ast.FormattedValue) else value) + "}")
                length += _dyn_len(value.value if isinstance(value, ast.FormattedValue) else value)
        return "".join(parts), prefix, length, dynamic
    return None



# --- Resolution of prefix parameters ---------------------------------------
# Keyboard builders take a ``prefix`` / ``callback_prefix`` argument, so their
# callback_data cannot be judged statically without knowing the values used by
# callers. Collect every constant that reaches such a parameter (defaults +
# call sites) and expand the pattern for each of them.

PREFIX_PARAM_HINTS = ("prefix", "action", "kind", "scope", "section")


def collect_param_values(trees: dict[str, ast.AST]) -> tuple[dict[str, dict[str, set[str]]], set[str]]:
    """Return (func -> param -> constant values, set of functions that are called).

    Call-site values win over signature defaults: a default that no caller ever
    uses would otherwise create phantom callback patterns.
    """
    signatures: dict[str, list[str]] = {}
    defaults: dict[str, dict[str, set[str]]] = {}
    from_calls: dict[str, dict[str, set[str]]] = {}
    called: set[str] = set()

    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                signatures[node.name] = args + [a.arg for a in node.args.kwonlyargs]
                slot = defaults.setdefault(node.name, {})
                dflts = node.args.defaults
                for arg, default in zip(args[len(args) - len(dflts):], dflts):
                    if isinstance(default, ast.Constant) and isinstance(default.value, str):
                        slot.setdefault(arg, set()).add(default.value)
                for kwarg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                    if isinstance(default, ast.Constant) and isinstance(default.value, str):
                        slot.setdefault(kwarg.arg, set()).add(default.value)

    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            if name is None:
                continue
            called.add(name)
            if name not in signatures:
                continue
            params = signatures[name]
            slot = from_calls.setdefault(name, {})
            for idx, arg in enumerate(node.args):
                if idx < len(params) and isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    slot.setdefault(params[idx], set()).add(arg.value)
            for kw in node.keywords:
                if kw.arg and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    slot.setdefault(kw.arg, set()).add(kw.value.value)

    merged: dict[str, dict[str, set[str]]] = {}
    for func, params in signatures.items():
        merged[func] = {}
        for param in params:
            call_values = from_calls.get(func, {}).get(param)
            if call_values:
                merged[func][param] = call_values
            elif defaults.get(func, {}).get(param):
                merged[func][param] = defaults[func][param]
    return merged, called


class ButtonVisitor(ast.NodeVisitor):
    def __init__(
        self,
        path: Path,
        report: Report,
        param_values: dict[str, dict[str, set[str]]],
        called_funcs: set[str],
    ) -> None:
        self.path = path
        self.report = report
        self.param_values = param_values
        self.called_funcs = called_funcs
        self.func_stack: list[str] = []

    def _visit_func(self, node):  # noqa: ANN001
        self.func_stack.append(node.name)
        self.generic_visit(node)
        self.func_stack.pop()

    visit_FunctionDef = _visit_func  # noqa: N815
    visit_AsyncFunctionDef = _visit_func  # noqa: N815

    def _substitutions(self) -> dict[str, set[str]]:
        if not self.func_stack:
            return {}
        return self.param_values.get(self.func_stack[-1], {})

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        enclosing = self.func_stack[-1] if self.func_stack else None
        # Only *keyboard builders* can be judged by call sites; handler
        # functions are invoked by aiogram, never by name.
        in_keyboards = "keyboards" in self.path.parts
        unreachable = in_keyboards and enclosing is not None and enclosing not in self.called_funcs
        for kw in node.keywords:
            if kw.arg != "callback_data":
                continue
            if unreachable:
                self.report.unreachable_buttons.append(
                    f"{self.path.relative_to(ROOT)}:{kw.value.lineno} (in {enclosing}(), never called)"
                )
                continue
            uses_cb = isinstance(kw.value, ast.Call) and getattr(kw.value.func, "id", None) == "cb"
            for rendered in _render_all(kw.value, self._substitutions()):
                pattern, prefix, length, dynamic = rendered
                self.report.buttons.append(
                    ButtonData(
                        pattern=pattern,
                        literal_prefix=prefix,
                        worst_case_len=length,
                        file=str(self.path.relative_to(ROOT)),
                        line=kw.value.lineno,
                        is_dynamic=dynamic,
                        safe_builder=uses_cb,
                    )
                )
        self.generic_visit(node)


def _render_all(node: ast.AST, subs: dict[str, set[str]]) -> list[tuple[str, str, int, bool]]:
    """Render a callback_data expression, expanding known prefix parameters.

    ``cb("a", x, y)`` (the safe builder) is treated like an f-string join.
    """
    if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "cb":
        parts: list[ast.AST] = list(node.args)
        expanded: list[tuple[str, str, int, bool]] = []
        pattern_bits: list[str] = []
        length = 0
        dynamic = False
        prefix = ""
        prefix_done = False
        for i, arg in enumerate(parts):
            if i:
                pattern_bits.append(":")
                length += 1
                if not prefix_done:
                    prefix += ":"
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                pattern_bits.append(arg.value)
                length += len(arg.value.encode())
                if not prefix_done:
                    prefix += arg.value
            else:
                dynamic = True
                prefix_done = True
                pattern_bits.append("{" + ast.unparse(arg) + "}")
                length += _dyn_len(arg)
        joined = "".join(pattern_bits)
        slots = re.findall(r"\{([a-zA-Z_][a-zA-Z_0-9]*)\}", joined)
        resolvable_cb = {name: subs[name] for name in slots if name in subs and subs[name]}
        if not resolvable_cb:
            return [(joined, prefix, length, dynamic)]
        variants = [joined]
        for name, values in resolvable_cb.items():
            variants = [v.replace("{" + name + "}", value) for v in variants for value in sorted(values)]
        for variant in variants:
            static_prefix = variant.split("{", 1)[0]
            still_dynamic = "{" in variant
            slots_left = re.findall(r"\{[^}]*\}", variant)
            static_len = len(re.sub(r"\{[^}]*\}", "", variant).encode())
            dyn = sum(UUID_LEN if ("id" in sl.lower() or "uuid" in sl.lower()) else INT_LEN for sl in slots_left)
            expanded.append((variant, static_prefix, static_len + dyn, still_dynamic))
        return expanded

    base = _render_pattern(node)
    if base is None:
        return []
    pattern, prefix, length, dynamic = base
    if not dynamic:
        return [base]

    # Expand "{param}" slots when the parameter's constant values are known.
    results: list[tuple[str, str, int, bool]] = []
    slots = re.findall(r"\{([a-zA-Z_][a-zA-Z_0-9]*)\}", pattern)
    resolvable = {s: subs[s] for s in slots if s in subs and subs[s]}
    if not resolvable:
        return [base]

    def expand(text: str, remaining: list[str]) -> list[str]:
        if not remaining:
            return [text]
        name = remaining[0]
        out: list[str] = []
        for value in sorted(resolvable[name]):
            out.extend(expand(text.replace("{" + name + "}", value), remaining[1:]))
        return out

    for concrete in expand(pattern, list(resolvable)):
        static_prefix = concrete.split("{", 1)[0]
        slots_left = re.findall(r"\{[^}]*\}", concrete)
        still_dynamic = bool(slots_left)
        static_len = len(re.sub(r"\{[^}]*\}", "", concrete).encode())
        dyn_len = 0
        for slot in slots_left:
            inner = slot[1:-1].lower()
            dyn_len += UUID_LEN if ("id" in inner or "uuid" in inner) else INT_LEN
        results.append((concrete, static_prefix, static_len + dyn_len, still_dynamic))
    return results


def _extract_filters(node: ast.AST, path: Path, func: str, report: Report) -> None:
    """Pull F.data comparisons out of a decorator expression."""
    for sub in ast.walk(node):
        # F.data == "x"   /   "x" == F.data
        if isinstance(sub, ast.Compare) and len(sub.ops) == 1:
            left, right = sub.left, sub.comparators[0]
            src_left = ast.unparse(left)
            if src_left.endswith("F.data") or src_left == "F.data":
                if isinstance(sub.ops[0], ast.Eq) and isinstance(right, ast.Constant):
                    report.filters.append(
                        HandlerFilter("eq", str(right.value), str(path.relative_to(ROOT)), sub.lineno, func)
                    )
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            owner = ast.unparse(sub.func.value)
            if not owner.endswith("F.data"):
                continue
            meth = sub.func.attr
            for arg in sub.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    kind = {
                        "startswith": "prefix",
                        "regexp": "regexp",
                        "contains": "contains",
                    }.get(meth, "unknown")
                    report.filters.append(
                        HandlerFilter(kind, arg.value, str(path.relative_to(ROOT)), sub.lineno, func)
                    )
                elif isinstance(arg, (ast.Set, ast.List, ast.Tuple)) and meth == "in_":
                    for elt in arg.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            report.filters.append(
                                HandlerFilter("eq", elt.value, str(path.relative_to(ROOT)), sub.lineno, func)
                            )


class HandlerVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, report: Report) -> None:
        self.path = path
        self.report = report

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            target = ast.unparse(dec.func)
            if "callback_query" not in target:
                continue
            _extract_filters(dec, self.path, node.name, self.report)
        self.generic_visit(node)

    visit_FunctionDef = _visit_func  # noqa: N815
    visit_AsyncFunctionDef = _visit_func  # noqa: N815


def _matches(button: ButtonData, filters: list[HandlerFilter]) -> HandlerFilter | None:
    text = button.pattern
    static = button.literal_prefix
    for f in filters:
        if f.kind == "eq":
            if not button.is_dynamic and f.value == text:
                return f
            # dynamic buttons never equal a constant filter
        elif f.kind == "prefix":
            if text.startswith(f.value) or (static and f.value.startswith(static) and button.is_dynamic and static):
                # dynamic: "cat:{id}" is served by prefix "cat:"
                if text.startswith(f.value) or f.value == static:
                    return f
        elif f.kind == "contains":
            if f.value in text or (static and f.value in static):
                return f
        elif f.kind == "regexp":
            try:
                if re.match(f.value, static or text):
                    return f
            except re.error:
                continue
    return None


def _filter_used(f: HandlerFilter, buttons: list[ButtonData]) -> bool:
    for b in buttons:
        if f.kind == "eq" and not b.is_dynamic and b.pattern == f.value:
            return True
        if f.kind == "prefix" and (b.pattern.startswith(f.value) or f.value.startswith(b.literal_prefix) and b.literal_prefix):
            return True
        if f.kind in ("contains", "regexp", "unknown"):
            return True
    return False


def build_report() -> Report:
    report = Report()
    trees: dict[str, ast.AST] = {}
    for path in _iter_py_files():
        trees[str(path)] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    param_values, called_funcs = collect_param_values(trees)

    for path_str, tree in trees.items():
        path = Path(path_str)
        ButtonVisitor(path, report, param_values, called_funcs).visit(tree)
        HandlerVisitor(path, report).visit(tree)

    # Buttons that are pure navigation placeholders never need a handler.
    ignore = {"noop", "action:noop"}
    for b in report.buttons:
        if b.pattern in ignore:
            continue
        if _matches(b, report.filters) is None:
            report.orphan_buttons.append(b)
        if b.worst_case_len > CALLBACK_DATA_LIMIT and not b.safe_builder:
            report.oversized.append(b)

    for f in report.filters:
        if not _filter_used(f, report.buttons):
            report.unused_filters.append(f)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build_report()
    if args.json:
        print(
            json.dumps(
                {
                    "buttons": len(rep.buttons),
                    "filters": len(rep.filters),
                    "orphan_buttons": [vars(b) for b in rep.orphan_buttons],
                    "oversized": [vars(b) for b in rep.oversized],
                    "unused_filters": [vars(f) for f in rep.unused_filters],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"scanned buttons : {len(rep.buttons)}")
        print(f"callback filters: {len(rep.filters)}")
        print()
        print(f"❌ orphan buttons (no handler matches): {len(rep.orphan_buttons)}")
        for b in rep.orphan_buttons:
            print(f"   {b.file}:{b.line}  {b.pattern}")
        print()
        print(f"❌ oversized callback_data (>{CALLBACK_DATA_LIMIT} bytes): {len(rep.oversized)}")
        for b in rep.oversized:
            print(f"   {b.file}:{b.line}  len~{b.worst_case_len}  {b.pattern}")
        print()
        print(f"ℹ️  buttons in keyboard builders nobody calls: {len(rep.unreachable_buttons)}")
        for entry in rep.unreachable_buttons:
            print(f"   {entry}")
        print()
        print(f"⚠️  filters with no button emitting them: {len(rep.unused_filters)}")
        for f in rep.unused_filters:
            print(f"   {f.file}:{f.line}  [{f.kind}] {f.value}  ({f.func})")

    return 1 if (rep.orphan_buttons or rep.oversized) else 0


if __name__ == "__main__":
    sys.exit(main())
