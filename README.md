# Rule-Based Inductive Miner 🚀

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/dependency_manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Streamlit](https://img.shields.io/badge/app-Streamlit-ff4b4b.svg)](https://streamlit.io/)
[![Status](https://img.shields.io/badge/status-experimental-orange.svg)](#--project-status)

**Rule-Based Inductive Miner (RBIM)** is an experimental process discovery
algorithm that integrates **declarative constraints (Declare rules)** directly
into the recursive discovery procedure of the **Inductive Miner (IM)**.

RBIM retains the data-driven discovery capabilities of IM while incorporating
domain knowledge through operator-based rule checks, recursive rule projection,
and rule-driven structure approximation. This allows declarative constraints to
guide discovery when the observed event data is incomplete, partially
non-conforming, or does not provide a suitable data-driven decomposition.

---

## ✨ Key Features

- **Rule-Guided Discovery:** Integrates declarative constraints directly into
  Inductive Miner-based process discovery.
- **Operator-Based Rule Checks:** Checks candidate process tree cuts
  (XOR, Sequence, Parallel, Loop) against the specified rules.
- **Subproblem Rule Projection:** Projects declarative constraints onto
  subproblems during recursive decomposition.
- **Rule-Driven Structure Approximation:** Derives additional process structure
  from declarative constraints when no suitable data-driven decomposition is
  available.
- **Optional Repair Strategies:** Supports repair mechanisms for reconsidering
  rejected data-driven decompositions.
- **Rule Extraction:** Includes utilities for extracting domain rules from
  **unstructured text** or **event data**.
- **Evaluation Metrics:** Includes fitness, precision, and rule-conformance
  evaluation utilities.
- **Interactive UI:** Built-in Streamlit app for experimentation and parameter
  tuning.

---

## ⚡ Quickstart

### 1. Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency
management.

```bash
# Install uv (if not already installed)
pip install uv

# Clone and install dependencies
git clone https://github.com/antonov1/rule-based-discovery.git
cd rule-based-inductive-miner
uv sync
```

### 2. Python Usage

```python
from inductive_miner import apply_RBIM
from inductive_miner.rules import PrecedenceRule, ResponseRule
from inductive_miner.im_utils import RepairVariant

# Define declarative constraints
rules = [
    PrecedenceRule("Approve Request", "Pay Check"),
    ResponseRule("Receive Order", "Send Confirmation"),
]

# Mine the model
model = apply_RBIM(
    log=log,
    rules=rules,
    repair_mode=RepairVariant.EditDistance,
    noise_threshold=0,
)
```

> **Tip:** Check out `inductive_miner/examples.py` for complete, runnable
> examples using toy event logs.

---

## 🟠 Data Repair Strategies

RBIM supports optional repair strategies that can be used during discovery.

| Strategy | Description |
| :--- | :--- |
| **Naïve / None** | Leaves the event data unchanged. |
| **Trace-Level** | Applies repair at the trace level. |
| **Event-Level** | Applies repair at the event level. |
| **Edit-Distance** | Uses edit-distance-based repair. |

Repair is optional. If no repair strategy is used, RBIM can still use its
rule-driven mechanisms to derive a model that incorporates the supplied
constraints.

---

## 📟 Supported Declarative Rules

The package supports the following templates from the **Declare** family:

| Category | Rule Template | Class |
| :--- | :--- | :--- |
| **Existence** | Existence (A) | `ExistenceRule` |
| | At Most Once (A) | `AtMostOnceRule` |
| | Initialization (A) | `InitializationRule` |
| | End (A) | `EndRule` |
| **Relation** | Precedence (A → B) | `PrecedenceRule` |
| | Response (A → B) | `ResponseRule` |
| | Responded Existence (A ↔ B) | `RespondedExistenceRule` |
| | Co-Existence (A ↔ B) | `CoExistenceRule` |
| | Chain Precedence (A ⇒ B) | `ChainPrecedenceRule` |
| | Chain Response (A ⇒ B) | `ChainResponseRule` |
| **Negative Relation** | Not Co-Existence (A ↮ B) | `NotCoExistenceRule` |
| | Not Succession (A ↛ B) | `NotSuccessionRule` |

---

## 💻 Interactive Web UI

A built-in [Streamlit](https://streamlit.io/) interface allows you to upload
event logs, configure declarative constraints, select discovery parameters and
repair strategies, and inspect discovered process trees interactively.

```bash
uv run streamlit run app.py
```

---

## 📦 Project Layout

```text
.
├── app.py                  # Streamlit web application entry point
├── inductive_miner/        # Rule-Based Inductive Miner implementation
│   ├── cuts/               # Cut detection and rule checks
│   ├── fall_throughs/      # Data- and rule-based fall-throughs
│   ├── rules/              # Rule definitions and projection
│   └── examples.py         # Toy logs and usage examples
├── rule_extraction/        # Rule extraction from text or event data
├── metrics/                # Fitness, precision, and rule-conformance metrics
├── tests/                  # Unit and integration tests
└── pyproject.toml          # Project configuration and dependencies
```

---

## 🕷️ Testing

Run the automated test suite with `pytest`:

```bash
uv run pytest
```

To run with coverage reporting:

```bash
uv run pytest --cov=inductive_miner --cov=rule_extraction
```

---

## ⚠️ Project Status

> **Status: Experimental**
>
> This project is an active research implementation of the Rule-Based
> Inductive Miner. APIs and implementation details may evolve over time.

---

<p align="center">
  <i>scientifically speaking, we beat the log with a stick until it conforms.</i>
</p>
