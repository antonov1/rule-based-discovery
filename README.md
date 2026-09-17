# Rule-Based Inductive Miner

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/dependency_manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Streamlit](https://img.shields.io/badge/app-Streamlit-ff4b4b.svg)](https://streamlit.io/)
[![Status](https://img.shields.io/badge/status-experimental-orange.svg)](#project-status)

Rule-Based Inductive Miner (RBIM) is an experimental extension of the
Inductive Miner that incorporates declarative constraints into process
discovery.

Instead of checking constraints only after a model has been discovered, RBIM
uses Declare rules during recursive decomposition. Candidate decompositions are checked
against the rule set, rules are projected onto the resulting subproblems, and
constraints can be used to approximate process structure when the log alone
does not yield a suitable decomposition.

The implementation also contains several optional repair strategies for cases
where a data-driven decomposition conflicts with the supplied rules.

## Installation

The project requires Python 3.12+ and uses
[uv](https://github.com/astral-sh/uv) for dependency management.

```bash
git clone https://github.com/antonov1/rule-based-discovery.git
cd rule-based-discovery
uv sync
```

## Usage

```python
from inductive_miner import apply_RBIM
from inductive_miner.rules import PrecedenceRule, ResponseRule
from inductive_miner.im_utils import RepairVariant

rules = [
    PrecedenceRule("Approve Request", "Pay Check"),
    ResponseRule("Receive Order", "Send Confirmation"),
]

model = apply_RBIM(
    log=log,
    rules=rules,
    repair_mode=RepairVariant.EditDistance,
    noise_threshold=0,
)
```

More examples using small synthetic logs can be found in
`inductive_miner/examples.py`.

## Discovery

RBIM follows the recursive structure of the Inductive Miner.

Candidate decompositions are checked against the supplied declarative rules.
When a decomposition is accepted, the relevant rules are projected onto its
subproblems before discovery continues recursively.

If the log does not provide a usable decomposition, RBIM can also use the rule
set to derive additional structure.

## Repair strategies

Repair can be applied when a data-driven decomposition is rejected because of
the rule set.

| Strategy | Description |
| --- | --- |
| `Naive` | No repair; use the original traces |
| `Trace` | Trace-level repair |
| `Event` | Event-level repair |
| `EditDistance` | Edit-distance-based repair |

Repair is not required. Without it, RBIM can still fall back to rule-driven
structure approximation.

## Supported Declare rules

The following Declare templates are currently implemented:

| Category | Template | Class |
| --- | --- | --- |
| Existence | Existence (A) | `ExistenceRule` |
| | At Most Once (A) | `AtMostOnceRule` |
| | Initialization (A) | `InitializationRule` |
| | End (A) | `EndRule` |
| Relation | Precedence (A → B) | `PrecedenceRule` |
| | Response (A → B) | `ResponseRule` |
| | Responded Existence (A ↔ B) | `RespondedExistenceRule` |
| | Co-Existence (A ↔ B) | `CoExistenceRule` |
| | Chain Precedence (A ⇒ B) | `ChainPrecedenceRule` |
| | Chain Response (A ⇒ B) | `ChainResponseRule` |
| Negative relation | Not Co-Existence (A ↮ B) | `NotCoExistenceRule` |
| | Not Succession (A ↛ B) | `NotSuccessionRule` |

## Rule extraction

The repository also contains utilities for obtaining declarative rules from
unstructured text and event data. These are located in `rule_extraction/`.

## Evaluation

Utilities for evaluating discovered models are provided in `metrics/`.
Currently this includes fitness, precision, and rule-conformance measures.

## Web interface

A Streamlit interface is included for running experiments without using the
Python API directly.

```bash
uv run streamlit run app.py
```

The interface can be used to load an event log, configure rules and discovery
parameters, select a repair strategy, and inspect the resulting process tree.

## Project structure

```text
.
├── app.py
├── inductive_miner/
│   ├── cuts/
│   ├── fall_throughs/
│   ├── rules/
│   └── examples.py
├── rule_extraction/
├── metrics/
├── tests/
└── pyproject.toml
```

The main RBIM implementation is under `inductive_miner/`. Cut detection and
rule checks are implemented in `cuts/`, while fallback behavior is implemented
in `fall_throughs/`.

## Tests

Run the test suite with:

```bash
uv run pytest
```

For coverage:

```bash
uv run pytest --cov=inductive_miner --cov=rule_extraction
```

## Project status

This is a research implementation and is still experimental. The API,
individual repair strategies, and parts of the discovery procedure may change
as the approach develops.

---

<p align="center">
  <i>scientifically speaking, we beat the log with a stick until it conforms.</i>
</p>
