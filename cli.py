#!/usr/bin/env python3
"""
Command-line Liberty analyzer -- quick terminal demo / CSV export without the dashboard.

Usage:
    python cli.py path/to/file.lib --pin Y --related A --slew 0.1 --load 0.01
    python cli.py path/to/file.lib --csv out.csv
"""
import argparse
import csv
import sys

from parser.timing_model import load_liberty_library


def main():
    ap = argparse.ArgumentParser(description="Sky130 / Liberty timing analyzer (CLI)")
    ap.add_argument("lib_file", help="Path to a .lib Liberty file")
    ap.add_argument("--pin", default="Y", help="Output pin name to report (default: Y)")
    ap.add_argument("--related", default=None, help="Related (input) pin filter, e.g. A")
    ap.add_argument("--slew", type=float, default=0.1, help="Input slew in ns (default 0.1)")
    ap.add_argument("--load", type=float, default=0.01, help="Output load in pF (default 0.01)")
    ap.add_argument("--csv", default=None, help="Write full summary CSV to this path")
    args = ap.parse_args()

    lib = load_liberty_library(args.lib_file)
    print(f"Parsed library: {lib.name}  (corner: {lib.corner or 'unknown'})")
    print(f"Cells found: {len(lib.cells)}\n")

    rows = []
    for fam, cells in sorted(lib.families().items()):
        for cell in cells:
            if args.pin not in cell.pins:
                continue
            pin = cell.pins[args.pin]
            for arc in pin.timing_arcs:
                if args.related and arc.related_pin != args.related:
                    continue
                rise = arc.cell_rise.interpolate(args.slew, args.load) if arc.cell_rise else None
                fall = arc.cell_fall.interpolate(args.slew, args.load) if arc.cell_fall else None

                if rise is not None:
                    print(f"Cell: {cell.name:32s} |  Rise Delay at "
                          f"(slew={args.slew}ns, load={args.load}pF) = {rise:.3f}ns")
                if fall is not None:
                    print(f"Cell: {cell.name:32s} |  Fall Delay at "
                          f"(slew={args.slew}ns, load={args.load}pF) = {fall:.3f}ns")

                rows.append({
                    "family": fam, "cell": cell.name, "drive_strength": cell.drive_strength,
                    "area": cell.area, "output_pin": args.pin, "related_pin": arc.related_pin,
                    "slew_ns": args.slew, "load_pF": args.load,
                    "rise_delay_ns": rise, "fall_delay_ns": fall,
                })

    if args.csv and rows:
        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nWrote {len(rows)} rows to {args.csv}")


if __name__ == "__main__":
    sys.exit(main())
