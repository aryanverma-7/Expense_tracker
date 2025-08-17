# app.py
"""
Cash Expense Tracker - Streamlit app (extended)
This file is a single combined Streamlit application that:
- Provides 30 predefined categories for quick selection
- Keeps Type selection as "In" and "Out"
- Supports CSV/XLSX upload and manual entry
- Provides Daily / Weekly / Monthly summary reports
- Shows Balance trend (In, Out, Balance) over selected period
- Shows Category Breakdown as a PIE chart (Outflows)
- Shows Expense Structure as a PIE chart (In vs Out and cat breakdown)
- Allows exporting filtered/full data to CSV/Excel
- Generates a simple PDF summary (if fpdf installed)
- Uses matplotlib for plotting (no explicit colors set)
- Structured and commented for clarity

Requirements:
pip install streamlit pandas matplotlib openpyxl fpdf
Run:
streamlit run app.py
"""

# -------------------------
# Imports & Configuration
# -------------------------
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, date, timedelta
from collections import OrderedDict

# Optional PDF support
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except Exception:
    FPDF_AVAILABLE = False

# Page configuration
st.set_page_config(page_title="Cash Expense Tracker (Extended)", layout="wide")

# -------------------------
# Constants & Predefined Lists
# -------------------------

# 30 predefined categories (user requested)
PREDEFINED_CATEGORIES = [
    "Salary", "Business Income", "Gift", "Interest", "Rent Income",
    "Groceries", "Transport", "Rent", "Utilities", "Dining Out",
    "Entertainment", "Healthcare", "Insurance", "Education", "Travel",
    "Shopping", "Electronics", "EMI/Loan", "Subscriptions", "Stationery",
    "Maintenance", "Fuel", "Clothing", "Household", "Tax",
    "Investment", "Savings", "Charity", "Pets", "Misc"
]

# Supported file extensions for upload
ALLOWED_FILE_TYPES = ["csv", "xlsx", "xls"]

# -------------------------
# Helper Functions
# -------------------------

@st.cache_data
def load_sample_data():
    """
    Returns a sample DataFrame populated across many categories and dates.
    This helps the app not appear empty and demonstrates charts.
    """
    sample_rows = [
        # Inflows
        {"Date": "2025-08-01", "Type": "In",  "Category": "Salary", "Amount": 40000.00, "Description": "Monthly salary"},
        {"Date": "2025-08-03", "Type": "In",  "Category": "Gift", "Amount": 2000.00, "Description": "Birthday gift"},
        {"Date": "2025-08-10", "Type": "In",  "Category": "Interest", "Amount": 150.00, "Description": "Bank interest"},
        {"Date": "2025-07-25", "Type": "In",  "Category": "Business Income", "Amount": 8000.00, "Description": "Freelance"},
        {"Date": "2025-06-15", "Type": "In",  "Category": "Rent Income", "Amount": 5000.00, "Description": "Room rent"},
        {"Date": "2025-05-05", "Type": "In",  "Category": "Investment", "Amount": 1200.00, "Description": "Dividends"},
        # Outflows
        {"Date": "2025-08-02", "Type": "Out", "Category": "Groceries", "Amount": 1200.00, "Description": "Supermarket"},
        {"Date": "2025-08-02", "Type": "Out", "Category": "Transport", "Amount": 250.00, "Description": "Taxi"},
        {"Date": "2025-08-04", "Type": "Out", "Category": "Dining Out", "Amount": 800.00, "Description": "Dinner with friends"},
        {"Date": "2025-08-06", "Type": "Out", "Category": "Utilities", "Amount": 1500.00, "Description": "Electricity bill"},
        {"Date": "2025-08-07", "Type": "Out", "Category": "Rent", "Amount": 12000.00, "Description": "Monthly rent"},
        {"Date": "2025-08-09", "Type": "Out", "Category": "Entertainment", "Amount": 600.00, "Description": "Movie & snacks"},
        {"Date": "2025-08-11", "Type": "Out", "Category": "Healthcare", "Amount": 500.00, "Description": "Medicines"},
        {"Date": "2025-08-12", "Type": "Out", "Category": "Shopping", "Amount": 2700.00, "Description": "Clothes"},
        {"Date": "2025-08-13", "Type": "Out", "Category": "Fuel", "Amount": 1800.00, "Description": "Car fuel"},
        {"Date": "2025-07-20", "Type": "Out", "Category": "Education", "Amount": 2200.00, "Description": "Course fee"},
        {"Date": "2025-06-30", "Type": "Out", "Category": "Insurance", "Amount": 900.00, "Description": "Policy premium"},
        {"Date": "2025-05-18", "Type": "Out", "Category": "Maintenance", "Amount": 400.00, "Description": "AC repair"},
        {"Date": "2025-08-14", "Type": "Out", "Category": "Misc", "Amount": 120.00, "Description": "Stationery"}
    ]
    # Fill some more varied sample rows so charts look rich (mix categories)
    extra_dates = pd.date_range(start="2025-05-01", end="2025-08-14", freq="7D")
    extra = []
    for i, d in enumerate(extra_dates):
        cat = PREDEFINED_CATEGORIES[i % len(PREDEFINED_CATEGORIES)]
        t = "Out" if i % 3 != 0 else "In"
        amt = float((i + 1) * 123) if t == "Out" else float((i + 2) * 500)
        extra.append({"Date": d.strftime("%Y-%m-%d"), "Type": t, "Category": cat, "Amount": round(amt, 2), "Description": f"Sample {i}"})
    data = sample_rows + extra
    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df

