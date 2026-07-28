import math
import os
import tempfile

import pm4py
import streamlit as st
from inductive_miner.main import apply_IM_with_rules
from llm_connection.query import query_llm_for_declare_rules
from metrics.fitness import fitness_token_based_tree as fitness_token_based
from metrics.precision import precision_token_based_tree as precision_token_based
from metrics.rule_conformance import conformance as rule_conformance_apply
from metrics.simplicity import complexity_size
from pm4py.objects.bpmn.layout import layouter
from pm4py.visualization.bpmn import visualizer as bpmn_visualizer
from pm4py.visualization.petri_net import visualizer as pn_visualizer
from pm4py.visualization.process_tree import visualizer as pt_visualizer
from powl import import_event_log
from promoai.general_utils.ai_providers import (
    AI_HELP_DEFAULTS,
    AI_MODEL_DEFAULTS,
    AIProviders,
    MAIN_HELP,
)
from promoai.general_utils.llm_connection import LLMConnection
from rule_extraction.from_data import extract
from rules.rule_utils import minimize_rule_set
from utils.preprocess import preprocess_log

STRATEGY_OPTIONS = {"From Data": "DATA", "From Text": "TEXT"}
TEMP_FOLDER = "/tmp/rim_uploads"


def get_children_activities(tree):
    activities = set()
    if tree.label is not None:
        activities.add(tree.label)
    else:
        for child in tree.children:
            activities.update(get_children_activities(child))
    return activities


def get_relevant_rules(activities, rules):
    relevant = []
    for rule in rules:
        # check if activity_a and activity_b are both in it
        if hasattr(rule, "activity_a") and hasattr(rule, "activity_b"):
            if rule.activity_a in activities and rule.activity_b in activities:
                relevant.append(rule)
        elif hasattr(rule, "target_activity"):
            if rule.target_activity in activities:
                relevant.append(rule)
    return relevant


def compute_metrics(model, log, rules, net):
    fitness = fitness_token_based(log, model)
    precision = precision_token_based(log, model)
    complexity = complexity_size(net)
    alphabet = set(log["concept:name"].unique())
    rule_conformance = rule_conformance_apply(model, rules if rules else [], alphabet)
    return {
        "fitness": fitness,
        "precision": precision,
        "complexity": complexity,
        "rule_conformance": rule_conformance,
    }


def reset_rule_discovery_state():
    st.session_state["discovery_done"] = False
    st.session_state["discovered_rules"] = []
    st.session_state["selected_rules"] = set()
    st.session_state["used_rules"] = []
    st.session_state["current_page"] = 1
    st.session_state["selection_version"] = (
        st.session_state.get("selection_version", 0) + 1
    )
    st.session_state.pop("model", None)
    st.session_state.pop("stats", None)
    st.session_state.pop("activity_filter", None)
    st.session_state.pop("rule_type_filter", None)


def reset_discovery_on_strategy_change():

    st.session_state["discovery_done"] = False
    st.session_state["discovered_rules"] = []
    st.session_state["selected_rules"] = set()
    st.session_state["used_rules"] = []
    st.session_state["current_page"] = 1
    st.session_state["selection_version"] = (
        st.session_state.get("selection_version", 0) + 1
    )

    st.session_state.pop("model", None)
    st.session_state.pop("stats", None)
    st.session_state.pop("activity_filter", None)
    st.session_state.pop("rule_type_filter", None)


def render_sidebar_progress():
    current = st.session_state["current_step"]

    steps = [
        "Connection Setup",
        "Data Upload",
        "Rule Mining",
        "Process Discovery",
    ]

    total_steps = len(steps)

    st.markdown("### 🧭 Progress")

    st.markdown(f"**Step {current + 1} of {total_steps}**")
    st.caption(steps[current])

    st.progress((current + 1) / total_steps)

    st.divider()

    if current > 0:
        if st.button("⬅ Back", use_container_width=True):
            st.session_state["current_step"] -= 1
            if st.session_state["current_step"] == 2:
                st.session_state["discovery_strategy"] = st.session_state.get(
                    "locked_discovery_strategy",
                    st.session_state.get("discovery_strategy", "From Data"),
                )
                st.session_state["last_discovery_strategy"] = st.session_state[
                    "discovery_strategy"
                ]

                st.session_state["text_rule_description"] = st.session_state.get(
                    "locked_text_rule_description",
                    st.session_state.get("text_rule_description", ""),
                )
            if st.session_state["current_step"] == 1:
                reset_rule_discovery_state()
                st.session_state.pop("event_log", None)
            st.session_state.pop("model", None)
            st.session_state.pop("stats", None)

            st.rerun()

    if st.button("Restart Session", type="secondary", use_container_width=True):
        st.session_state.clear()
        st.rerun()


