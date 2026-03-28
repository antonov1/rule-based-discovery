# Inductive Miner Examples (Structured)

This document structures the provided inductive miner output into readable Markdown examples.

## Example 6 — Enforce `End(B)` although one trace ends with `C`

**Why:** Not all traces end in `B`, but the resulting model should.

### Input

- **Log:** `[['A', 'B'], ['C', 'B'], ['A', 'C']]`
- **Rules:** `[End(B)]`

### Discovery summary

- Initial failed cut: `X`
- Accepted cut: `->` with groups `[['A'], ['C'], ['B']]`
- Unsatisfied rules for accepted cut: `[]`

### Projected decomposition

- **Operator:** `->`
- **Groups:** `[['A'], ['C'], ['B']]`
- **Projected rules:** `[[], [], [End(B)]]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 3, 'n_empty': 1}`
  - `{'acts': ['C'], 'n_traces': 3, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`

### Base cases

- `A`
- `C`
- `B`

### Models

- **IM (no constraints):** `->( X( tau, 'A' ), X( tau, 'C' ), X( tau, 'B' ) )`
- **RIM:** `->( X( tau, 'A' ), X( tau, 'C' ), 'B' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `1.0`

---

## Example 7 — Enforce `Precedence(A, B)` although `B` appears without `A`

**Why:** The first trace violates precedence, but the model should require `A` before `B`.

### Input

- **Log:** `[['B'], ['A', 'B'], ['C', 'A', 'B']]`
- **Rules:** `[Precedence(A, B)]`

### Discovery summary

- Initial failed cut: `X`
- Accepted top-level cut: `->` with groups `[['A', 'C'], ['B']]`
- Unsatisfied rules for accepted cut: `[]`

### Repair / projection behavior

- Rule projection introduces `Existence(A)` on the left branch.

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B']]`
- **Projected rules:** `[[Existence(A)], []]`
- **Sublogs:**
  - `{'acts': ['A', 'C'], 'n_traces': 3, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 3, 'n_empty': 0}`

### Nested decomposition for `['A', 'C']`

- **Operator:** `->`
- **Groups:** `[['C'], ['A']]`
- **Projected rules:** `[[], [Existence(A)]]`
- **Sublogs:**
  - `{'acts': ['C'], 'n_traces': 2, 'n_empty': 1}`
  - `{'acts': ['A'], 'n_traces': 2, 'n_empty': 0}`

### Base cases

- `C`
- `A`
- `B`

### Models