def safe_read_file(uploaded_file):
    """
    Safely read CSV or Excel file and normalize to expected columns.
    Expected columns: Date, Type, Category, Amount, Description
    """
    try:
        name = uploaded_file.name.lower()
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return None

    # Normalize column names (case insensitive)
    df_columns = {c.lower(): c for c in df.columns}
    # Map to standard names if possible
    rename_map = {}
    for std in ["date", "type", "category", "amount", "description"]:
        if std in df_columns:
            rename_map[df_columns[std]] = std.capitalize()
    df = df.rename(columns=rename_map)

    # Ensure required cols
    required = {"Date", "Type", "Category", "Amount"}
    if not required.issubset(set(df.columns)):
        st.error(f"Uploaded file must contain columns: {required}. Found: {list(df.columns)}")
        return None

    # Parse Date column robustly
    try:
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
    except Exception:
        # try manual conversion
        df["Date"] = df["Date"].apply(lambda x: pd.to_datetime(str(x), errors="coerce")).dt.date

    # Ensure Amount numeric
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)

    # Standardize Type values to In/Out
    df["Type"] = df["Type"].astype(str).str.strip().str.capitalize()
    df.loc[~df["Type"].isin(["In", "Out"]), "Type"] = df.loc[~df["Type"].isin(["In", "Out"]), "Type"].apply(lambda x: "In" if "in" in str(x).lower() else "Out")
    return df[["Date", "Type", "Category", "Amount", "Description"]]

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        return output.getvalue()
    except Exception:
        # fallback to CSV bytes if excel writer not available
        return df_to_csv_bytes(df)

def build_pdf_summary(df: pd.DataFrame, totals: dict) -> bytes:
    """
    Build a simple PDF summary (totals + recent transactions).
    Requires fpdf library.
    """
    if not FPDF_AVAILABLE:
        raise RuntimeError("FPDF not installed. Install using: pip install fpdf")
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Cash Expense Tracker - Summary", ln=True, align="C")
    pdf.ln(6)
    pdf.set_font("Arial", size=12)
    pdf.cell(60, 8, f"Total In: ₹{totals.get('total_in', 0.0):,.2f}")
    pdf.ln(6)
    pdf.cell(60, 8, f"Total Out: ₹{totals.get('total_out', 0.0):,.2f}")
    pdf.ln(6)
    pdf.cell(60, 8, f"Balance: ₹{totals.get('balance', 0.0):,.2f}")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Recent Transactions:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    # Table header
    header = ["Date", "Type", "Category", "Amount", "Description"]
    col_w = [28, 18, 40, 28, 80]
    for h, w in zip(header, col_w):
        pdf.cell(w, 7, h, border=1)
    pdf.ln()
    # Rows
    recent = df.sort_values("Date", ascending=False).head(10)
    for _, r in recent.iterrows():
        pdf.cell(col_w[0], 7, str(r.get("Date", "")), border=1)
        pdf.cell(col_w[1], 7, str(r.get("Type", "")), border=1)
        pdf.cell(col_w[2], 7, str(r.get("Category", ""))[:20], border=1)
        pdf.cell(col_w[3], 7, f"{r.get('Amount', 0.0):.2f}", border=1)
        pdf.cell(col_w[4], 7, str(r.get("Description", ""))[:35], border=1)
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1")