def inject_css():
    with open("miner.css", "r") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def initialization():
    if "selection_version" not in st.session_state:
        st.session_state["selection_version"] = 0
    if "selected_rules" not in st.session_state:
        st.session_state["selected_rules"] = set()
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = 1
    if "current_step" not in st.session_state:
        st.session_state["current_step"] = 0
    if "provider" not in st.session_state:
        st.session_state["provider"] = list(AI_MODEL_DEFAULTS.keys())[0]
    if "model_name" not in st.session_state:
        st.session_state["model_name"] = AI_MODEL_DEFAULTS[st.session_state["provider"]]
    if "setup_done" not in st.session_state:
        st.session_state["setup_done"] = False
    if "show_skipped_message" not in st.session_state:
        st.session_state["show_skipped_message"] = False
    if "show_saved_message" not in st.session_state:
        st.session_state["show_saved_message"] = False
    if "used_rules" not in st.session_state:
        st.session_state["used_rules"] = []
    if "discovered_rules" not in st.session_state:
        st.session_state["discovered_rules"] = []
    if "discovery_done" not in st.session_state:
        st.session_state["discovery_done"] = False
    if "discovery_strategy" not in st.session_state:
        st.session_state["discovery_strategy"] = "From Data"
    if "last_discovery_strategy" not in st.session_state:
        st.session_state["last_discovery_strategy"] = st.session_state[
            "discovery_strategy"
        ]
    if "text_rule_description" not in st.session_state:
        st.session_state["text_rule_description"] = ""


def setup_llm_connection():
    def on_provider_change():
        st.session_state["model_name"] = AI_MODEL_DEFAULTS[st.session_state["provider"]]

    st.markdown("## ⚙️ Connection Setup")

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
        if provider == AIProviders.AZURE.value:
            azure_endpoint = st.text_input(
                "Azure Endpoint",
                key="azure_endpoint",
                placeholder="https://your-resource.openai.azure.com/",
            )

        st.caption(
            "You can continue without credentials if you wish to mine rules only from data."
        )

        if st.button("Proceed", use_container_width=True):
            if api_key.strip():
                if provider == AIProviders.AZURE.value:
                    args = {"END_POINT": azure_endpoint}
                else:
                    args = {}

                st.session_state["llm_credentials"] = LLMConnection(
                    api_key=api_key,
                    llm_name=ai_model_name,
                    ai_provider=provider,
                    args=args,
                )
                st.session_state["show_saved_message"] = True
            else:
                st.session_state.pop("llm_credentials", None)
                st.session_state["show_saved_message"] = False
                st.session_state["show_skipped_message"] = True

            st.session_state["current_step"] = 1
            st.rerun()


