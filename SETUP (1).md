# Setup & Getting Real Liberty Data

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Getting Sky130 (primary library)

```bash
git clone https://github.com/kunalg123/sky130RTLDesignAndSynthesisWorkshop.git
```
Liberty file: `sky130RTLDesignAndSynthesisWorkshop/lib/sky130_fd_sc_hd__tt_025C_1v80.lib`

`tt_025C_1v80` = typical-typical process corner, 25°C, 1.8V.

## Getting NanGate45, GF180MCU, Sky130HD, and IHP SG13G2

All four are bundled in one repo (`OpenROAD-flow-scripts`) as part of
OpenROAD's reference flow. The full repo is large (it vendors entire tool
builds), so use a sparse checkout to grab only the Liberty files:

```bash
git clone --filter=blob:none --sparse https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git
cd OpenROAD-flow-scripts
git sparse-checkout set flow/platforms
```

This gives you, under `flow/platforms/`:
- `nangate45/lib/*.lib` — NanGate45 / FreePDK45 (plain text)
- `gf180/lib/*.lib` — GF180MCU
- `sky130hd/lib/*.lib` — a second, independently-characterized Sky130 export
- `ihp-sg13g2/lib/*.lib` — IHP SG13G2
- `asap7/lib/*.lib.gz` — ASAP7 (**gzipped** — extract with `gunzip` or
  Python's `gzip.open(path, "rt")` before parsing)

Alternative, smaller clone covering NanGate45 + ASAP7 + a Sky130HD copy:
```bash
git clone https://github.com/TILOS-AI-Institute/MacroPlacement.git
```
Files land under `MacroPlacement/Enablements/<NanGate45|ASAP7|SKY130HD>/lib/`.

## Run against real data

```bash
python cli.py path/to/file.lib --pin Y --related A --slew 0.1 --load 0.01 --csv exports/test.csv
streamlit run app.py
# upload the same file from the sidebar
```

## Debugging a new library that doesn't parse cleanly

If a cell shows unexpected results (missing output pins, wrong delay
values, or a crash), inspect its raw parsed structure directly:

```bash
python debug_cell.py path/to/file.lib <cell_name>
```

This prints exactly what the parser captured for every pin on that cell —
attributes, complex attributes, and timing-arc counts — which is how both
known bugs (below) were originally diagnosed.

## Known vendor quirks already handled

- **Quoted attribute values** (Sky130) — `direction : "output";` rather than
  unquoted — handled by stripping quotes at the point of use.
- **Mismatched LUT dimensions** (GF180MCU, Sky130HD, IHP SG13G2) — declared
  `index_1`/`index_2` breakpoint counts not exactly matching the `values()`
  matrix — handled by clamping interpolation to actual matrix bounds, with
  a `NaN` fallback for any table too malformed even for that.

## Verified result

Parsing `sky130_fd_sc_hd__tt_025C_1v80.lib` (428 cells) produced 59 valid
timing-arc rows on the `Y` output pin alone, with delay correctly decreasing
as drive strength increases (`inv_1` > `inv_2` > `inv_4`, etc.). The same
parser and dashboard have since been run cleanly, end-to-end (including
full CSV export), against NanGate45, GF180MCU, Sky130HD, and IHP SG13G2 as
well.
