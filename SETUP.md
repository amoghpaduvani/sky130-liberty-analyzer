# Setup & Getting Real Sky130 Data

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Getting real Sky130 Liberty files

The easiest source of ready-to-use, plain-text `.lib` files (the same ones
used across most open-source Sky130 workshops, and what this project was
verified against) is:

```bash
git clone https://github.com/kunalg123/sky130RTLDesignAndSynthesisWorkshop.git
```

The Liberty file lands at:
```
sky130RTLDesignAndSynthesisWorkshop/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
```

`tt_025C_1v80` = typical-typical process corner, 25°C, 1.8V — a good default
to explore.

Alternative source (per-cell JSON format, not plain-text `.lib` — needs
foundry install tooling to merge into a full library file):
```bash
git clone https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd.git
```

## Run against real data

```bash
python cli.py path/to/sky130_fd_sc_hd__tt_025C_1v80.lib \
  --pin Y --related A --slew 0.1 --load 0.01 --csv exports/real_test.csv

streamlit run app.py
# then upload the same .lib file from the sidebar
```

## Verified result

Parsing `sky130_fd_sc_hd__tt_025C_1v80.lib` (428 cells) produced 59 valid
timing-arc rows on the `Y` output pin alone, with delay correctly decreasing
as drive strength increases (`inv_1` > `inv_2` > `inv_4`, etc.) — confirming
both the parser and the interpolation logic are correct against real
foundry-characterized data.
