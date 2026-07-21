"""
Liberty (.lib) timing file parser.

Liberty is a nested group-attribute format used industry-wide by every STA tool
(PrimeTime, Tempus, OpenSTA, etc). This parser implements a small recursive-descent
parser over the group/attribute grammar:

    group_name (arg1, arg2) {
        simple_attr : value ;
        complex_attr (arg) ;                 # e.g. index_1("0.01,0.02,...");
        nested_group (args) { ... }
    }

No external dependencies -- pure Python, so it's easy to read, easy to extend,
and easy to explain in an interview.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import re


# --------------------------------------------------------------------------- #
# AST node
# --------------------------------------------------------------------------- #

@dataclass
class LibGroup:
    """A single Liberty group, e.g. `cell (...)  { ... }`."""
    kind: str                                   # 'cell', 'pin', 'timing', 'library', ...
    args: list[str] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)      # simple_attr : value;
    complex_attrs: dict[str, list[str]] = field(default_factory=dict)  # name(args);
    children: list["LibGroup"] = field(default_factory=list)

    def get_children(self, kind: str) -> list["LibGroup"]:
        return [c for c in self.children if c.kind == kind]

    def get_child(self, kind: str) -> Optional["LibGroup"]:
        matches = self.get_children(kind)
        return matches[0] if matches else None

    @property
    def name(self) -> str:
        """Most groups (cell, pin, lu_table_template...) name themselves via args[0]."""
        return self.args[0] if self.args else ""


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./]*")


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def _find_matching(text: str, open_idx: int, open_ch: str, close_ch: str) -> int:
    """Return index of the char that matches text[open_idx], respecting quoted strings."""
    depth = 0
    in_str = False
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            in_str = not in_str
        elif not in_str:
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError(f"Unbalanced '{open_ch}{close_ch}' starting at {open_idx}")


def _split_args(args_str: str) -> list[str]:
    args_str = args_str.strip()
    if not args_str:
        return []
    # args are usually comma separated, possibly quoted
    parts = re.split(r",\s*", args_str)
    return [p.strip().strip('"') for p in parts if p.strip()]


def _find_semicolon(text: str, start: int) -> int:
    """Find ';' at depth 0 outside quotes, starting from `start`."""
    depth = 0
    in_str = False
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            in_str = not in_str
        elif not in_str:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == ";" and depth == 0:
                return i
        i += 1
    return -1


def _parse_body(text: str) -> tuple[dict, dict, list]:
    """Parse the interior of a group. Returns (attrs, complex_attrs, children)."""
    attrs: dict[str, str] = {}
    complex_attrs: dict[str, list[str]] = {}
    children: list[LibGroup] = []

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        m = _IDENT_RE.match(text, i)
        if not m:
            i += 1
            continue

        ident = m.group(0)
        j = m.end()
        # skip whitespace after identifier
        while j < n and text[j].isspace():
            j += 1

        if j < n and text[j] == "(":
            close_paren = _find_matching(text, j, "(", ")")
            args_str = text[j + 1:close_paren]
            k = close_paren + 1
            while k < n and text[k].isspace():
                k += 1

            if k < n and text[k] == "{":
                close_brace = _find_matching(text, k, "{", "}")
                body_text = text[k + 1:close_brace]
                sub_attrs, sub_complex, sub_children = _parse_body(body_text)
                group = LibGroup(
                    kind=ident,
                    args=_split_args(args_str),
                    attrs=sub_attrs,
                    complex_attrs=sub_complex,
                    children=sub_children,
                )
                children.append(group)
                i = close_brace + 1
            else:
                # complex attribute e.g. index_1("0.01,0.02"); or values("..","..");
                semi = _find_semicolon(text, k)
                if semi == -1:
                    i = k
                    continue
                complex_attrs.setdefault(ident, []).append(args_str)
                i = semi + 1
        elif j < n and text[j] == ":":
            semi = _find_semicolon(text, j + 1)
            if semi == -1:
                i = j + 1
                continue
            value = text[j + 1:semi].strip()
            attrs[ident] = value
            i = semi + 1
        else:
            i = j

    return attrs, complex_attrs, children


def parse_liberty(text: str) -> LibGroup:
    """Parse a full .lib file's text into a tree rooted at the `library` group."""
    text = _strip_comments(text)
    attrs, complex_attrs, children = _parse_body(text)

    if children and children[0].kind == "library":
        return children[0]

    # Fallback: wrap whatever we found
    return LibGroup(kind="library", args=["unknown"], attrs=attrs,
                     complex_attrs=complex_attrs, children=children)


def parse_liberty_file(path: str) -> LibGroup:
    with open(path, "r", errors="ignore") as f:
        text = f.read()
    return parse_liberty(text)
