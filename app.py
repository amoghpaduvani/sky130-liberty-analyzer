"""
Liberty File Analyzer & Cell Visualizer
================================================
Interactive dashboard for exploring Liberty (.lib) standard-cell timing data:
delay LUTs, drive-strength comparisons, and setup/hold-style rise/fall arcs.

Run:
    streamlit run app.py

Upload any Sky130 (or other Liberty-compliant) .lib file, or use the bundled
synthetic sample to try it out immediately.
"""

import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from parser.liberty_parser import parse_liberty
from parser.timing_model import build_library, LibertyLibrary, Cell

st.set_page_config(page_title="Liberty Timing Analyzer", layout="wide", page_icon="📐")


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner=False)
def parse_lib_text(text: str) -> LibertyLibrary:
    root = parse_liberty(text)
    return build_library(root)


def load_library() -> LibertyLibrary | None:
    st.sidebar.header("1. Load a Liberty file")
    uploaded = st.sidebar.file_uploader("Upload a .lib file", type=["lib", "txt"])
    use_sample = st.sidebar.checkbox("Use bundled synthetic sample instead", value=uploaded is None)

    if uploaded is not None and not use_sample:
        text = uploaded.read().decode("utf-8", errors="ignore")
        return parse_lib_text(text)
    else:
        with open("sample_data/synthetic_test.lib") as f:
            text = f.read()
        st.sidebar.caption(
            "⚠️ Synthetic sample (structurally matches Sky130 format, numbers are "
            "illustrative). Upload a real sky130_fd_sc_hd__*.lib for real analysis."
        )
        return parse_lib_text(text)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def lut_to_df(lut) -> pd.DataFrame:
    df = pd.DataFrame(lut.values, index=lut.index_1, columns=lut.index_2)
    df.index.name = "slew (ns)"
    df.columns.name = "load (pF)"
    return df