def rule_discovery():
    options = (
        ["From Data", "From Text"]
        if st.session_state.get("llm_credentials")
        else ["From Data"]
    )
    st.markdown("### 🔍 2. Rule Discovery")
    if "discovered_rules" not in st.session_state:
        st.session_state["discovered_rules"] = []
    # --- Settings Area ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 1])
        with c1:
            strategy = st.selectbox(
                "Strategy",
                options=options,
                key="discovery_strategy",
            )

            if st.session_state["last_discovery_strategy"] != strategy:
                reset_discovery_on_strategy_change()
                st.session_state["last_discovery_strategy"] = strategy
                st.rerun()

            disabled = strategy != "From Data"
        with c2:
            support_val = st.number_input(
                "Min. Support", 0.01, 0.99, 0.50, disabled=disabled
            )
        with c3:
            conf_val = st.number_input(
                "Min. Confidence", 0.01, 1.0, 0.80, disabled=disabled
            )
        if strategy == "From Text":
            # Add a textbox area for prompting
            description = st.text_area(
                "Enter process description",
                placeholder="Describe the process...",
                height=100,
                key="text_rule_description",
            )
        if st.button("Discover Rules ⚡", use_container_width=True):
            st.session_state["discovery_done"] = True
            st.toast("Hold on tight, discovering rules", icon="🔍")
            if strategy == "From Data":
                preprocessed_log = preprocess_log(st.session_state["event_log"])
                extracted = extract(
                    preprocessed_log,
                    min_support=support_val,
                    min_confidence=conf_val,
                )
                st.session_state["discovered_rules"] = minimize_rule_set(
                    extracted, preprocessed_log
                )
                # st.session_state["discovered_rules"] = extracted

            elif strategy == "From Text":
                rules_to_consider = []
                try:
                    rules, _, _ = query_llm_for_declare_rules(
                        st.session_state["text_rule_description"],
                        activities=sorted(
                            set(
                                a
                                for trace in preprocess_log(
                                    st.session_state["event_log"]
                                )
                                for a in trace
                            )
                        ),
                        llm_connection=st.session_state.get("llm_credentials"),
                    )
                    for rule in rules:
                        rule.apply(preprocess_log(st.session_state["event_log"]))
                        rule.calc_support()
                        if rule.get_support() == 0:
                            continue
                        try:
                            rule.calc_confidence(
                                preprocess_log(st.session_state["event_log"])
                            )
                        except Exception:
                            rule.calc_confidence()
                        rules_to_consider.append(rule)
                    st.session_state["discovered_rules"] = rules_to_consider

                except ValueError as e:
                    st.error(f"Error during rule discovery: {str(e)}")
                    st.session_state["discovered_rules"] = []
            print(
                f"Discovered {len(st.session_state['discovered_rules'])} rules with support >= {support_val} and confidence >= {conf_val}"
            )
            st.toast("Mining complete!", icon="✨")
            st.rerun()

        st.write("")

    if st.session_state.get("discovery_done"):
        activities = sorted(
            set(
                a
                for trace in preprocess_log(st.session_state["event_log"])
                for a in trace
            )
        )
        rule_types = sorted(
            set(str(r).split("(")[0] for r in st.session_state["discovered_rules"])
        )

        current_f_act = st.session_state.get("activity_filter", activities)
        current_f_type = st.session_state.get("rule_type_filter", rule_types)

        raw_rules = [
            r for r in st.session_state["discovered_rules"] if r.get_support() != 0
        ]

        filtered_rules = [
            r
            for r in raw_rules
            if str(r).split("(")[0] in current_f_type
            and any(act in str(r) for act in current_f_act)
        ]
        filtered_rules.sort(
            key=lambda r: (r.get_support(), r.get_confidence()), reverse=True
        )

        st.markdown("### 📋 Rule Discovery Workspace")
        if "selected_activities" not in st.session_state:
            st.session_state["selected_activities"] = set()
        if "selected_types" not in st.session_state:
            st.session_state["selected_types"] = set()
        action_col1, action_col2 = st.columns([2, 2])
        disabled = (
            len(st.session_state["discovered_rules"]) == 0 or strategy != "From Data"
        )
        with action_col1:
            if strategy == "From Data":
                with st.popover(
                    "🔍 Filter Discovery Results",
                    use_container_width=True,
                    disabled=disabled,
                ):
                    # We use key to link all rules to the session state accessed in Step 2
                    st.multiselect(
                        "Activities",
                        options=activities,
                        default=activities,
                        key="activity_filter",
                        on_change=reset_selection_on_filter,
                    )
                    st.multiselect(
                        "Rule Types",
                        options=rule_types,
                        default=rule_types,
                        key="rule_type_filter",
                        on_change=reset_selection_on_filter,
                    )

                    if st.button(
                        "Clear All Filters", use_container_width=True, disabled=disabled
                    ):
                        # Reset the keys in session state specifically
                        st.session_state["activity_filter"] = activities
                        st.session_state["rule_type_filter"] = rule_types
                        st.session_state["selected_rules"] = set()
                        st.rerun()
            else:
                st.button(
                    "🔍 Filter Discovery Results",
                    use_container_width=True,
                    disabled=True,
                    help="Filtering is only available for rules mined from data.",
                )
        with action_col2:
            with st.popover("🛠️ Selection Tools", use_container_width=True):
                st.markdown("##### Bulk Actions")
                st.caption("Applied to currently filtered rules")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Select All", use_container_width=True):
                        bulk_action("SELECT_ALL", filtered_rules)

                    if st.button("Invert", use_container_width=True):
                        bulk_action("INVERT", filtered_rules)

                with c2:
                    if st.button("Clear All", use_container_width=True):
                        bulk_action("CLEAR_ALL", [])

                    if len(st.session_state["selected_rules"]) > 0:
                        export_data = "\n".join(
                            list(st.session_state["selected_rules"])
                        )
                        st.download_button(
                            "Export .txt",
                            data=export_data,
                            file_name="selected_rules.txt",
                            use_container_width=True,
                        )

        # Pagination Slicing
        items_per_page = 8
        total_rules = len(filtered_rules)
        total_pages = max(1, math.ceil(total_rules / items_per_page))
        if st.session_state.current_page > total_pages:
            # in case we rediscover rules and we end up, e.g. on page 10 even though there are 2 pages
            st.session_state.current_page = total_pages
        if st.session_state.current_page < 1:
            st.session_state.current_page = 1
        start_idx = (st.session_state.current_page - 1) * items_per_page
        rules_to_display = filtered_rules[start_idx : start_idx + items_per_page]

        # --- THE TABLE ---
        st.divider()
        h1, h2, h3, h4 = st.columns([5, 1, 1, 1])
        h1.markdown(
            '<div class="rule-header">Discovered Rule</div>', unsafe_allow_html=True
        )
        h2.markdown('<div class="rule-header">Supp.</div>', unsafe_allow_html=True)
        h3.markdown('<div class="rule-header">Conf.</div>', unsafe_allow_html=True)
        h4.markdown('<div class="rule-header">Select</div>', unsafe_allow_html=True)
        rule_by_id = {str(r): r for r in rules_to_display}

        for r in rules_to_display:
            r_id = str(r)
            is_checked = r_id in st.session_state["selected_rules"]

            # Apply a highlight class if selected
            row_class = "selected-row" if is_checked else ""

            with st.container():
                st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
                r1, r2, r3, r4 = st.columns([5, 1, 1, 1])

                r1.markdown(f"**{r_id}**")
                r2.markdown(
                    f'<span class="metric-text">{r.get_support():.3f}</span>',
                    unsafe_allow_html=True,
                )
                r3.markdown(
                    f'<span class="metric-text">{r.get_confidence():.3f}</span>',
                    unsafe_allow_html=True,
                )

                checked = r4.checkbox(
                    " ",
                    key=f"cb_{hash(r_id)}_{st.session_state['selection_version']}",
                    value=is_checked,
                    label_visibility="collapsed",
                )

                if checked:
                    st.session_state["selected_rules"].add(r_id)
                else:
                    st.session_state["selected_rules"].discard(r_id)
                st.markdown("</div>", unsafe_allow_html=True)
        # Pagination footer
        st.write("")
        _, p_prev, p_text, p_next, _ = st.columns([4, 0.5, 1, 0.5, 4])

        with p_prev:
            # Key names to target CSS styling for these buttons
            if st.button(
                "‹", key="btn_prev_page", disabled=(st.session_state.current_page <= 1)
            ):
                if st.session_state.current_page == 1:
                    st.toast("You're already on the first page!", icon="⚠️")
                else:
                    st.session_state.current_page -= 1
                    st.rerun()

        with p_text:
            st.markdown(
                f"<p style='text-align:center; padding-top:10px; font-size:14px; opacity:0.8;'>"
                f"{st.session_state.current_page} of {total_pages}</p>",
                unsafe_allow_html=True,
            )

        with p_next:
            if st.button(
                "›",
                key="btn_next_page",
                disabled=(st.session_state.current_page >= total_pages),
            ):
                if st.session_state.current_page == total_pages:
                    st.toast("You're already on the last page!", icon="⚠️")
                else:
                    st.session_state.current_page += 1
                    st.rerun()

        st.divider()
        col_left, col_right = st.columns([3, 1])
        with col_left:
            st.write(
                f"Items selected for Process Discovery: **{len(st.session_state['selected_rules'])}**"
            )
        with col_right:
            if st.button("Proceed to Stage 3 →", type="primary"):
                st.toast(
                    "Rules locked in! Moving to Process Discovery stage.", icon="🚀"
                )
                st.session_state["locked_discovery_strategy"] = st.session_state[
                    "discovery_strategy"
                ]
                st.session_state["locked_text_rule_description"] = st.session_state.get(
                    "text_rule_description",
                    "",
                )
                st.session_state["last_discovery_strategy"] = st.session_state[
                    "discovery_strategy"
                ]

                rule_by_id = {str(r): r for r in st.session_state["discovered_rules"]}
                st.session_state["used_rules"] = [
                    rule_by_id[rid]
                    for rid in st.session_state["selected_rules"]
                    if rid in rule_by_id
                ]
                st.session_state.pop("model", None)
                st.session_state.pop("stats", None)

                st.session_state["current_step"] = 3
                st.rerun()
    else:
        st.info("Run the discovery engine to view and select process rules.")