- **IM (no constraints):** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), 'B' )`
- **RIM:** `->( ->( X( tau, 'C' ), 'A' ), 'B' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `1.0`

---

## Example 8 — Enforce `Response(A, B)` although some `A` is not followed by `B`

**Why:** Some occurrences of `A` are not followed by `B`, but the model should enforce that they are.

### Input

- **Log:** `[['A'], ['A', 'C'], ['A', 'B'], ['C']]`
- **Rules:** `[Response(A, B)]`

### Discovery summary

- Initial failed cut: `X`
- Accepted top-level cut: `->` with groups `[['A'], ['B', 'C']]`
- Unsatisfied rules for accepted cut: `[]`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A'], ['B', 'C']]`
- **Projected rules:** `[[], [Existence(B)]]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 4, 'n_empty': 1}`
  - `{'acts': ['B', 'C'], 'n_traces': 4, 'n_empty': 1}`

### Nested decomposition for `['B', 'C']`

- **Operator:** `X`
- **Groups:** `[['B'], ['C']]`
- **Sublogs:**
  - `{'acts': ['B'], 'n_traces': 1, 'n_empty': 0}`
  - `{'acts': ['C'], 'n_traces': 2, 'n_empty': 0}`

### Base cases

- `A`
- `B`
- `C`

### Models

- **IM (no constraints):** `->( X( tau, 'A' ), X( tau, X( 'B', 'C' ) ) )`
- **RIM:** `->( X( tau, 'A' ), 'B' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.5`

---

## Example 9 — Enforce `RespondedExistence(A, B)` although `A` occurs alone

**Why:** `A` appears without `B` in one trace, but the model should ensure that if `A` occurs, `B` occurs too.

### Input

- **Log:** `[['A'], ['A', 'B'], ['C'], ['B']]`
- **Rules:** `[RespondedExistence(A, B)]`

### Discovery summary

- Accepted top-level cut: `X` with groups `[['A', 'B'], ['C']]`
- Unsatisfied rules for accepted cut: `[]`

### Projected decomposition (top level)

- **Operator:** `X`
- **Groups:** `[['A', 'B'], ['C']]`
- **Projected rules:** `[[RespondedExistence(A, B)], []]`
- **Sublogs:**
  - `{'acts': ['A', 'B'], 'n_traces': 3, 'n_empty': 0}`
  - `{'acts': ['C'], 'n_traces': 1, 'n_empty': 0}`

### Nested decomposition for `['A', 'B']`

- **Operator:** `->`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[], [Existence(B)]]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 3, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`

### Base cases

- `A`
- `B`
- `C`

### Models

- **IM (no constraints):** `X( ->( X( tau, 'A' ), X( tau, 'B' ) ), 'C' )`
- **RIM:** `X( ->( X( tau, 'A' ), 'B' ), 'C' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `1.0`

---

## Example 10 — Enforce `NotSuccession(A, B)` although the log contains `A` then `B`

**Why:** The first trace violates the rule, but the model should disallow `B` after `A`.

### Input

- **Log:** `[['A', 'B'], ['A', 'C'], ['B']]`
- **Rules:** `[NotSuccession(A, B)]`

### Discovery summary

- Candidate cut `->` with groups `[['A'], ['C', 'B']]` was rejected because:
  - **Unsatisfied rules:** `['NotSuccession(A, B)']`
- After repair, accepted top-level cut: `X` with groups `[['A', 'C'], ['B']]`

### Projected decomposition (top level)

- **Operator:** `X`
- **Groups:** `[['A', 'C'], ['B']]`
- **Projected rules:** `[[], []]`
- **Sublogs:**
  - `{'acts': ['A', 'C'], 'n_traces': 1, 'n_empty': 0}`
  - `{'acts': ['B'], 'n_traces': 1, 'n_empty': 0}`

### Nested decomposition for `['A', 'C']`

- **Operator:** `->`
- **Groups:** `[['A'], ['C']]`
- **Projected rules:** `[[], []]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 1, 'n_empty': 0}`
  - `{'acts': ['C'], 'n_traces': 1, 'n_empty': 0}`

### Base cases

- `A`
- `C`
- `B`

### Models

- **IM (no constraints):** `->( X( tau, 'A' ), X( 'B', 'C' ) )`
- **RIM:** `X( ->( 'A', 'C' ), 'B' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.5`

---

## Example 11 — Combine `Init(A)` and `End(C)` with noisy traces

**Why:** The first trace does not start with `A` and one trace ends with `B`, but the model should start with `A` and end with `C`.

### Input

- **Log:** `[['B', 'A'], ['A', 'C'], ['A', 'B'], ['A', 'D', 'C']]`
- **Rules:** `[Init(A), End(C)]`

### Discovery summary

- Accepted top-level cut: `->` with groups `[['A', 'B'], ['C', 'D']]`
- Unsatisfied rules for accepted cut: `[]`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A', 'B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A)], [End(C)]]`
- **Sublogs:**
  - `{'acts': ['A', 'B'], 'n_traces': 4, 'n_empty': 0}`
  - `{'acts': ['C', 'D'], 'n_traces': 4, 'n_empty': 2}`

### Nested decomposition for `['A', 'B']`

- Candidate cut `+` with groups `[['A'], ['B']]` rejected because:
  - **Unsatisfied rules:** `['Init(A)']`
- Accepted replacement: `->` with groups `[['A'], ['B']]`

### Nested decomposition for `['C', 'D']`

- **Operator:** `->`
- **Groups:** `[['D'], ['C']]`
- **Projected rules:** `[[], [End(C)]]`

### Base cases

- `A`
- `B`
- `D`
- `C`

### Models

- **IM (no constraints):** `->( +( 'A', X( tau, 'B' ) ), X( tau, ->( X( tau, 'D' ), 'C' ) ) )`
- **RIM:** `->( ->( 'A', X( tau, 'B' ) ), ->( X( tau, 'D' ), 'C' ) )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.625`

---

## Example 12 — Combine `Existence(A)` and `AtMost1(A)`

**Why:** The model should require `A`, but also forbid repeating it.

### Input

- **Log:** `[['A', 'B', 'A'], ['B'], ['A', 'C']]`
- **Rules:** `[Existence(A), AtMost1(A)]`

### Discovery summary

- Accepted top-level cut: `->` with groups `[['A', 'B'], ['C']]`
- Nested accepted cut on `['A', 'B']`: `+` with groups `[['A'], ['B']]`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A', 'B'], ['C']]`
- **Projected rules:** `[[Existence(A), AtMost1(A)], []]`
- **Sublogs:**
  - `{'acts': ['A', 'B'], 'n_traces': 3, 'n_empty': 0}`
  - `{'acts': ['C'], 'n_traces': 3, 'n_empty': 2}`

