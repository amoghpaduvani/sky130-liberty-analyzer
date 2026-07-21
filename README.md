# Sky130 Liberty File Analyzer & Cell Visualizer

Parses real `.lib` **Liberty** timing files (the standard format read by
PrimeTime, Tempus, and OpenSTA) from the open-source **Sky130 PDK** and
visualizes standard-cell timing: delay LUTs, drive-strength comparisons,
and rise/fall transition arcs — no proprietary EDA tool required.

## Why this project

- Liberty (`.lib`) is the universal timing-model format used by every STA
  tool on earth. Understanding what's inside it (lookup tables indexed by
  input slew and output load, indexed by drive strength) is core STA/PD
  knowledge.
- Sky130 is a fully open, freely downloadable PDK — everything here can be
  demoed live with public data, no NDA, no tool license.
- The parser is written from scratch (no `liberty-parser` pip package) so
  it's fully explainable in an interview: it's a small recursive-descent
  parser over Liberty's `group (args) { attr : value; }` grammar.

## Project layout

```
sky130-liberty-analyzer/
├── parser/
│   ├── liberty_parser.py   # low-level recursive-descent Liberty grammar parser
│   └── timing_model.py     # Cell/Pin/TimingArc objects + bilinear LUT interpolation
├── app.py                  # Streamlit interactive dashboard
├── cli.py                  # command-line version (prints the demo-style output, CSV export)
├── sample_data/
│   └── synthetic_test.lib  # small synthetic file (Sky130-structured) for a quick self-test
├── requirements.txt
└── README.md
```

## Getting the real Sky130 Liberty files

The dashboard works with the synthetic sample out of the box, but for a
real resume-worthy demo you want actual foundry-characterized data. Two
ways to get it:

**Option A — smallest download (recommended), just the standard-cell timing repo:**
```bash
git clone https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd.git
# Liberty files are under: skywater-pdk-libs-sky130_fd_sc_hd/timing/*.lib
```

**Option B — full PDK (much larger, only needed if you want LEF/GDS too):**
```bash
git clone https://github.com/google/skywater-pdk.git
cd skywater-pdk
git submodule update --init libraries/sky130_fd_sc_hd/latest
# Liberty files land in: libraries/sky130_fd_sc_hd/latest/timing/*.lib
```

File naming tells you the PVT corner:
`sky130_fd_sc_hd__<process>_<temp>_<voltage>.lib`
e.g. `sky130_fd_sc_hd__tt_025C_1v80.lib` = typical-typical, 25°C, 1.8V.

Grab the `tt_025C_1v80.lib` (typical) file first — it's the most commonly
used corner and a good default to explore.

## Setup & run

```bash
pip install -r requirements.txt

# Interactive dashboard
streamlit run app.py
# then upload a real sky130_fd_sc_hd__*.lib file from the sidebar

# Or use the CLI
python cli.py path/to/sky130_fd_sc_hd__tt_025C_1v80.lib --pin Y --related A --slew 0.1 --load 0.01 --csv out.csv
```

## What it shows

- **Delay/transition heatmaps** — `cell_rise`, `cell_fall`, `rise_transition`,
  `fall_transition` lookup tables, indexed by input slew (rows) × output
  load (columns), exactly as stored in the Liberty file.
- **Bilinear interpolation** — pick any (slew, load) point (not just the
  characterized grid points) and get an interpolated delay, the same
  technique real STA tools use between LUT breakpoints.
- **Drive-strength comparison** — auto-groups cells into families by
  stripping the `_1/_2/_4/_8` suffix (Sky130's drive-strength naming
  convention) and plots delay side-by-side, e.g. INVX1 vs INVX2 vs INVX4.
- **CSV export** — full parsed summary (cell, drive strength, area, rise/fall
  delay at your chosen operating point) downloadable straight from the
  dashboard, or via `--csv` on the CLI.

## How the parser works (for your interview walkthrough)

Liberty is a nested `group (args) { ... }` / `attribute : value;` grammar.
`liberty_parser.py` implements this as:

1. Strip `/* */` comments.
2. Scan character-by-character tracking brace/paren depth and quoted
   strings (so commas/braces inside `"..."` values don't confuse the parser).
3. For each identifier found, decide if it's a **group** (followed by
   `(args) {`), a **complex attribute** (followed by `(args) ;`, e.g.
   `index_1("0.01,0.02");`), or a **simple attribute** (`name : value;`).
4. Recurse into `{ ... }` bodies to build a tree of `LibGroup` nodes.

`timing_model.py` then walks that generic tree and extracts the
domain-specific pieces (`Cell` → `Pin` → `TimingArc` → `LutTable`), and
implements standard bilinear interpolation over the 2D slew/load grid.

## Notes

- `sample_data/synthetic_test.lib` is a **hand-written, structurally
  accurate** Liberty snippet used only to verify the parser — it is *not*
  real Sky130 foundry data. Swap in real files from the links above before
  using this for anything resume/interview-facing.
- Tested against the standard `sky130_fd_sc_hd` (high-density) library
  format; other Sky130 flavors (`hs`, `ms`, `ls`, `lp`) and most other
  vendors' `.lib` files use the same grammar and should parse fine too.
