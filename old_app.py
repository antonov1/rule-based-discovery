import streamlit as st
from promoai.general_utils.ai_providers import AI_HELP_DEFAULTS, AI_MODEL_DEFAULTS
from promoai.general_utils.llm_connection import LLMConnection

st.markdown(
    """
<style>
    /* 1. SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: var(--secondary-background-color) !important;
        border-right: 2px solid rgba(255, 75, 75, 0.4); /* Neon Red Accent Line */
        min-width: 350px !important;
    }

    /* 2. SIDEBAR HEADER */
    .sidebar-title {
        font-size: 22px;
        font-weight: 800;
        color: white;
        margin-bottom: 5px;
        letter-spacing: -0.5px;
    }

    /* 3. SLEEK INPUTS IN SIDEBAR */
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        color: var(--text-color) !important;
    }

    [data-testid="stSidebar"] label p {
        color: var(--text-color) !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 1px;
    }

    /* 4. YOUR FAVORITE RED GLOW BUTTON (Sidebar Fit) */
    div.stButton {
        width: 100% !important;
        margin-top: 20px;
    }

    div.stButton > button {
        width: 100% !important;
        background: linear-gradient(90deg, #ff4b4b 0%, #ff7676 100%) !important;
        color: white !important;
        border-radius: 14px !important;
        height: 3.8em !important;
        font-size: 14px !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        border: none !important;
        box-shadow: 0 8px 25px rgba(255, 75, 75, 0.4) !important;
        transition: all 0.3s ease-in-out !important;
    }

    div.stButton > button:hover {
        box-shadow: 0 12px 35px rgba(255, 75, 75, 0.6) !important;
        background: linear-gradient(90deg, #ff5f5f 0%, #ff8f8f 100%) !important;
        transform: translateY(-2px) !important;
    }

    /* 5. MAIN CONTENT PADDING */
    .main .block-container {
        padding-top: 2rem;
        max-width: 95%;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "provider" not in st.session_state:
    st.session_state["provider"] = list(AI_MODEL_DEFAULTS.keys())[0]
if "model_name" not in st.session_state:
    st.session_state["model_name"] = AI_MODEL_DEFAULTS[st.session_state["provider"]]


def on_provider_change():
    st.session_state["model_name"] = AI_MODEL_DEFAULTS[st.session_state["provider"]]


with st.sidebar:
    st.caption("LLM Settings")

    st.divider()

    # Input Fields
    provider = st.selectbox(
        "AI Provider",
        options=AI_MODEL_DEFAULTS.keys(),
        key="provider",
        on_change=on_provider_change,
        help="Select the LLM backbone for your agents.",
    )

    ai_model_name = st.text_input(
        "Model Name",
        key="model_name",
        help=AI_HELP_DEFAULTS.get(st.session_state["provider"], ""),
    )

    api_key = st.text_input(
        "API Key", type="password", placeholder="Enter credentials..."
    )

    # The Iconic Button
    if st.button("Save Credentials", use_container_width=True):
        if not api_key:
            st.error("Missing API Key")
        else:
            st.session_state["llm_credentials"] = LLMConnection(
                api_key=api_key, llm_name=ai_model_name, ai_provider=provider
            )
            st.toast("Connection Established", icon="⚡")

st.title("🛠️ Rule-Based Inductive Miner")

tab1, tab2, tab3 = st.tabs(["Data Upload", "Rule Discovery", "Process Discovery"])
with tab1:
    import streamlit as st

# --- 1. THE FILE UPLOADER CSS ---
st.markdown(
    """
<style>
    /* 1. WRAPPER CONTAINER STYLING */
    /* Target the container in Tab 1 */
    [data-testid="stVerticalBlock"] > div:has(div[data-testid="stFileUploader"]) {
        background-color: var(--secondary-background-color) !important;
        border-radius: 20px !important;
        padding: 30px !important;
        border: 1px solid rgba(255, 75, 75, 0.1) !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2) !important;
    }

    /* 2. STYLE THE DROPZONE (The dotted box) */
    [data-testid="stFileUploadDropzone"] {
        background-color: var(--background-color) !important;
        border: 2px dashed rgba(255, 75, 75, 0.3) !important;
        border-radius: 15px !important;
        transition: all 0.3s ease !important;
    }

    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #ff4b4b !important;
        background-color: rgba(255, 75, 75, 0.05) !important;
        box-shadow: 0 0 15px rgba(255, 75, 75, 0.1) !important;
    }

    /* 3. STYLE THE "BROWSE FILES" BUTTON INSIDE */
    [data-testid="stFileUploadDropzone"] button {
        background-color: #ff4b4b !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: bold !important;
    }

    /* 4. TYPOGRAPHY IMPROVEMENT */
    .upload-text {
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 5px;
        color: var(--text-color);
    }
    .upload-subtext {
        font-size: 14px;
        color: #9ea4b0;
        margin-bottom: 20px;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- 2. THE UI CODE INSIDE TAB 1 ---
with tab1:
    # Custom Header for the upload area
    st.markdown(
        '<p class="upload-text">📥 Import Event Log</p>', unsafe_allow_html=True
    )
    st.markdown(
        '<p class="upload-subtext">Upload your XES or GZ files to initialize the Rule-Based Inductive Miner agent.</p>',
        unsafe_allow_html=True,
    )

    # The Uploader
    uploaded_log = st.file_uploader(
        "For **using an agent**, upload an event log:",
        type=["xes", "gz"],
        label_visibility="collapsed",  # Hide the default label to use our custom one
    )

    # Interactive Step: Only show the "Analyze" button if a file is present
    if uploaded_log is not None:
        st.write("")  # Spacing
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Using your favorite Red Glow Button style here
            if st.button("Initialize Miner 🚀", use_container_width=True):
                st.toast(f"Processing {uploaded_log.name}...", icon="⚙️")
                # Add your mining logic here
    else:
        st.info("Waiting for data... Upload a file to proceed.", icon="💡")
with tab2:
    st.info("Blabla")
with tab3:
    st.info("To be integrated!")