### Nested decomposition for `['A', 'B']`

- **Operator:** `+`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[Existence(A), AtMost1(A)], []]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 3, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`

### Base cases

- `*( 'A', tau )`
- `B`
- `C`

### Models

- **IM (no constraints):** `->( +( X( tau, *( 'A', tau ) ), X( tau, 'B' ) ), X( tau, 'C' ) )`
- **RIM:** `->( +( 'A', X( tau, 'B' ) ), X( tau, 'C' ) )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.8`

---

## Example 13 — Combine `Precedence(A, B)` and `Response(A, B)`

**Why:** `B` should only happen after `A`, and every `A` should be followed by `B`, despite contradictory traces.

### Input

- **Log:** `[['B'], ['A'], ['A', 'B'], ['C', 'A', 'D']]`
- **Rules:** `[Precedence(A, B), Response(A, B)]`

### Discovery summary

- Accepted top-level cut: `->` with groups `[['A', 'C'], ['B', 'D']]`
- Rule projection yields:
  - left branch: `Existence(A)`
  - right branch: `Existence(B)`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B', 'D']]`
- **Projected rules:** `[[Existence(A)], [Existence(B)]]`
- **Sublogs:**
  - `{'acts': ['A', 'C'], 'n_traces': 4, 'n_empty': 1}`
  - `{'acts': ['B', 'D'], 'n_traces': 4, 'n_empty': 1}`

### Nested decomposition

- For `['A', 'C']`: `->` with groups `[['C'], ['A']]`
- For `['B', 'D']`: `X` with groups `[['B'], ['D']]`

### Base cases

- `C`
- `A`
- `B`
- `D`

### Models

- **IM (no constraints):** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), X( tau, X( 'B', 'D' ) ) )`
- **RIM:** `->( ->( X( tau, 'C' ), 'A' ), 'B' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.6666666666666666`

---

## Example 14 — Combine `Existence(A)` with `NotCoExistence(A, B)`

**Why:** The model should require `A` but still forbid `A` and `B` from appearing together.

### Input

- **Log:** `[['A'], ['B'], ['A', 'B'], ['C']]`
- **Rules:** `[Existence(A), NotCoExistence(A, B)]`

### Discovery summary

- Candidate top-level cut `X` with groups `[['A', 'B'], ['C']]` conflicts with:
  - `['Existence(A)']`
- After repair, subproblem on `['A', 'B']` yields candidate `->` with conflict:
  - `['NotCoExistence(A, B)']`
- Final repaired result collapses to the base case `A`.

### Models

- **IM (no constraints):** `X( ->( X( tau, 'A' ), X( tau, 'B' ) ), 'C' )`
- **RIM:** `A`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.0`

---

## Example 15 — Combine `CoExistence(A, B)` with `Init(A)`

**Why:** The model should start with `A` and enforce that `A` and `B` always occur together.

### Input

- **Log:** `[['A'], ['B'], ['A', 'B'], ['C', 'A', 'B']]`
- **Rules:** `[Init(A), CoExistence(A, B)]`

### Discovery summary

- Accepted top-level cut: `->` with groups `[['A', 'C'], ['B']]`
- Projected rules:
  - left branch: `[Init(A), Existence(A)]`
  - right branch: `[Existence(B)]`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B)]]`
- **Sublogs:**
  - `{'acts': ['A', 'C'], 'n_traces': 4, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 4, 'n_empty': 1}`

### Nested decomposition for `['A', 'C']`

- **Operator:** `->`
- **Groups:** `[['C'], ['A']]`

### Base cases

- `C`
- `A`
- `B`

### Models

- **IM (no constraints):** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), X( tau, 'B' ) )`
- **RIM:** `->( 'A', 'B' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.5`

