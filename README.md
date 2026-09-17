# Rule-Based Inductive Miner 🚀

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/dependency_manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Streamlit](https://img.shields.io/badge/app-Streamlit-ff4b4b.svg)](https://streamlit.io/)
[![Status](https://img.shields.io/badge/status-experimental-orange.svg)](#--project-status)

**Rule-Based Inductive Miner** is an experimental process mining framework that integrates **declarative constraints (Declare rules)** directly into the recursive discovery loop of the **Inductive Miner (IM)**.

By pairing inductive splitting operators with domain guards, rule projection,
and trace/event repair strategies, it discovers sound process trees even when
event data is noisy, incomplete, or partially non-conforming.

---

## ✨ Key Features

- **Hybrid Discovery:** Combines imperative process tree discovery (Inductive Miner) with declarative constraints.
- **Rule Extraction:** Extract domain rules automatically from **unstructured text** or **event data**.
- **Operator-Based Guards:** Ensures candidate process tree cuts (XOR, Sequence, Parallel, Loop) respect specified business rules.
- **Subproblem Rule Projection:** Automatically projects declarative constraints onto sub-logs during recursive decomposition.
- **4 Data Repair Strategies:** Handles non-conforming traces via customizable log repair algorithms.
- **Comprehensive Metrics:** Includes fitness, precision, and compliance evaluation utilities.
- **Interactive UI:** Built-in Streamlit app for visual experimentation and parameter tuning.

---

## ⚡ Quickstart

### 1. Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast, deterministic dependency management.

```bash
# Install uv (if not already installed)
pip install uv

# Clone and install dependencies
git clone https://github.com/your-username/rule-based-inductive-miner.git
cd rule-based-inductive-miner
uv sync
```

### 2. Python Usage

```python
from inductive_miner import apply_RBIM
from inductive_miner.rules import PrecedenceRule, ResponseRule
from inductive_miner.im_utils import RepairVariant

# 1. Define declarative constraints
list_of_rules = [
    PrecedenceRule("Approve Request", "Pay Check"),
    ResponseRule("Receive Order", "Send Confirmation"),
]

# 2. Mine the model
   model = apply_RBIM(
         log=log,
         rules=list_of_rules,
         repair_mode=RepairVariant.EditDistance,
         noise_threshold=0,
   )

```

> **Tip:** Check out `inductive_miner/examples.py` for complete, runnable scripts using toy event logs.

---

## 🚩 Core Architecture

```text
                       +----------------------+
                       | Raw / Noisy Log      |
                       | + Declarative Rules  |
                       +----------+----------+
                                   |
                       +----------v----------+
                       | Static Operator      |
                       | Guard Evaluation     |
                       +----------+----------+
                                  |
                  +-----------------------+-----------------------+
                  |                                             |
         [Log Conforms]                          [Log Non-Conforming]
                   |                                             |
                   |                          +----------v----------+
                   |                          | Apply Repair Strategy|
                   |                          | (Trace/Event/Edit)   |
                   |                          +----------+----------+
                   |                                             |
                   +-----------------------+----------------------+
                                   |
                        +----------v----------+
                        |  Recursive Split     |
                        |  + Rule Projection   |
                        +----------+----------+
                                   |
                       +----------v----------+
                        | Discovered Tree /    |
                        | Compliant Submodels  |
                       +----------------------+
```

1. **Operator Guards:** Declarative rules evaluate candidate process tree operators (Sequence, Exclusive Choice, Parallel, Loop) to filter out cuts that violate domain semantics.
2. **Adaptive Log Repair:** If an operator is semantically valid but the log contains violations, a repair strategy modifies the sub-log to enable the cut.
3. **Rule Projection:** As logs are partitioned into subproblems, rules are mathematically projected onto the relevant sub-alphabets, maintaining constraint satisfaction across the recursion.

---

## 🟠 Data Repair Strategies

| Strategy          | Description                                                                     | Best Used When...                                                       |
| :---------------- | :------------------------------------------------------------------------------ | :---------------------------------------------------------------------- |
| **Naïve / None**  | Leaves the log untouched; strictly falls back to base Inductive Miner behavior. | You want zero artificial manipulation of event data.                    |
| **Trace-Level**   | Filters out entire traces that violate the target operator's constraints.       | Non-conforming traces are considered erroneous anomalies/outliers.      |
| **Event-Level**   | Isolates and removes specific violating events within traces.                   | Traces are long and mostly valid, but contain stray activities.         |
| **Edit-Distance** | Uses minimum-cost string/trace alignment (insertion/deletion) to satisfy rules. | Preserving maximum trace volume while enforcing compliance is critical. |

---

## 📟 Supported Declarative Rules

The package supports major templates from the **Declare** family:

| Category              | Rule Template                | Class                    |
| :-------------------- | :--------------------------- | :----------------------- |
| **Existence**         | Existence (A)                | `ExistenceRule`          |
|                       | At Most Once (A)             | `AtMostOnceRule`         |
|                       | Initialization (A)           | `InitializationRule`     |
|                       | End (A)                      | `EndRule`                |
| **Relation**          | Precedence (A -> B)          | `PrecedenceRule`         |
|                       | Response (A -> B)            | `ResponseRule`           |
|                       | Responded Existence (A -> B) | `RespondedExistenceRule` |
|                       | Co-Existence (A <-> B)       | `CoExistenceRule`        |
|                       | Chain Precedence (A => B)    | `ChainPrecedenceRule`    |
|                       | Chain Response (A => B)      | `ChainResponseRule`      |
| **Negative Relation** | Not Co-Existence (A !<-> B)  | `NotCoExistenceRule`     |
|                       | Not Succession (A !-> B)     | `NotSuccessionRule`      |

---

## 💻 Interactive Web UI

A built-in [Streamlit](https://streamlit.io/) interface allows you to upload logs, configure declarative constraints, select repair strategies, and inspect discovered process trees interactively.

```bash
uv run streamlit run app.py
```

---

## 📦 Project Layout

```text
.
├── app.py                 # Streamlit web application entry point
├── inductive_miner/        # Core IM engine, guards, operators, and repair logic
│   └── examples.py         # Toy logs and end-to-end usage examples
│   ├── rules/           # Rule definitions and projection mechanics
├── rule_extraction/       # Extract rules from text (NLP/LLM) or event data
├── metrics/              # Conformance, fitness, precision, and compliance metrics
├── tests/               # Unit and integration test suite
┘── pyproject.toml         # Project configuration and dependency lock
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
> This project is an active research implementation designed to explore hybrid declarative-imperative discovery algorithms. APIs may evolve over time.

---

<p align="center">
  <i>scientifically speaking, we beat the log with a stick until it conforms.</i>
</p>