def ensure_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures DataFrame has all expected columns and correct dtypes.
    """
    if df is None:
        df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "Description"])
    for col in ["Date", "Type", "Category", "Amount", "Description"]:
        if col not in df.columns:
            if col == "Amount":
                df[col] = 0.0
            else:
                df[col] = ""
    # Date to date type
    try:
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
    except Exception:
        df["Date"] = pd.to_datetime(df["Date"].astype(str), errors="coerce").dt.date
    # Amount numeric
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    # Type normalization
    df["Type"] = df["Type"].astype(str).str.capitalize()
    df.loc[~df["Type"].isin(["In", "Out"]), "Type"] = df.loc[~df["Type"].isin(["In", "Out"]), "Type"].apply(lambda x: "In" if "in" in str(x).lower() else "Out")
    return df[["Date", "Type", "Category", "Amount", "Description"]]

# -------------------------
# UI: Header & Totals placeholders
# -------------------------

st.title("💸 Cash Expense Tracker (Extended)")
st.markdown("An extended version with 30 categories, daily/weekly/monthly reports, balance trend, and pie charts.")

# Placeholders for metrics (updated later)
metric_col1, metric_col2, metric_col3 = st.columns([1, 1, 1])
with metric_col1:
    placeholder_total_in = st.empty()
with metric_col2:
    placeholder_total_out = st.empty()
with metric_col3:
    placeholder_balance = st.empty()

st.markdown("---")

# -------------------------
# Left panel: Upload & Add Entry
# -------------------------

left, right = st.columns([2, 3])

with left:
    st.header("Import Data")
    st.write("Upload CSV or Excel with columns: Date, Type, Category, Amount, Description (Description optional).")
    uploaded = st.file_uploader("Upload CSV/XLSX", type=ALLOWED_FILE_TYPES, accept_multiple_files=False, key="uploader_ext")

    if uploaded is not None:
        df_uploaded = safe_read_file(uploaded)
        if df_uploaded is None:
            df = None
        else:
            df = ensure_df_columns(df_uploaded)
    else:
        # Start with sample data if no upload
        df = load_sample_data()

    st.markdown("### Add New Entry")
    with st.form("add_entry_form", clear_on_submit=True):
        new_date = st.date_input("Date", value=date.today())
        # Type split into In and Out
        new_type = st.radio("Type", options=["In", "Out"], index=1)
        # Category dropdown with 30 predefined categories + allow custom input
        cat_select = st.selectbox("Category (choose from list)", options=PREDEFINED_CATEGORIES, index=0)
        cat_custom = st.text_input("Or enter custom category (optional)", value="")
        new_category = cat_custom.strip() if cat_custom.strip() != "" else cat_select
        new_amount = st.number_input("Amount (₹)", min_value=0.0, format="%.2f", step=10.0)
        new_desc = st.text_area("Description (optional)", value="", height=40)
        add_submitted = st.form_submit_button("Add Entry")
        if add_submitted:
            new_row = {"Date": new_date, "Type": new_type, "Category": new_category, "Amount": float(new_amount), "Description": new_desc}
            if isinstance(df, pd.DataFrame):
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            else:
                df = pd.DataFrame([new_row])
            df = ensure_df_columns(df)
            st.success("Entry added successfully.")
            st.experimental_rerun()  # refresh UI to show new data immediately

    st.markdown("### Export / Tools")
    if isinstance(df, pd.DataFrame) and not df.empty:
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            st.download_button("Download Full CSV", data=df_to_csv_bytes(df), file_name="transactions_full.csv", mime="text/csv")
        with btn_col2:
            try:
                st.download_button("Download Full Excel", data=df_to_excel_bytes(df), file_name="transactions_full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.info("Excel export fallback used (CSV).")
        if FPDF_AVAILABLE:
            if st.button("Generate & Download PDF Summary"):
                totals_temp = {}
                totals_temp["total_in"] = float(df.loc[df["Type"] == "In", "Amount"].sum())
                totals_temp["total_out"] = float(df.loc[df["Type"] == "Out", "Amount"].sum())
                totals_temp["balance"] = totals_temp["total_in"] - totals_temp["total_out"]
                pdf_bytes = build_pdf_summary(df, totals_temp)
                st.download_button("Download PDF", data=pdf_bytes, file_name="summary.pdf", mime="application/pdf")
    else:
        st.info("No data available to export. Add entries or upload a file.")

# -------------------------
# Right panel: Viewing, Filters, Reports
# -------------------------
with right:
    st.header("View, Filter & Reports")

    # Ensure df valid
    if not isinstance(df, pd.DataFrame):
        st.warning("No data loaded. Upload or add entries to get started.")
        df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "Description"])
        df["Date"] = pd.to_datetime(df["Date"]).dt.date

    # Normalize
    df = ensure_df_columns(df)

    # Filters: search, type, date range
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        search_text = st.text_input("Search (Category or Description)", value="", key="search_ext")
    with filter_col2:
        type_filter = st.selectbox("Type Filter", options=["All", "In", "Out"], index=0)

    date_col1, date_col2 = st.columns(2)
    min_default = df["Date"].min() if not df.empty else date.today()
    max_default = df["Date"].max() if not df.empty else date.today()
    with date_col1:
        start_date = st.date_input("Start date", value=min_default, key="start_date_ext")
    with date_col2:
        end_date = st.date_input("End date", value=max_default, key="end_date_ext")

    # Report Frequency selection
    freq = st.radio("Report Frequency", options=["Daily", "Weekly", "Monthly"], index=2, horizontal=True)

    # Apply Filters
    filtered = df.copy()
    if search_text:
        mask = (
            filtered["Description"].fillna("").str.contains(search_text, case=False, na=False) |
            filtered["Category"].fillna("").str.contains(search_text, case=False, na=False)
        )
        filtered = filtered.loc[mask]
    if type_filter != "All":
        filtered = filtered.loc[filtered["Type"] == type_filter]
    try:
        filtered = filtered.loc[(filtered["Date"] >= start_date) & (filtered["Date"] <= end_date)]
    except Exception:
        # coerce dates just in case
        filtered["Date"] = pd.to_datetime(filtered["Date"]).dt.date
        filtered = filtered.loc[(filtered["Date"] >= start_date) & (filtered["Date"] <= end_date)]

    st.markdown(f"**Showing {len(filtered)} rows** (from {start_date} to {end_date})")
    st.dataframe(filtered.sort_values("Date", ascending=False).reset_index(drop=True), height=300)

    # Export filtered
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        st.download_button("Download Filtered CSV", data=df_to_csv_bytes(filtered), file_name="transactions_filtered.csv", mime="text/csv")
    with col_ex2:
        try:
            st.download_button("Download Filtered Excel", data=df_to_excel_bytes(filtered), file_name="transactions_filtered.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception:
            st.info("Excel export not available: fallback used.")

    st.markdown("---")

    # -------------------------
    # Aggregations: totals and reports
    # -------------------------
    total_in = float(filtered.loc[filtered["Type"] == "In", "Amount"].sum())
    total_out = float(filtered.loc[filtered["Type"] == "Out", "Amount"].sum())
    balance_val = total_in - total_out

    placeholder_total_in.metric("Total In", f"₹{total_in:,.2f}")
    placeholder_total_out.metric("Total Out", f"₹{total_out:,.2f}")
    placeholder_balance.metric("Balance", f"₹{balance_val:,.2f}")

    # Periodic report summary (Daily/Weekly/Monthly)
    st.subheader(f"{freq} Summary")
    if filtered.empty:
        st.info("No transactions in the selected range to summarize.")
    else:
        temp = filtered.copy()
        temp["Date_dt"] = pd.to_datetime(temp["Date"])
        if freq == "Daily":
            temp["Period"] = temp["Date_dt"].dt.date
        elif freq == "Weekly":
            # week label: Year-WeekNum
            temp["Period"] = temp["Date_dt"].dt.strftime("%Y-W%U")
        else:
            temp["Period"] = temp["Date_dt"].dt.to_period("M").astype(str)

        period_group = temp.groupby(["Period", "Type"], as_index=False)["Amount"].sum().pivot(index="Period", columns="Type", values="Amount").fillna(0.0)
        period_group["Net"] = period_group.get("In", 0.0) - period_group.get("Out", 0.0)
        period_group = period_group.reset_index().sort_values("Period", ascending=False)
        st.dataframe(period_group, height=220)

    st.markdown("---")

    # -------------------------
    # Balance Trend: plot In, Out and Balance over time
    # -------------------------
    st.subheader("Balance Trend Analysis")
    if filtered.empty:
        st.info("No data available to plot trend.")
    else:
        trend_df = filtered.copy()
        trend_df["Date_dt"] = pd.to_datetime(trend_df["Date"])
        # Resample daily to fill missing dates in the selected range for smoother trend
        idx = pd.date_range(start=start_date, end=end_date, freq="D")
        daily = trend_df.groupby([pd.Grouper(key="Date_dt", freq="D"), "Type"])["Amount"].sum().unstack(fill_value=0.0)
        daily = daily.reindex(idx, fill_value=0.0)
        # Ensure both columns exist
        if "In" not in daily.columns:
            daily["In"] = 0.0
        if "Out" not in daily.columns:
            daily["Out"] = 0.0
        daily = daily.sort_index()
        daily["Balance_Cumulative"] = (daily["In"] - daily["Out"]).cumsum()
        # Plot using matplotlib (single plot with two bars/lines)
        fig_trend, ax = plt.subplots(figsize=(10, 4))
        # Plot stacked area for In and Out (Out as positive area but we'll show Out separately)
        ax.plot(daily.index, daily["In"], label="In (Daily)", linewidth=1.5)
        ax.plot(daily.index, daily["Out"], label="Out (Daily)", linewidth=1.5)
        ax.plot(daily.index, daily["Balance_Cumulative"], label="Cumulative Balance", linewidth=2.0)
        ax.set_xlabel("Date")
        ax.set_ylabel("Amount (₹)")
        ax.legend()
        plt.tight_layout()
        st.pyplot(fig_trend)

    st.markdown("---")

    # -------------------------
    # Category Breakdown (Outflow) - PIE chart
    # -------------------------
    st.subheader("Category Breakdown (Outflow) - Pie Chart")
    outflows = filtered.loc[filtered["Type"] == "Out"]
    if outflows.empty:
        st.info("No outflows to show category breakdown.")
    else:
        cat_sum = outflows.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        # If too many small categories, group them into 'Others'
        if len(cat_sum) > 12:
            top = cat_sum.head(11)
            others = cat_sum.iloc[11:].sum()
            top["Others"] = others
            cat_sum_plot = top
        else:
            cat_sum_plot = cat_sum

        fig_pie1, ax1 = plt.subplots(figsize=(6, 6))
        ax1.pie(cat_sum_plot.values, labels=cat_sum_plot.index, autopct="%1.1f%%", startangle=90)
        ax1.axis("equal")
        st.pyplot(fig_pie1)

    st.markdown("---")

    # -------------------------
    # Expense Structure: Pie charts for overall composition
    # -------------------------
    st.subheader("Expense Structure (In vs Out & Category Composition)")

    # Pie 1: In vs Out
    comp = pd.Series({"In": filtered.loc[filtered["Type"] == "In", "Amount"].sum(),
                      "Out": filtered.loc[filtered["Type"] == "Out", "Amount"].sum()})
    fig_comp1, axc1 = plt.subplots(figsize=(5, 5))
    axc1.pie(comp.values, labels=comp.index, autopct="%1.1f%%", startangle=90)
    axc1.axis("equal")
    st.markdown("**Overall Composition: In vs Out**")
    st.pyplot(fig_comp1)

    # Pie 2: Expense category composition across both In and Out (or only Out if requested)
    # We show combined structure where In categories and Out categories both appear but segregated by Type
    st.markdown("**Detailed Category Composition (both In & Out combined)**")
    combined_cat = filtered.groupby(["Category"])["Amount"].sum().sort_values(ascending=False)
    if combined_cat.empty:
        st.info("No data to show detailed category composition.")
    else:
        # Aggregate small categories into Others if too many
        if len(combined_cat) > 12:
            topc = combined_cat.head(11)
            other_sum = combined_cat.iloc[11:].sum()
            topc["Others"] = other_sum
            combined_plot = topc
        else:
            combined_plot = combined_cat

        fig_pie2, axp2 = plt.subplots(figsize=(6, 6))
        axp2.pie(combined_plot.values, labels=combined_plot.index, autopct="%1.1f%%", startangle=90)
        axp2.axis("equal")
        st.pyplot(fig_pie2)

    st.markdown("---")

    # -------------------------
    # Expense Summary Table and insights
    # -------------------------
    st.subheader("Quick Insights & Top Categories")
    if filtered.empty:
        st.info("No quick insights available (no data).")
    else:
        top_spending = outflows.groupby("Category")["Amount"].sum().sort_values(ascending=False).head(5)
        st.markdown("**Top 5 Outflow Categories**")
        st.table(top_spending.reset_index().rename(columns={"Amount": "Total Out (₹)"}))

        st.markdown("**Net movement**")
        net_df = pd.DataFrame({
            "Metric": ["Total In", "Total Out", "Balance"],
            "Amount (₹)": [total_in, total_out, balance_val]
        })
        st.table(net_df)

# -------------------------
# Footer and Notes
# -------------------------
st.markdown("---")
st.caption("Extended Cash Expense Tracker — 30 categories | In/Out split | Daily/Weekly/Monthly reports | Balance trend | Pie charts for breakdowns")

# End of file