---

## Example 16 — `Init(A)` + `CoExistence(A, B)` + `End(E)` with noisy optional behavior

**Why:** `A` should always be the first activity, `A` and `B` should always appear together, and every valid execution should end in `E`.

### Input

- **Log:** `[['A', 'B', 'D', 'E'], ['A', 'B', 'E'], ['B', 'E'], ['A', 'D', 'E'], ['A', 'B', 'D'], ['C', 'A', 'B', 'E']]`
- **Rules:** `[Init(A), CoExistence(A, B), End(E)]`

### Discovery summary

- Accepted top-level cut: `->` with groups `[['A', 'C'], ['B'], ['D'], ['E']]`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B'], ['D'], ['E']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B)], [], [End(E)]]`
- **Sublogs:**
  - `{'acts': ['A', 'C'], 'n_traces': 6, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 6, 'n_empty': 1}`
  - `{'acts': ['D'], 'n_traces': 6, 'n_empty': 3}`
  - `{'acts': ['E'], 'n_traces': 6, 'n_empty': 1}`

### Nested decomposition for `['A', 'C']`

- **Operator:** `->`
- **Groups:** `[['C'], ['A']]`

### Base cases

- `C`
- `A`
- `B`
- `D`
- `E`

### Models

- **IM (no constraints):** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), X( tau, 'B' ), X( tau, 'D' ), X( tau, 'E' ) )`
- **RIM:** `->( 'A', 'B', X( tau, 'D' ), 'E' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.5714285714285714`

---

## Example 17 — `Init(A)` + `CoExistence(A, B)` + `AtMost1(B)` + `NotSuccession(C, D)`

**Why:** `A` must start, `A` and `B` must always occur together, `B` cannot repeat, and `D` must not come after `C`.

### Input

- **Log:** `[['A', 'B', 'C'], ['A', 'B', 'D'], ['A', 'B', 'C', 'B'], ['B', 'A', 'C'], ['A', 'C'], ['A', 'B', 'C', 'D']]`
- **Rules:** `[Init(A), CoExistence(A, B), AtMost1(B), NotSuccession(C, D)]`

### Discovery summary

- Several candidate sequence cuts were rejected because they violated `NotSuccession(C, D)`.
- The final accepted structured solution uses:
  - top-level `->` with groups `[['A'], ['B'], ['C', 'D']]`
  - nested `X` on `['C', 'D']`

### Projected decomposition (final constrained structure)

- **Operator:** `->`
- **Groups:** `[['A'], ['B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B), AtMost1(B)], [NotSuccession(C, D)]]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 3, 'n_empty': 0}`
  - `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`
  - `{'acts': ['C', 'D'], 'n_traces': 3, 'n_empty': 0}`

### Nested decomposition for `['C', 'D']`

- **Operator:** `X`
- **Groups:** `[['C'], ['D']]`

### Fallback traces observed

- `FALLTHROUGH: flower`
- `FALLTHROUGH: once`

### Base cases

- `A`
- `B`
- `C`
- `D`

### Models

- **IM (no constraints):** `->( +( X( tau, *( 'B', tau ) ), ->( 'A', X( tau, 'C' ) ) ), X( tau, 'D' ) )`
- **RIM:** `->( 'A', 'B', X( 'C', 'D' ) )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.09090909090909091`

---

## Example 18 — `Init(A)` + `CoExistence(A, B)` + `Response(B, D)` + `NotCoExistence(C, D)`

**Why:** `A` must be first, `A` and `B` must occur together, every `B` must eventually be followed by `D`, and `C` and `D` must never appear together.

### Input

- **Log:** `[['A', 'B', 'D'], ['A', 'B', 'C', 'D'], ['B', 'D'], ['A', 'D'], ['A', 'B'], ['A', 'B', 'C']]`
- **Rules:** `[Init(A), CoExistence(A, B), Response(B, D), NotCoExistence(C, D)]`

### Discovery summary

- Candidate cut `->` with groups `[['A'], ['C', 'B'], ['D']]` rejected because:
  - **Unsatisfied rules:** `['NotCoExistence(C, D)']`
- Final accepted constrained structure:
  - `->` with groups `[['A'], ['B'], ['C', 'D']]`

### Projected decomposition (final constrained structure)

- **Operator:** `->`
- **Groups:** `[['A'], ['B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B)], [Existence(D), NotCoExistence(C, D)]]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 5, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 5, 'n_empty': 1}`
  - `{'acts': ['C', 'D'], 'n_traces': 5, 'n_empty': 1}`

### Base cases

- `A`
- `B`
- `D`

### Models

- **IM (no constraints):** `->( X( tau, 'A' ), X( tau, ->( 'B', X( tau, 'C' ) ) ), X( tau, 'D' ) )`
- **RIM:** `->( 'A', 'B', 'D' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.4`

---

## Example 19 — `Init(A)` + `CoExistence(A, B)` + `Precedence(B, C)` + `End(E)`

**Why:** `A` must start, `A` and `B` must always occur together, `C` may only happen if `B` already happened, and `E` must be the end activity.

### Input

- **Log:** `[['A', 'B', 'C', 'E'], ['A', 'B', 'E'], ['B', 'A', 'E'], ['A', 'C', 'E'], ['A', 'B', 'E', 'C'], ['A', 'B', 'D', 'C', 'E']]`
- **Rules:** `[Init(A), CoExistence(A, B), Precedence(B, C), End(E)]`

### Discovery summary

- Accepted top-level cut: `->` with groups `[['A', 'B'], ['D'], ['C', 'E']]`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A', 'B'], ['D'], ['C', 'E']]`
- **Projected rules:** `[[Init(A), CoExistence(A, B), Existence(B)], [], [End(E)]]`
- **Sublogs:**
  - `{'acts': ['A', 'B'], 'n_traces': 6, 'n_empty': 0}`
  - `{'acts': ['D'], 'n_traces': 6, 'n_empty': 5}`
  - `{'acts': ['C', 'E'], 'n_traces': 6, 'n_empty': 0}`

### Nested decomposition

- For `['A', 'B']`:
  - candidate `+` rejected because of `['Init(A)']`
  - accepted replacement: `->( 'A', 'B' )`
- For `['C', 'E']`:
  - candidate `+` rejected because of `['End(E)']`
  - accepted replacement: `->( X( tau, 'C' ), 'E' )`

### Base cases

- `A`
- `B`
- `D`
- `C`
- `E`

### Models

- **IM (no constraints):** `->( +( 'A', X( tau, 'B' ) ), X( tau, 'D' ), +( X( tau, 'C' ), 'E' ) )`
- **RIM:** `->( ->( 'A', 'B' ), X( tau, 'D' ), ->( X( tau, 'C' ), 'E' ) )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.35714285714285715`

---

## Example 20 — `Init(A)` + `CoExistence(A, B)` + `RespondedExistence(B, D)` + `AtMost1(B)`

**Why:** Whenever `B` appears, `D` must also appear somewhere in the same trace; `A` and `B` must always occur together; `A` must be first; and `B` cannot repeat.

### Input

- **Log:** `[['A', 'B', 'D'], ['A', 'B'], ['A', 'D'], ['B', 'D'], ['A', 'B', 'B', 'D'], ['A', 'B', 'C']]`
- **Rules:** `[Init(A), CoExistence(A, B), RespondedExistence(B, D), AtMost1(B)]`

### Discovery summary

- Accepted top-level cut: `->` with groups `[['A'], ['B'], ['C', 'D']]`

### Projected decomposition (top level)

- **Operator:** `->`
- **Groups:** `[['A'], ['B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B), AtMost1(B)], [Existence(D)]]`
- **Sublogs:**
  - `{'acts': ['A'], 'n_traces': 6, 'n_empty': 1}`
  - `{'acts': ['B'], 'n_traces': 6, 'n_empty': 1}`
  - `{'acts': ['C', 'D'], 'n_traces': 6, 'n_empty': 1}`

### Nested decomposition for `['C', 'D']`

- **Operator:** `X`
- **Groups:** `[['C'], ['D']]`

### Base cases

- `A`
- `*( 'B', tau )` observed in unconstrained base behavior
- `C`
- `D`

### Models

- **IM (no constraints):** `->( X( tau, 'A' ), X( tau, *( 'B', tau ) ), X( tau, X( 'C', 'D' ) ) )`
- **RIM:** `->( 'A', 'B', 'D' )`

### Similarity

- **Semantic similarity with IM (no constraints):** `0.3333333333333333`

---