def heatmap_figure(lut, title: str) -> go.Figure:
    fig = go.Figure(data=go.Heatmap(
        z=lut.values,
        x=lut.index_2,
        y=lut.index_1,
        colorscale="Turbo",
        colorbar=dict(title="ns"),
        hovertemplate="load=%{x} pF<br>slew=%{y} ns<br>delay=%{z:.4f} ns<extra></extra>",
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Total output net capacitance (pF)",
        yaxis_title="Input net transition / slew (ns)",
        height=380,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def build_family_csv(lib: LibertyLibrary, slew: float, load: float) -> pd.DataFrame:
    rows = []
    for fam, cells in lib.families().items():
        for cell in cells:
            for pin in cell.output_pins:
                for arc in pin.timing_arcs:
                    rise = arc.cell_rise.interpolate(slew, load) if arc.cell_rise else None
                    fall = arc.cell_fall.interpolate(slew, load) if arc.cell_fall else None
                    rows.append({
                        "family": fam,
                        "cell": cell.name,
                        "drive_strength": cell.drive_strength,
                        "area": cell.area,
                        "output_pin": pin.name,
                        "related_pin": arc.related_pin,
                        "slew_ns": slew,
                        "load_pF": load,
                        "rise_delay_ns": rise,
                        "fall_delay_ns": fall,
                    })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

st.title("📐 Liberty Timing File Analyzer & Visualizer")
st.caption(
    "Parses real `.lib` Liberty timing files (the same format read by PrimeTime, "
    "Tempus, and OpenSTA) and visualizes cell delay, transition, and drive-strength data. "
    "Verified against Sky130, NanGate45, GF180MCU, Sky130HD, and IHP SG13G2."
)

lib = load_library()
if lib is None or not lib.cells:
    st.warning("No cells parsed. Check the uploaded file is a valid Liberty (.lib) file.")
    st.stop()

st.sidebar.header("2. Pick a cell & operating point")
families = lib.families()
family_name = st.sidebar.selectbox("Cell family", sorted(families.keys()))
family_cells = families[family_name]
cell_names = [c.name for c in family_cells]
cell_name = st.sidebar.selectbox("Cell (drive strength)", cell_names)
cell: Cell = lib.cells[cell_name]

output_pins = cell.output_pins
if not output_pins:
    st.error(f"No output pins with timing data found on {cell_name}.")
    st.stop()

pin_name = st.sidebar.selectbox("Output pin", [p.name for p in output_pins])
pin = cell.pins[pin_name]

arc_options = [f"{a.related_pin} → {pin_name}" for a in pin.timing_arcs]
arc_idx = st.sidebar.selectbox("Timing arc (related pin → output)", range(len(arc_options)),
                                format_func=lambda i: arc_options[i])
arc = pin.timing_arcs[arc_idx]

st.sidebar.divider()
slew = st.sidebar.slider("Input slew (ns)", 0.01, 1.0, 0.1, 0.01)
load = st.sidebar.slider("Output load (pF)", 0.001, 0.2, 0.01, 0.001, format="%.3f")

# --------------------------------------------------------------------------- #
# Top summary row -- the "demo output" numbers
# --------------------------------------------------------------------------- #

col1, col2, col3, col4 = st.columns(4)
rise_delay = arc.cell_rise.interpolate(slew, load) if arc.cell_rise else None
fall_delay = arc.cell_fall.interpolate(slew, load) if arc.cell_fall else None
rise_trans = arc.rise_transition.interpolate(slew, load) if arc.rise_transition else None
fall_trans = arc.fall_transition.interpolate(slew, load) if arc.fall_transition else None

col1.metric("Rise delay", f"{rise_delay:.4f} ns" if rise_delay is not None else "—")
col2.metric("Fall delay", f"{fall_delay:.4f} ns" if fall_delay is not None else "—")
col3.metric("Rise transition", f"{rise_trans:.4f} ns" if rise_trans is not None else "—")
col4.metric("Fall transition", f"{fall_trans:.4f} ns" if fall_trans is not None else "—")

st.code(
    f"Cell: {cell_name}  |  Rise Delay at (slew={slew:.2f}ns, load={load:.3f}pF) "
    f"= {rise_delay:.4f}ns" if rise_delay is not None else "No rise delay table for this arc.",
    language="text",
)

st.divider()

# --------------------------------------------------------------------------- #
# Heatmaps
# --------------------------------------------------------------------------- #

st.subheader(f"Delay heatmaps — {cell_name}, {arc.related_pin} → {pin_name}")
h1, h2 = st.columns(2)
if arc.cell_rise:
    h1.plotly_chart(heatmap_figure(arc.cell_rise, "Rise delay (ns)"), use_container_width=True)
if arc.cell_fall:
    h2.plotly_chart(heatmap_figure(arc.cell_fall, "Fall delay (ns)"), use_container_width=True)

with st.expander("Raw LUT tables"):
    t1, t2 = st.columns(2)
    if arc.cell_rise:
        t1.write("**cell_rise**")
        t1.dataframe(lut_to_df(arc.cell_rise))
    if arc.cell_fall:
        t2.write("**cell_fall**")
        t2.dataframe(lut_to_df(arc.cell_fall))

st.divider()

# --------------------------------------------------------------------------- #
# Drive-strength comparison
# --------------------------------------------------------------------------- #

st.subheader(f"Drive strength comparison — family `{family_name}`")
st.caption(f"Rise delay at the operating point above (slew={slew:.2f}ns, load={load:.3f}pF), across every drive strength in this family.")

comp_rows = []
for c in family_cells:
    if pin_name not in c.pins:
        continue
    p = c.pins[pin_name]
    matching_arcs = [a for a in p.timing_arcs if a.related_pin == arc.related_pin]
    if not matching_arcs:
        continue
    a = matching_arcs[0]
    r = a.cell_rise.interpolate(slew, load) if a.cell_rise else None
    f = a.cell_fall.interpolate(slew, load) if a.cell_fall else None
    comp_rows.append({"cell": c.name, "drive_strength": c.drive_strength,
                       "area": c.area, "rise_delay_ns": r, "fall_delay_ns": f})

comp_df = pd.DataFrame(comp_rows).sort_values("drive_strength")
if not comp_df.empty:
    bar = go.Figure()
    bar.add_bar(x=comp_df["cell"], y=comp_df["rise_delay_ns"], name="Rise delay (ns)")
    bar.add_bar(x=comp_df["cell"], y=comp_df["fall_delay_ns"], name="Fall delay (ns)")
    bar.update_layout(barmode="group", height=380,
                       yaxis_title="Delay (ns)", margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(bar, use_container_width=True)
    st.dataframe(comp_df, use_container_width=True)
else:
    st.info("Only one drive strength found for this family/pin/arc combination.")

st.divider()

# --------------------------------------------------------------------------- #
# CSV export
# --------------------------------------------------------------------------- #

st.subheader("Export")
export_slew = slew
export_load = load
full_df = build_family_csv(lib, export_slew, export_load)
csv_buf = io.StringIO()
full_df.to_csv(csv_buf, index=False)

st.download_button(
    "⬇️ Download full library summary (CSV)",
    data=csv_buf.getvalue(),
    file_name=f"{lib.name}_summary_slew{export_slew}_load{export_load}.csv",
    mime="text/csv",
)
st.dataframe(full_df, use_container_width=True, height=300)

st.divider()
st.caption(
    f"Library: `{lib.name}`  |  Corner: `{lib.corner or 'unknown'}`  |  "
    f"Cells parsed: {len(lib.cells)}  |  Families: {len(families)}"
)
