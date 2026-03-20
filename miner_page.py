import streamlit as st

STRATEGY_OPTIONS = {"From Data": "DATA", "From Text": "TEXT"}

st.markdown(
    """
<style>
    [data-testid="stSidebar"] {
        background-color: var(--secondary-background-color) !important;
        border-right: 1px solid rgba(255, 75, 75, 0.3) !important;
    }
    [data-testid="stSidebar"] *, .stMarkdown, label p {
        color: var(--text-color) !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] > div:has(div[data-testid="stVerticalBlock"]) {
        border: 1px solid rgba(255, 75, 75, 0.2) !important;
        border-radius: 24px !important;
        padding: 40px !important;
        background: linear-gradient(160deg, rgba(26, 8, 8, 0.5) 0%, rgba(14, 17, 23, 0.5) 100%) !important;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3) !important;
        backdrop-filter: blur(10px);
    }

    [data-testid="stFileUploadDropzone"] {
        background-color: var(--background-color) !important;
        border: 2px dashed rgba(255, 75, 75, 0.4) !important;
        border-radius: 15px !important;
        transition: all 0.3s ease !important;
        padding: 20px !important;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #ff4b4b !important;
        background-color: rgba(255, 75, 75, 0.05) !important;
    }
    [data-testid="stFileUploadDropzone"] button {
        background-color: #ff4b4b !important;
        color: white !important;
        border-radius: 10px !important;
        border: none !important;
    }

    div.stButton > button {
        width: 100% !important;
        background: linear-gradient(90deg, #ff4b4b 0%, #ff7676 100%) !important;
        color: white !important;
        border-radius: 14px !important;
        height: 3.8em !important;
        font-size: 16px !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        border: none !important;
        box-shadow: 0 8px 25px rgba(255, 75, 75, 0.4) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    div.stButton > button:hover {
        box-shadow: 0 12px 35px rgba(255, 75, 75, 0.6) !important;
        background: linear-gradient(90deg, #ff5f5f 0%, #ff8f8f 100%) !important;
        transform: translateY(-2px) !important;
    }

    .workbench-header {
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin-bottom: 10px;
    }
    .upload-hint {
        font-size: 14px;
        color: #9ea4b0;
        margin-bottom: 25px;
    }
         .rule-header {
        font-weight: 800;
        text-transform: uppercase;
        font-size: 12px;
        letter-spacing: 1px;
        color: #9ea4b0;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(255, 75, 75, 0.2);
        margin-bottom: 15px;
    }

    /* Row Styling */
    .rule-row {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 8px;
        transition: all 0.2s ease;
    }

    .rule-row:hover {
        border-color: rgba(255, 75, 75, 0.3);
        background-color: rgba(255, 75, 75, 0.02);
    }

    /* Metric Badges */
    .metric-text {
        font-family: 'Courier New', monospace;
        font-weight: 700;
        color: #ff7676;
    }
    [data-testid="stCheckbox"] div[role="checkbox"] {
    background-color: #ff4b4b !important;
    border-color: #ff4b4b !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# --- 2. WORKSPACE PROTECTION ---
# Check if the user has configured the connection
if "selected_rules" not in st.session_state:
    st.session_state["selected_rules"] = set()
# --- 3. SIDEBAR STATUS ---
with st.sidebar:
    st.markdown("### ⚒️ WORKBENCH")
    st.caption("Active Session Control")
    st.divider()
    st.success("Credentials Provided")
    # st.markdown(f"**Provider:** {st.session_state['provider']}")
    # st.markdown(f"**Model:** {st.session_state['model_name']}")

    if st.button("Reset Session", type="secondary"):
        st.session_state.clear()
        st.rerun()

# --- 4. MAIN UI TABS ---
st.markdown(
    '<div class="workbench-header">⚒️ Miner Workbench</div>', unsafe_allow_html=True
)

tab1, tab2, tab3 = st.tabs(
    ["📥 Data Upload", "🔍 Rule Discovery", "🏗️ Process Discovery"]
)

# --- TAB 1: DATA UPLOAD ---
with tab1:
    st.write("")
    st.markdown("### 1. Import Event Log")
    st.markdown(
        '<p class="upload-hint">Upload XES or GZ files to let the agent begin rule extraction.</p>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        uploaded_log = st.file_uploader(
            "Upload log", type=["xes", "gz"], label_visibility="collapsed"
        )

        if uploaded_log:
            st.success(f"Log '{uploaded_log.name}' successfully loaded into memory!")

            # Action button only appears after upload
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("Initialize Analysis", use_container_width=True):
                    st.toast("...", icon="⚙️")
                    st.session_state["data_ready"] = True
        else:
            st.info("Waiting for data... Please drop an event log file above.")

# --- TAB 2: RULE DISCOVERY ---
mock_rules = [
    {"id": 1, "rule": "Existence(A)", "conf": 0.92, "supp": 0.15},
    {"id": 2, "rule": "AtMost1(B)", "conf": 0.88, "supp": 0.05},
    {"id": 3, "rule": "CoExistence(A,B)", "conf": 0.98, "supp": 0.22},
    {"id": 4, "rule": "Succession(A,B)", "conf": 0.85, "supp": 0.12},
]

with tab2:
    st.markdown("### 🔍 2. Rule Discovery Engine")

    # --- Settings Area ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 1])
        with c1:
            strategy = st.selectbox("Strategy", ["From Data", "From Text"])
        with c2:
            support_val = st.number_input("Min. Support", 0.0, 1.0, 0.10)
        with c3:
            conf_val = st.number_input("Min. Confidence", 0.0, 1.0, 0.80)

        if st.button("Discover Rules ⚡", use_container_width=True):
            st.session_state["discovery_done"] = True
            st.toast("Mining complete!", icon="✨")

    st.write("")  # Spacing

    # --- Results Area (The 4-Column Table) ---
    if st.session_state.get("discovery_done"):
        st.markdown("##### 📋 Discovered Rules")
        st.caption(
            "Select the rules you want to include in the Process Discovery stage."
        )

        # --- Header Row ---
        h1, h2, h3, h4 = st.columns([4, 1, 1, 1])
        h1.markdown('<div class="rule-header">Rule Logic</div>', unsafe_allow_html=True)
        h2.markdown('<div class="rule-header">Conf.</div>', unsafe_allow_html=True)
        h3.markdown('<div class="rule-header">Supp.</div>', unsafe_allow_html=True)
        h4.markdown('<div class="rule-header">Select</div>', unsafe_allow_html=True)

        # --- Data Rows ---
        for r in mock_rules:
            # Wrap each row in a clean container
            with st.container():
                r1, r2, r3, r4 = st.columns([4, 1, 1, 1])

                # Column 1: The Rule
                r1.markdown(f"**{r['rule']}**")

                # Column 2: Confidence
                r2.markdown(
                    f'<span class="metric-text">{r["conf"]:.2f}</span>',
                    unsafe_allow_html=True,
                )

                # Column 3: Support
                r3.markdown(
                    f'<span class="metric-text">{r["supp"]:.2f}</span>',
                    unsafe_allow_html=True,
                )

                # Column 4: The Tickbox (Select)
                # We use the rule ID as the key to track selection
                is_selected = r4.checkbox(
                    "Select", key=f"rule_{r['id']}", label_visibility="collapsed"
                )

                if is_selected:
                    st.session_state["selected_rules"].add(r["id"])
                else:
                    st.session_state["selected_rules"].discard(r["id"])

        # --- Bulk Action ---
        st.divider()
        col_left, col_right = st.columns([3, 1])
        with col_left:
            st.write(
                f"Items selected for Process Discovery: **{len(st.session_state['selected_rules'])}**"
            )
        with col_right:
            if st.button("Proceed to Stage 3 →", type="primary"):
                st.switch_page("miner_workbench.py")  # Or logic to switch tabs

    else:
        st.info("Run the discovery engine to view and select process rules.")
# --- TAB 3: PROCESS DISCOVERY ---
with tab3:
    if "data_ready" not in st.session_state or "analysis" not in st.session_state:
        st.warning("WIP.")
    else:
        st.markdown("### 3. Model Generation")
        st.caption("Convert discovered rules into a visual process model.")

        with st.container(border=True):
            st.info("Visualization engine is ready. Select format to generate model.")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.button("BPMN Model", use_container_width=True)
            with c2:
                st.button("Petri Net", use_container_width=True)
            with c3:
                st.button("Process Tree", use_container_width=True)

            st.divider()
            # Placeholder for the SVG output

st.divider()
