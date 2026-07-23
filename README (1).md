# Sky130 Liberty File Analyzer & Cell Visualizer

A from-scratch parser and interactive visualizer for **Liberty (`.lib`) timing
files** — the industry-standard format read by PrimeTime, Tempus, and OpenSTA
— built and verified against the open-source **Sky130 PDK**.

> ✅ **Verified against real foundry data.** Successfully parsed
> `sky130_fd_sc_hd__tt_025C_1v80.lib` (428 standard cells) and extracted
> 59 rise/fall timing arcs with correct delay values, cross-checked against
> the expected drive-strength trend (INVX1 > INVX2 > INVX4 delay, as it
> should be).

## What this demonstrates

- **Understanding of the Liberty format** — not just using a tool that reads
  `.lib` files, but knowing what's structurally inside them: nested
  `group(args) { attr : value; }` syntax, `lu_table_template` definitions,
  and per-arc `cell_rise` / `cell_fall` / `rise_transition` / `fall_transition`
  lookup tables indexed by input slew and output load.
- **STA fundamentals** — bilinear interpolation over a 2D delay LUT is
  exactly how real timing tools compute delay for slew/load values that
  fall between characterized grid points.
- **Sky130 cell library conventions** — drive-strength naming (`_1`, `_2`,
  `_4`...), PVT corner naming (`tt_025C_1v80` = typical-typical, 25°C, 1.8V),
  and how delay scales with drive strength.
- **End-to-end tool building** — parser → data model → CLI → interactive
  dashboard → CSV export, each layer independently testable.

## Architecture

```
parser/
├── liberty_parser.py   # Recursive-descent parser for Liberty's grammar.
│                       # No external dependency (no pip liberty-parser) —
│                       # written from first principles so it's fully
│                       # explainable: strips comments, tracks brace/paren
│                       # depth and quoted strings, classifies each token as
│                       # a group, a complex attribute (e.g. index_1(...);),
│                       # or a simple attribute (name : value;).
└── timing_model.py     # Builds Cell → Pin → TimingArc → LutTable objects
                         # from the raw parse tree, and implements bilinear
                         # interpolation over the slew/load grid.
app.py                  # Streamlit dashboard: heatmaps, drive-strength
                         # comparison, CSV export.
cli.py                  # Terminal version — same analysis, scriptable.
```

## Sample output (real Sky130 data)

```
Cell: sky130_fd_sc_hd__inv_1  |  Rise Delay at (slew=0.1ns, load=0.01pF) = 0.103ns
Cell: sky130_fd_sc_hd__inv_2  |  Rise Delay at (slew=0.1ns, load=0.01pF) = 0.076ns
Cell: sky130_fd_sc_hd__inv_4  |  Rise Delay at (slew=0.1ns, load=0.01pF) = 0.056ns
```

## Dashboard

*(screenshot placeholder — see `screenshots/` folder)*

The Streamlit app lets you pick any cell family, output pin, and timing arc,
then explore:
- **Delay/transition heatmaps** across the full slew × load grid
- **Drive-strength comparison** — auto-grouped cell families (`inv`, `buf`,
  `nand2`, etc.) plotted side by side at any chosen operating point
- **CSV export** of the full parsed summary

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py          # interactive dashboard
python cli.py <file.lib> --pin Y --related A --slew 0.1 --load 0.01
```

For instructions on downloading real Sky130 Liberty files, see
[`SETUP.md`](SETUP.md).

## Tech stack

Python · Streamlit · Plotly · Pandas — no proprietary EDA tool, no paid
license, fully reproducible with public data.

## License

MIT — see [`LICENSE`](LICENSE).