def reset_selection_on_filter():
    """Wipes selection and resets pagination whenever filters change."""
    st.session_state["selected_rules"] = set()
    st.session_state["current_page"] = 1
    st.session_state["selection_version"] += 1
    st.toast("Filters changed: Selection cleared.", icon="🧹")


def bulk_action(mode, filtered_rules_list):
    if mode == "SELECT_ALL":
        for r in filtered_rules_list:
            st.session_state["selected_rules"].add(str(r))
    elif mode == "CLEAR_ALL":
        st.session_state["selected_rules"] = set()
    elif mode == "INVERT":
        all_filtered = set(str(r) for r in filtered_rules_list)
        currently_selected = st.session_state["selected_rules"]
        st.session_state["selected_rules"] = all_filtered - currently_selected

    # Increment version to refresh all checkboxes
    st.session_state["selection_version"] += 1
    st.rerun()


def upload_data():
    st.markdown("### 1. Data Upload 📥")
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
            # Create the folder if it doesn't exist
            os.makedirs(TEMP_FOLDER, exist_ok=True)

            # Action button only appears after upload
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("Proceed to Rule Discovery", use_container_width=True):
                    st.toast(
                        "Hold on tight, uploading and processing the log...", icon="⏳"
                    )
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        delete=False,
                        dir=TEMP_FOLDER,
                        suffix=uploaded_log.name,
                    ) as temp_file:
                        temp_file.write(uploaded_log.read())
                        temp_path = temp_file.name

                    log = import_event_log(temp_path)
                    st.session_state["event_log"] = pm4py.convert_to_dataframe(log)

                    st.session_state["current_step"] = 2
                    st.rerun()
        else:
            st.info("Start by uploading an event log.")


