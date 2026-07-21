"""
Turns a raw LibGroup tree (from liberty_parser) into clean, queryable Python
objects: LutTable, TimingArc, Cell, LibertyLibrary.

Also implements bilinear interpolation over a 2D lookup table, which is
exactly how real STA tools compute delay for slew/load values that fall
between characterized index points.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re

from .liberty_parser import LibGroup, parse_liberty_file


def _parse_float_list(raw: str) -> list[float]:
    """Turn '"0.01, 0.02, 0.03"' style Liberty index/values text into floats."""
    cleaned = raw.replace('\\', ' ').replace('"', ' ')
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", cleaned)
    return [float(x) for x in nums]


@dataclass
class LutTable:
    """A 2D (or 1D) lookup table: rows indexed by slew (index_1), columns by load (index_2)."""
    index_1: list[float]           # input transition / slew (ns)
    index_2: list[float]           # output net capacitance / load (pF)
    values: list[list[float]]      # values[row][col], row->index_1, col->index_2

    def interpolate(self, slew: float, load: float) -> float:
        """Bilinear interpolation, clamped to table edges (same behavior as most STA tools
        outside the characterized range: use nearest edge instead of extrapolating wildly)."""
        return _bilinear(self.index_1, self.index_2, self.values, slew, load)


@dataclass
class TimingArc:
    related_pin: str
    timing_sense: str = ""             # positive_unate / negative_unate / non_unate
    cell_rise: LutTable | None = None
    cell_fall: LutTable | None = None
    rise_transition: LutTable | None = None
    fall_transition: LutTable | None = None


@dataclass
class Pin:
    name: str
    direction: str = ""
    capacitance: float | None = None
    function: str = ""
    timing_arcs: list[TimingArc] = field(default_factory=list)


@dataclass
class Cell:
    name: str
    area: float | None = None
    pins: dict[str, Pin] = field(default_factory=dict)

    @property
    def output_pins(self) -> list[Pin]:
        return [p for p in self.pins.values() if p.direction == "output"]

    @property
    def drive_strength(self) -> int | None:
        """Sky130 naming convention: sky130_fd_sc_hd__inv_2 -> drive strength 2."""
        m = re.search(r"_(\d+)$", self.name)
        return int(m.group(1)) if m else None

    @property
    def family(self) -> str:
        """Base logical function name with drive-strength suffix stripped,
        e.g. sky130_fd_sc_hd__inv_2 -> sky130_fd_sc_hd__inv"""
        return re.sub(r"_\d+$", "", self.name)


@dataclass
class LibertyLibrary:
    name: str
    corner: str = ""
    cells: dict[str, Cell] = field(default_factory=dict)

    def families(self) -> dict[str, list[Cell]]:
        """Group cells by family so drive strengths (X1/X2/X4...) can be compared."""
        out: dict[str, list[Cell]] = {}
        for c in self.cells.values():
            out.setdefault(c.family, []).append(c)
        for fam in out:
            out[fam].sort(key=lambda c: (c.drive_strength or 0))
        return out


# --------------------------------------------------------------------------- #
# Bilinear interpolation
# --------------------------------------------------------------------------- #

def _locate(axis: list[float], x: float) -> tuple[int, int, float]:
    """Find bracketing indices (lo, hi) and interpolation fraction t in axis for value x.
    Clamps to the ends of the axis rather than extrapolating."""
    if len(axis) == 1:
        return 0, 0, 0.0
    if x <= axis[0]:
        return 0, 1, 0.0
    if x >= axis[-1]:
        return len(axis) - 2, len(axis) - 1, 1.0
    for i in range(len(axis) - 1):
        if axis[i] <= x <= axis[i + 1]:
            span = axis[i + 1] - axis[i]
            t = (x - axis[i]) / span if span != 0 else 0.0
            return i, i + 1, t
    return len(axis) - 2, len(axis) - 1, 1.0


def _bilinear(rows: list[float], cols: list[float], grid: list[list[float]],
              row_x: float, col_x: float) -> float:
    r0, r1, tr = _locate(rows, row_x)
    c0, c1, tc = _locate(cols, col_x)

    v00 = grid[r0][c0]
    v01 = grid[r0][c1]
    v10 = grid[r1][c0]
    v11 = grid[r1][c1]

    top = v00 + (v01 - v00) * tc
    bot = v10 + (v11 - v10) * tc
    return top + (bot - top) * tr


# --------------------------------------------------------------------------- #
# Building the model from a parsed LibGroup tree
# --------------------------------------------------------------------------- #

def _build_lut(group: LibGroup) -> LutTable | None:
    idx1_raw = group.complex_attrs.get("index_1")
    idx2_raw = group.complex_attrs.get("index_2")
    vals_raw = group.complex_attrs.get("values")
    if not idx1_raw or not vals_raw:
        return None

    index_1 = _parse_float_list(idx1_raw[0])
    index_2 = _parse_float_list(idx2_raw[0]) if idx2_raw else index_1

    # `values` may be split across multiple quoted rows within one complex_attr entry,
    # or the parser may have captured them as one combined string with commas/newlines.
    raw_values_str = vals_raw[0]
    row_strs = re.findall(r'"([^"]*)"', raw_values_str)
    if not row_strs:
        row_strs = [raw_values_str]

    values: list[list[float]] = [_parse_float_list(row) for row in row_strs]
    values = [row for row in values if row]

    if not values:
        return None
    return LutTable(index_1=index_1, index_2=index_2, values=values)


def _build_pin(pin_group: LibGroup) -> Pin:
    pin = Pin(
        name=pin_group.name,
        direction=pin_group.attrs.get("direction", ""),
        function=pin_group.attrs.get("function", "").strip('"'),
    )
    cap_raw = pin_group.attrs.get("capacitance")
    if cap_raw:
        try:
            pin.capacitance = float(cap_raw)
        except ValueError:
            pass

    for timing_group in pin_group.get_children("timing"):
        arc = TimingArc(
            related_pin=timing_group.attrs.get("related_pin", "").strip('"'),
            timing_sense=timing_group.attrs.get("timing_sense", ""),
        )
        for lut_kind, attr_name in (
            ("cell_rise", "cell_rise"),
            ("cell_fall", "cell_fall"),
            ("rise_transition", "rise_transition"),
            ("fall_transition", "fall_transition"),
        ):
            sub = timing_group.get_child(lut_kind)
            if sub is not None:
                setattr(arc, attr_name, _build_lut(sub))
        pin.timing_arcs.append(arc)

    return pin


def build_library(root: LibGroup) -> LibertyLibrary:
    lib = LibertyLibrary(name=root.name)

    # corner is usually embedded in the library name, e.g. sky130_fd_sc_hd__tt_025C_1v80
    m = re.search(r"__(tt|ss|ff)_(\w+)_(\d+v\d+)", root.name)
    if m:
        lib.corner = f"{m.group(1)}_{m.group(2)}_{m.group(3)}"

    for cell_group in root.get_children("cell"):
        cell = Cell(name=cell_group.name)
        area_raw = cell_group.attrs.get("area")
        if area_raw:
            try:
                cell.area = float(area_raw)
            except ValueError:
                pass
        for pin_group in cell_group.get_children("pin"):
            pin = _build_pin(pin_group)
            cell.pins[pin.name] = pin
        lib.cells[cell.name] = cell

    return lib


def load_liberty_library(path: str) -> LibertyLibrary:
    root = parse_liberty_file(path)
    return build_library(root)
