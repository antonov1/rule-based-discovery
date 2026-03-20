import streamlit as st
from promoai.general_utils.ai_providers import (
    AI_HELP_DEFAULTS,
    AI_MODEL_DEFAULTS,
    MAIN_HELP,
)
from promoai.general_utils.llm_connection import LLMConnection


def run_setup():
    st.markdown(
        """
    <style>
        /* 1. DYNAMIC SIDEBAR (Theme-Sync) */
        [data-testid="stSidebar"] {
            background-color: var(--secondary-background-color) !important;
            border-right: 1px solid rgba(255, 75, 75, 0.3) !important;
        }

        /* 2. THE MODERN CARD (Red-Tinted Glassmorphism) */
        [data-testid="stVerticalBlockBorderWrapper"] > div:has(div[data-testid="stVerticalBlock"]) {
            border: 1px solid rgba(255, 75, 75, 0.2) !important;
            border-radius: 24px !important;
            padding: 40px !important;
            background: linear-gradient(160deg, rgba(26, 8, 8, 0.9) 0%, rgba(14, 17, 23, 0.9) 100%) !important;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(255, 75, 75, 0.05) !important;
            backdrop-filter: blur(12px);
        }

        [data-testid="stSidebar"] *, .stMarkdown, label p {
            color: var(--text-color) !important;
        }

        input, [data-baseweb="select"] * {
            color: var(--text-color) !important;
            -webkit-text-fill-color: var(--text-color) !important;
        }

        div.stButton {
            width: 100% !important;
            margin-top: 25px;
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
            color: white !important;
        }

        div.stButton > button:active {
            transform: scale(0.98) !important;
        }

        /* 5. INPUT BOX STYLING */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            background-color: var(--background-color) !important;
            border: 1px solid rgba(255, 75, 75, 0.2) !important;
            border-radius: 12px !important;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Initialize State
    if "provider" not in st.session_state:
        st.session_state["provider"] = list(AI_MODEL_DEFAULTS.keys())[0]
    if "model_name" not in st.session_state:
        st.session_state["model_name"] = AI_MODEL_DEFAULTS[st.session_state["provider"]]

    def on_provider_change():
        st.session_state["model_name"] = AI_MODEL_DEFAULTS[st.session_state["provider"]]

    # --- 3. PAGE UI ---

    st.title("⚙️ Connection Setup")
    st.markdown("##### *Initialize the engine by linking an LLM provider.*")

    # The Sidebar remains consistent as a "Status Deck"
    with st.sidebar:
        st.caption("Connection Setup")
        st.divider()
        if "llm_credentials" in st.session_state:
            st.success("Setup Completed", icon="🟢")
        else:
            st.warning("Missing Credentials", icon="🔴")

    # The Main Setup Card
    with st.container(border=True):
        st.markdown("### 🔑 API Configuration")

        provider = st.selectbox(
            "AI Provider",
            options=AI_MODEL_DEFAULTS.keys(),
            key="provider",
            on_change=on_provider_change,
            help=MAIN_HELP,
        )

        col1, col2 = st.columns(2)
        with col1:
            ai_model_name = st.text_input(
                "Model Name",
                key="model_name",
                help=AI_HELP_DEFAULTS.get(st.session_state["provider"], ""),
            )
        with col2:
            api_key = st.text_input(
                "API Key", type="password", placeholder="Enter your key here..."
            )

        # Padding before the big button
        st.write("")

        # The Iconic Button (Full width of the card)
        if st.button("Save Credentials", use_container_width=True):
            if not api_key:
                st.error("Please provide an API key to establish the connection.")
            else:
                try:
                    st.session_state["llm_credentials"] = LLMConnection(
                        api_key=api_key, llm_name=ai_model_name, ai_provider=provider
                    )
                    st.success("Configuration Completed!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Failed to connect: {str(e)}")

    st.divider()
    st.caption("Rule-Based Inductive Miner • Prototype v0.1")


if __name__ == "__main__":
    run_setup()