def miner_page():
    inject_css()
    initialization()

    with st.sidebar:
        st.markdown("### ⚒️ Process Discovery")
        st.divider()
        render_sidebar_progress()

        if st.session_state.pop("show_saved_message", False):
            st.balloons()
            st.success("Credentials Provided")
            st.markdown(
                f"**Provider:** {st.session_state['provider']}  \n**Model:** {st.session_state['model_name']}"
            )

        if st.session_state.get("setup_done"):
            st.success("Credentials Provided")
            st.markdown(
                f"**Provider:** {st.session_state['provider']}  \n**Model:** {st.session_state['model_name']}"
            )

    if st.session_state["current_step"] == 0:
        st.markdown(
            '<div class="workbench-header">⚒️ Connection Setup </div>',
            unsafe_allow_html=True,
        )

        setup_llm_connection()
    if st.session_state["current_step"] == 1:
        st.markdown(
            '<div class="workbench-header">⚒️ Data Upload </div>',
            unsafe_allow_html=True,
        )

        upload_data()

    if st.session_state["current_step"] == 2:
        st.markdown(
            '<div class="workbench-header">⚒️ Rule Mining </div>',
            unsafe_allow_html=True,
        )
        # remove the model from state if present
        rule_discovery()
    if st.session_state["current_step"] == 3:
        st.markdown(
            '<div class="workbench-header">⚒️ Process Discovery </div>',
            unsafe_allow_html=True,
        )

        st.markdown("### 3. Process Discovery 🏗️")
        st.caption("Convert discovered rules into a visual process model.")
        if "model" not in st.session_state:
            pass

            st.session_state["model"] = apply_IM_with_rules(
                log=preprocess_log(st.session_state["event_log"]),
                rules=st.session_state["used_rules"],
            )

        if "model" not in st.session_state or st.session_state["model"] is None:
            st.warning("No model discovered with current parameters")
            return
        activities = get_children_activities(st.session_state["model"])
        relevant_rules = get_relevant_rules(activities, st.session_state["used_rules"])
        with st.expander("Relevant rules"):
            for rule in relevant_rules:
                st.markdown(f"- {rule}")
                st.write("")
        viz_col1, _ = st.columns([2, 1])

        with viz_col1:
            view_mode = st.segmented_control(
                "Select Notation:",
                options=["Process Tree", "Petri Net", "BPMN"],
                default="BPMN",
                key="viz_mode_selector",
            )
        net, im, fm = pm4py.convert_to_petri_net(st.session_state["model"])
        # Mini Stats for the model
        if "stats" not in st.session_state:
            stats = compute_metrics(
                st.session_state["model"],
                st.session_state["event_log"],
                relevant_rules,
                net,
            )
            st.session_state["stats"] = stats
        # show the metrics
        st.markdown("#### Model Metrics")

        metric_html = f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Fitness</div>
                <div class="metric-value">{st.session_state['stats']['fitness']:.3f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Precision</div>
                <div class="metric-value">{st.session_state['stats']['precision']:.3f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Complexity</div>
                <div class="metric-value">{st.session_state['stats']['complexity']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Rule Conformance</div>
                <div class="metric-value">{st.session_state['stats']['rule_conformance'][0]:.3f}</div>
            </div>
        </div>
        """

        st.markdown(metric_html, unsafe_allow_html=True)
        unsat_rules = st.session_state["stats"]["rule_conformance"][1]

        if unsat_rules:
            st.warning(
                f"{len(unsat_rules)} unsatisfied rule{'s' if len(unsat_rules) != 1 else ''}"
            )
            with st.expander("Show Unsatisfied Rules"):
                st.markdown(
                    """
                    <style>
                    .rule-chip {
                        display: inline-block;
                        padding: 0.35rem 0.6rem;
                        margin: 0.2rem 0.25rem 0.2rem 0;
                        border-radius: 999px;
                        background: #ffe8e8;
                        color: #8a1f1f;
                        border: 1px solid #ffb8b8;
                        font-size: 0.9rem;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown(
                    " ".join(
                        f'<span class="rule-chip">{rule}</span>' for rule in unsat_rules
                    ),
                    unsafe_allow_html=True,
                )
        else:
            st.success("All rules satisfied")
        with st.container(border=True):
            try:
                if view_mode == "Process Tree":
                    parameters = {
                        pt_visualizer.Variants.WO_DECORATION.value.Parameters.FORMAT: "svg"
                    }
                    gviz = pt_visualizer.apply(
                        st.session_state["model"], parameters=parameters
                    )

                elif view_mode == "Petri Net":
                    gviz = pn_visualizer.apply(
                        net, im, fm, parameters={"format": "svg"}
                    )
                else:  # BPMN
                    bpmn = pm4py.convert_to_bpmn(net, im, fm)
                    layouted_bpmn = layouter.apply(bpmn)
                    gviz = bpmn_visualizer.apply(
                        layouted_bpmn, parameters={"format": "svg"}
                    )

                svg_str = gviz.pipe(format="svg").decode("utf-8")

                st.image(svg_str)

            except Exception as e:
                st.error(f"Visualization Error: {str(e)}")

    st.divider()


if __name__ == "__main__":
    miner_page()
