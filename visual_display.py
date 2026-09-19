from tests import events_df
import streamlit as st

st.title("Stock News Event Results")

percentage_columns = [
    "guidance_revision",
    "immediate_return",
    "1h_return",
    "1d_return",
    "3d_return",
    "immediate_adjusted",
    "1h_adjusted",
    "1d_adjusted",
    "3d_adjusted"
]

st.dataframe(
    events_df.style.format({
        col: "{:.2%}"
        for col in percentage_columns
    }),
    use_container_width=True
)