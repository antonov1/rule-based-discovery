# Rule-Based Inductive Miner Examples

Each example shows:

1. the **input log** and **constraints**,
2. the **main mining decision**,
3. the **projected constrained decomposition**,
4. the final **IM vs. RIM models**,
5. the resulting **semantic similarity** based on the footprint matrices.

---

## 1. Existence constraint: require `A`

### Goal

Enforce `Existence(A)` even though some traces do not contain `A`.

### Input

- **Log:** `[['B'], ['A', 'B'], ['B', 'C']]`
- **Rules:** `[Existence(A)]`

### Key mining decision

- `X` was attempted first and failed.
- The accepted cut is a **sequence**:
  `->` with groups `[['A'], ['B'], ['C']]`.

### Constraint projection

The existence constraint is pushed only to the branch containing `A`.

- **Operator:** `->`
- **Groups:** `[['A'], ['B'], ['C']]`
- **Projected rules:** `[[Existence(A)], [], []]`

### Projected sublogs

- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 2}`
- `B`: `{'acts': ['B'], 'n_traces': 3, 'n_empty': 0}`
- `C`: `{'acts': ['C'], 'n_traces': 3, 'n_empty': 2}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), 'B', X( tau, 'C' ) )`
- **RIM:** `->( 'A', 'B', X( tau, 'C' ) )`

### Effect of the constraint

The optional `A` in the unconstrained model becomes mandatory in the repaired model.

### Similarity

- **Semantic similarity with IM:** `1.0`

---

## 2. At-most-once constraint: forbid repeated `A`

### Goal

Enforce `AtMost1(A)` although the log contains repeated occurrences of `A`.

### Input

- **Log:** `[['A', 'B', 'A'], ['A'], ['B', 'A', 'C']]`
- **Rules:** `[AtMost1(A)]`

### Key mining decision

- The accepted top-level cut is:
  `->` with groups `[['A', 'B'], ['C']]`.
- Inside `['A', 'B']`, no standard structured cut was sufficient under the constraint.
- A **fallthrough** was applied:
  `strict tau`, yielding `->( X( tau, 'B' ), 'A' )`.

### Constraint projection

- **Top level operator:** `->`
- **Top level groups:** `[['A', 'B'], ['C']]`
- **Projected rules:** `[[AtMost1(A)], []]`

For the left branch:

- **Nested operator:** `->`
- **Nested groups:** `[['B'], ['A']]`
- **Projected rules:** `[[], [AtMost1(A)]]`

### Projected sublogs

Top level:

- `['A', 'B']`: `{'acts': ['A', 'B'], 'n_traces': 3, 'n_empty': 0}`
- `['C']`: `{'acts': ['C'], 'n_traces': 3, 'n_empty': 2}`

Nested:

- `B`: `{'acts': ['B'], 'n_traces': 2, 'n_empty': 1}`
- `A`: `{'acts': ['A'], 'n_traces': 2, 'n_empty': 0}`

### Resulting models

- **IM:** `->( *( ->( X( tau, 'B' ), 'A' ), tau ), X( tau, 'C' ) )`
- **RIM:** `->( ->( X( tau, 'B' ), 'A' ), X( tau, 'C' ) )`

### Effect of the constraint

The unconstrained model allows repetition through a loop; the repaired model removes that looping behavior and keeps only one occurrence of `A`.

### Similarity

- **Semantic similarity with IM:** `0.2`

---

## 3. Not-co-existence constraint: separate `A` and `B`

### Goal

Enforce `NotCoExistence(A, B)` although the log contains a trace where `A` and `B` occur together.

### Input

- **Log:** `[['A'], ['B'], ['A', 'B'], ['A']]`
- **Rules:** `[NotCoExistence(A, B)]`

### Key mining decision

- Candidate cut:
  `->` with groups `[['A'], ['B']]`
  was rejected.
- Rejection reason:
  `NotCoExistence(A, B)` is violated by sequencing `A` and `B`.
- Repair replaces the sequence by an **exclusive choice**:
  `X( 'A', 'B' )`.

### Constraint projection

- **Operator:** `X`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[], []]`

### Projected sublogs

- `A`: `{'acts': ['A'], 'n_traces': 2, 'n_empty': 0}`
- `B`: `{'acts': ['B'], 'n_traces': 1, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), X( tau, 'B' ) )`
- **RIM:** `X( 'A', 'B' )`

### Effect of the constraint

The repaired model forces a choice between `A` and `B`, ensuring they never appear together.

### Similarity

- **Semantic similarity with IM:** `0.0`

---

## 4. Co-existence constraint: require `A` and `B` together

### Goal

Enforce `CoExistence(A, B)` although the log contains traces with only `A` or only `B`.

### Input

- **Log:** `[['A'], ['A', 'B'], ['B'], ['A', 'B']]`
- **Rules:** `[CoExistence(A, B)]`

### Key mining decision

- Accepted cut:
  `->` with groups `[['A'], ['B']]`.

### Constraint projection

Co-existence is projected into branch-local existence requirements.

- **Operator:** `->`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[Existence(A)], [Existence(B)]]`

### Projected sublogs

- `A`: `{'acts': ['A'], 'n_traces': 4, 'n_empty': 1}`
- `B`: `{'acts': ['B'], 'n_traces': 4, 'n_empty': 1}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), X( tau, 'B' ) )`
- **RIM:** `->( 'A', 'B' )`

### Effect of the constraint

Both previously optional activities become mandatory, so valid executions must contain both `A` and `B`.

### Similarity

- **Semantic similarity with IM:** `1.0`

---

## 5. Init constraint: force `A` as the first activity

### Goal

Enforce `Init(A)` although one trace starts with `B`.

### Input

- **Log:** `[['B', 'A'], ['A', 'C'], ['A', 'B']]`
- **Rules:** `[Init(A)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'B'], ['C']]`
- In subproblem `['A', 'B']`, candidate cut:
  `+` with groups `[['A'], ['B']]`
  was rejected because it violates `Init(A)`.
- Repaired nested structure:
  `->( 'A', X( tau, 'B' ) )`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'B'], ['C']]`
- **Projected rules:** `[[Init(A)], []]`

Nested left branch:

- **Operator:** `->`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[Init(A)], []]`

### Projected sublogs

Top level:

- `['A', 'B']`: `{'acts': ['A', 'B'], 'n_traces': 3, 'n_empty': 0}`
- `['C']`: `{'acts': ['C'], 'n_traces': 3, 'n_empty': 2}`

Nested:

- `A`: `{'acts': ['A'], 'n_traces': 2, 'n_empty': 0}`
- `B`: `{'acts': ['B'], 'n_traces': 2, 'n_empty': 1}`

### Resulting models

- **IM:** `->( +( 'A', X( tau, 'B' ) ), X( tau, 'C' ) )`
- **RIM:** `->( ->( 'A', X( tau, 'B' ) ), X( tau, 'C' ) )`

### Effect of the constraint

The parallel/commutative behavior between `A` and `B` is replaced by a sequence that guarantees `A` comes first.

### Similarity

- **Semantic similarity with IM:** `0.4`

---

## 6. End constraint: force `B` as the last activity

### Goal

Enforce `End(B)` although one trace ends with `C`.

### Input

- **Log:** `[['A', 'B'], ['C', 'B'], ['A', 'C']]`
- **Rules:** `[End(B)]`

### Key mining decision

- Accepted cut:
  `->` with groups `[['A'], ['C'], ['B']]`

### Constraint projection

The end constraint is projected to the branch containing `B`.

- **Operator:** `->`
- **Groups:** `[['A'], ['C'], ['B']]`
- **Projected rules:** `[[], [], [End(B)]]`

### Projected sublogs

- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 1}`
- `C`: `{'acts': ['C'], 'n_traces': 3, 'n_empty': 1}`
- `B`: `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), X( tau, 'C' ), X( tau, 'B' ) )`
- **RIM:** `->( X( tau, 'A' ), X( tau, 'C' ), 'B' )`

### Effect of the constraint

`B` becomes mandatory at the end of every valid execution.

### Similarity

- **Semantic similarity with IM:** `1.0`

---

## 7. Precedence constraint: require `A` before `B`

### Goal

Enforce `Precedence(A, B)` although one trace contains `B` without `A`.

### Input

- **Log:** `[['B'], ['A', 'B'], ['C', 'A', 'B']]`
- **Rules:** `[Precedence(A, B)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'C'], ['B']]`
- Rule projection introduces `Existence(A)` on the left branch.
- Nested left branch is further decomposed as:
  `->` with groups `[['C'], ['A']]`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B']]`
- **Projected rules:** `[[Existence(A)], []]`

Nested left branch:

- **Operator:** `->`
- **Groups:** `[['C'], ['A']]`
- **Projected rules:** `[[], [Existence(A)]]`

### Projected sublogs

Top level:

- `['A', 'C']`: `{'acts': ['A', 'C'], 'n_traces': 3, 'n_empty': 1}`
- `['B']`: `{'acts': ['B'], 'n_traces': 3, 'n_empty': 0}`

Nested:

- `C`: `{'acts': ['C'], 'n_traces': 2, 'n_empty': 1}`
- `A`: `{'acts': ['A'], 'n_traces': 2, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), 'B' )`
- **RIM:** `->( ->( X( tau, 'C' ), 'A' ), 'B' )`

### Effect of the constraint

The repaired model ensures `B` can only happen after a branch that necessarily contains `A`.

### Similarity

- **Semantic similarity with IM:** `1.0`

---

## 8. Response constraint: require `B` after `A`

### Goal

Enforce `Response(A, B)` although some occurrences of `A` are not followed by `B`.

### Input

- **Log:** `[['A'], ['A', 'C'], ['A', 'B'], ['C']]`
- **Rules:** `[Response(A, B)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A'], ['B', 'C']]`
- Rule projection introduces `Existence(B)` on the right branch.
- The right branch is decomposed as an exclusive choice:
  `X` with groups `[['B'], ['C']]`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A'], ['B', 'C']]`
- **Projected rules:** `[[], [Existence(B)]]`

Nested right branch:

- **Operator:** `X`
- **Groups:** `[['B'], ['C']]`

### Projected sublogs

Top level:

- `A`: `{'acts': ['A'], 'n_traces': 4, 'n_empty': 1}`
- `['B', 'C']`: `{'acts': ['B', 'C'], 'n_traces': 4, 'n_empty': 1}`

Nested:

- `B`: `{'acts': ['B'], 'n_traces': 1, 'n_empty': 0}`
- `C`: `{'acts': ['C'], 'n_traces': 2, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), X( tau, X( 'B', 'C' ) ) )`
- **RIM:** `->( X( tau, 'A' ), 'B' )`

### Effect of the constraint

Because every `A` must be followed by `B`, the optional right branch collapses to mandatory `B`, removing `C` from the constrained result.

### Similarity

- **Semantic similarity with IM:** `0.5`

---

## 9. Responded-existence constraint: if `A` occurs, `B` must occur too

### Goal

Enforce `RespondedExistence(A, B)` although `A` appears alone in one trace.

### Input

- **Log:** `[['A'], ['A', 'B'], ['C'], ['B']]`
- **Rules:** `[RespondedExistence(A, B)]`

### Key mining decision

- Accepted top-level cut:
  `X` with groups `[['A', 'B'], ['C']]`
- The left branch is decomposed as:
  `->` with groups `[['A'], ['B']]`
- Rule projection introduces `Existence(B)` on the right side of that nested sequence.

### Constraint projection

Top level:

- **Operator:** `X`
- **Groups:** `[['A', 'B'], ['C']]`
- **Projected rules:** `[[RespondedExistence(A, B)], []]`

Nested left branch:

- **Operator:** `->`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[], [Existence(B)]]`

### Projected sublogs

Top level:

- `['A', 'B']`: `{'acts': ['A', 'B'], 'n_traces': 3, 'n_empty': 0}`
- `C`: `{'acts': ['C'], 'n_traces': 1, 'n_empty': 0}`

Nested:

- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 1}`
- `B`: `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`

### Resulting models

- **IM:** `X( ->( X( tau, 'A' ), X( tau, 'B' ) ), 'C' )`
- **RIM:** `X( ->( X( tau, 'A' ), 'B' ), 'C' )`

### Effect of the constraint

Within the `A/B` branch, `B` becomes mandatory whenever that branch is taken.

### Similarity

- **Semantic similarity with IM:** `1.0`

---

## 10. Not-succession constraint: forbid `B` after `A`

### Goal

Enforce `NotSuccession(A, B)` although the log contains the sequence `A` then `B`.

### Input

- **Log:** `[['A', 'B'], ['A', 'C'], ['B']]`
- **Rules:** `[NotSuccession(A, B)]`

### Key mining decision

- Candidate cut:
  `->` with groups `[['A'], ['B', 'C']]`
  was rejected because it violates `NotSuccession(A, B)`.
- Repair yields an exclusive choice:
  `X( ->( 'A', 'C' ), 'B' )`
- The constrained subproblem keeps `A` and `C` together and separates `B`.

### Constraint projection

- **Operator:** `X`
- **Groups:** `[['A', 'C'], ['B']]`
- **Projected rules:** `[[], []]`

Nested left branch:

- **Operator:** `->`
- **Groups:** `[['A'], ['C']]`
- **Projected rules:** `[[], []]`

### Projected sublogs

Top level:

- `['A', 'C']`: `{'acts': ['A', 'C'], 'n_traces': 1, 'n_empty': 0}`
- `B`: `{'acts': ['B'], 'n_traces': 1, 'n_empty': 0}`

Nested:

- `A`: `{'acts': ['A'], 'n_traces': 1, 'n_empty': 0}`
- `C`: `{'acts': ['C'], 'n_traces': 1, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), X( 'B', 'C' ) )`
- **RIM:** `X( ->( 'A', 'C' ), 'B' )`

### Effect of the constraint

The repaired model blocks every execution where `B` follows `A` by separating `B` into an alternative branch.

### Similarity

- **Semantic similarity with IM:** `0.5`

## 11. Combined `Init(A)` and `End(C)` under noisy traces

### Goal

Enforce both `Init(A)` and `End(C)` although the log contains traces that start with `B` or end with `B`.

### Input

- **Log:** `[['B', 'A'], ['A', 'C'], ['A', 'B'], ['A', 'D', 'C']]`
- **Rules:** `[Init(A), End(C)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'B'], ['C', 'D']]`
- On the left branch, candidate `+` over `[['A'], ['B']]` was rejected because of `Init(A)`.
- Repair on the left branch:
  `->( 'A', X( tau, 'B' ) )`
- On the right branch, `End(C)` is enforced through:
  `->( X( tau, 'D' ), 'C' )`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A)], [End(C)]]`

Nested left branch:

- **Operator:** `->`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[Init(A)], []]`

Nested right branch:

- **Operator:** `->`
- **Groups:** `[['D'], ['C']]`
- **Projected rules:** `[[], [End(C)]]`

### Projected sublogs

Top level:

- `['A', 'B']`: `{'acts': ['A', 'B'], 'n_traces': 4, 'n_empty': 0}`
- `['C', 'D']`: `{'acts': ['C', 'D'], 'n_traces': 4, 'n_empty': 2}`

Nested left:

- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 0}`
- `B`: `{'acts': ['B'], 'n_traces': 3, 'n_empty': 2}`

Nested right:

- `D`: `{'acts': ['D'], 'n_traces': 2, 'n_empty': 1}`
- `C`: `{'acts': ['C'], 'n_traces': 2, 'n_empty': 0}`

### Resulting models

- **IM:** `->( +( 'A', X( tau, 'B' ) ), X( tau, ->( X( tau, 'D' ), 'C' ) ) )`
- **RIM:** `->( ->( 'A', X( tau, 'B' ) ), ->( X( tau, 'D' ), 'C' ) )`

### Effect of the constraints

The repaired model simultaneously forces `A` to be first and `C` to be last, replacing optional unordered behavior by stricter sequencing on both sides.

### Similarity

- **Semantic similarity with IM:** `0.625`

---

## 12. Combined `Existence(A)` and `AtMost1(A)`

### Goal

Require `A` to occur, but never more than once.

### Input

- **Log:** `[['A', 'B', 'A'], ['B'], ['A', 'C']]`
- **Rules:** `[Existence(A), AtMost1(A)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'B'], ['C']]`
- Nested accepted cut on `['A', 'B']`:
  `+` with groups `[['A'], ['B']]`
- On the `A` branch, repeated occurrences are repaired into a single mandatory `A`.

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'B'], ['C']]`
- **Projected rules:** `[[Existence(A), AtMost1(A)], []]`

Nested left branch:

- **Operator:** `+`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[Existence(A), AtMost1(A)], []]`

### Projected sublogs

Top level:

- `['A', 'B']`: `{'acts': ['A', 'B'], 'n_traces': 3, 'n_empty': 0}`
- `['C']`: `{'acts': ['C'], 'n_traces': 3, 'n_empty': 2}`

Nested:

- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 1}`
- `B`: `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`

### Resulting models

- **IM:** `->( +( X( tau, *( 'A', tau ) ), X( tau, 'B' ) ), X( tau, 'C' ) )`
- **RIM:** `->( +( 'A', X( tau, 'B' ) ), X( tau, 'C' ) )`

### Effect of the constraints

The repaired model keeps `A` mandatory while removing the repetition that existed in the unconstrained loop-based behavior.

### Similarity

- **Semantic similarity with IM:** `0.8`

---

## 13. Combined `Precedence(A, B)` and `Response(A, B)`

### Goal

Ensure that `B` can only happen after `A`, and that every `A` is followed by `B`.

### Input

- **Log:** `[['B'], ['A'], ['A', 'B'], ['C', 'A', 'D']]`
- **Rules:** `[Precedence(A, B), Response(A, B)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'C'], ['B', 'D']]`
- Rule projection yields:
  - `Existence(A)` on the left branch
  - `Existence(B)` on the right branch
- Nested decompositions:
  - left: `->` with `[['C'], ['A']]`
  - right: `X` with `[['B'], ['D']]`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B', 'D']]`
- **Projected rules:** `[[Existence(A)], [Existence(B)]]`

Nested left:

- **Operator:** `->`
- **Groups:** `[['C'], ['A']]`
- **Projected rules:** `[[], [Existence(A)]]`

Nested right:

- **Operator:** `X`
- **Groups:** `[['B'], ['D']]`

### Projected sublogs

Top level:

- `['A', 'C']`: `{'acts': ['A', 'C'], 'n_traces': 4, 'n_empty': 1}`
- `['B', 'D']`: `{'acts': ['B', 'D'], 'n_traces': 4, 'n_empty': 1}`

Nested left:

- `C`: `{'acts': ['C'], 'n_traces': 3, 'n_empty': 2}`
- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 0}`

Nested right:

- `B`: `{'acts': ['B'], 'n_traces': 2, 'n_empty': 0}`
- `D`: `{'acts': ['D'], 'n_traces': 1, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), X( tau, X( 'B', 'D' ) ) )`
- **RIM:** `->( ->( X( tau, 'C' ), 'A' ), 'B' )`

### Effect of the constraints

Together, the two constraints collapse the optional right-side alternatives into mandatory `B`, yielding a much stricter aligned sequence.

### Similarity

- **Semantic similarity with IM:** `0.67`

---

## 14. Combined `Existence(A)` and `NotCoExistence(A, B)`

### Goal

Require `A`, but forbid `A` and `B` from appearing together.

### Input

- **Log:** `[['A'], ['B'], ['A', 'B'], ['C']]`
- **Rules:** `[Existence(A), NotCoExistence(A, B)]`

### Key mining decision

- Candidate top-level cut:
  `X` with groups `[['A', 'B'], ['C']]`
  conflicts with `Existence(A)`.
- In the `['A', 'B']` subproblem, candidate sequence
  `->` with `[['A'], ['B']]`
  conflicts with `NotCoExistence(A, B)`.
- Both levels repair to the same strict outcome:
  base case `A`.

### Constraint projection

No stable structured decomposition survives both constraints jointly; the result collapses directly to a single activity.

### Resulting models

- **IM:** `X( ->( X( tau, 'A' ), X( tau, 'B' ) ), 'C' )`
- **RIM:** `A`

### Effect of the constraints

The combination is highly restrictive: requiring `A` while forbidding coexistence with `B` leaves only the base activity `A` as a valid repair.

### Similarity

- **Semantic similarity with IM:** `0.0`

---

## 15. Combined `Init(A)` and `CoExistence(A, B)`

### Goal

Force the process to start with `A` and require `A` and `B` to appear together.

### Input

- **Log:** `[['A'], ['B'], ['A', 'B'], ['C', 'A', 'B']]`
- **Rules:** `[Init(A), CoExistence(A, B)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'C'], ['B']]`
- Projection yields:
  - left branch: `[Init(A), Existence(A)]`
  - right branch: `[Existence(B)]`
- Nested left branch:
  `->` with groups `[['C'], ['A']]`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B)]]`

Nested left:

- **Operator:** `->`
- **Groups:** `[['C'], ['A']]`

### Projected sublogs

Top level:

- `['A', 'C']`: `{'acts': ['A', 'C'], 'n_traces': 4, 'n_empty': 1}`
- `['B']`: `{'acts': ['B'], 'n_traces': 4, 'n_empty': 1}`

Nested:

- `C`: `{'acts': ['C'], 'n_traces': 3, 'n_empty': 2}`
- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), X( tau, 'B' ) )`
- **RIM:** `->( 'A', 'B' )`

### Effect of the constraints

The repaired model removes both the optional prefix `C` and the optionality of `B`, leaving only the mandatory ordered pair `A` then `B`.

### Similarity

- **Semantic similarity with IM:** `0.5`

---

## 16. Combined `Init(A)`, `CoExistence(A, B)`, and `End(E)`

### Goal

Require `A` first, enforce coexistence of `A` and `B`, and force the process to end with `E`.

### Input

- **Log:** `[['A', 'B', 'D', 'E'], ['A', 'B', 'E'], ['B', 'E'], ['A', 'D', 'E'], ['A', 'B', 'D'], ['C', 'A', 'B', 'E']]`
- **Rules:** `[Init(A), CoExistence(A, B), End(E)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'C'], ['B'], ['D'], ['E']]`
- Projected obligations:
  - `A`-branch: `Init(A)` plus `Existence(A)`
  - `B`-branch: `Existence(B)`
  - `E`-branch: `End(E)`
- Nested left branch:
  `->` with groups `[['C'], ['A']]`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'C'], ['B'], ['D'], ['E']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B)], [], [End(E)]]`

Nested left:

- **Operator:** `->`
- **Groups:** `[['C'], ['A']]`

### Projected sublogs

- `['A', 'C']`: `{'acts': ['A', 'C'], 'n_traces': 6, 'n_empty': 1}`
- `['B']`: `{'acts': ['B'], 'n_traces': 6, 'n_empty': 1}`
- `['D']`: `{'acts': ['D'], 'n_traces': 6, 'n_empty': 3}`
- `['E']`: `{'acts': ['E'], 'n_traces': 6, 'n_empty': 1}`

Nested:

- `C`: `{'acts': ['C'], 'n_traces': 5, 'n_empty': 4}`
- `A`: `{'acts': ['A'], 'n_traces': 5, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, ->( X( tau, 'C' ), 'A' ) ), X( tau, 'B' ), X( tau, 'D' ), X( tau, 'E' ) )`
- **RIM:** `->( 'A', 'B', X( tau, 'D' ), 'E' )`

### Effect of the constraints

The repaired model keeps only the optional middle behavior (`D`) while making start, coexistence, and end obligations explicit and mandatory.

### Similarity

- **Semantic similarity with IM:** `0.57`

---

## 17. Combined `Init(A)`, `CoExistence(A, B)`, `AtMost1(B)`, and `NotSuccession(C, D)`

### Goal

Require `A` to start, require `A` and `B` together, forbid repeated `B`, and forbid `D` after `C`.

### Input

- **Log:** `[['A', 'B', 'C'], ['A', 'B', 'D'], ['A', 'B', 'C', 'B'], ['B', 'A', 'C'], ['A', 'C'], ['A', 'B', 'C', 'D']]`
- **Rules:** `[Init(A), CoExistence(A, B), AtMost1(B), NotSuccession(C, D)]`

### Key mining decision

- Several candidate sequence cuts were explored and rejected due to `NotSuccession(C, D)`.
- The final accepted constrained structure is:
  `->` with groups `[['A'], ['B'], ['C', 'D']]`
- Rightmost branch is repaired as:
  `X( 'C', 'D' )`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A'], ['B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B), AtMost1(B)], [NotSuccession(C, D)]]`

Nested right branch:

- **Operator:** `X`
- **Groups:** `[['C'], ['D']]`
- **Projected rules:** `[[], []]`

### Projected sublogs

Top level:

- `A`: `{'acts': ['A'], 'n_traces': 3, 'n_empty': 0}`
- `B`: `{'acts': ['B'], 'n_traces': 3, 'n_empty': 1}`
- `['C', 'D']`: `{'acts': ['C', 'D'], 'n_traces': 3, 'n_empty': 0}`

Nested:

- `C`: `{'acts': ['C'], 'n_traces': 2, 'n_empty': 0}`
- `D`: `{'acts': ['D'], 'n_traces': 1, 'n_empty': 0}`

### Resulting models

- **IM:** `->( +( X( tau, *( 'B', tau ) ), ->( 'A', X( tau, 'C' ) ) ), X( tau, 'D' ) )`
- **RIM:** `->( 'A', 'B', X( 'C', 'D' ) )`

### Effect of the constraints

This is a strong repair: looping and order ambiguity disappear, and the tail is reduced to a conflict-free choice between `C` and `D`.

### Similarity

- **Semantic similarity with IM:** `0.09`

---

## 18. Combined `Init(A)`, `CoExistence(A, B)`, `Response(B, D)`, and `NotCoExistence(C, D)`

### Goal

Require `A` first, require `A` and `B` together, require every `B` to be followed by `D`, and forbid `C` and `D` from co-occurring.

### Input

- **Log:** `[['A', 'B', 'D'], ['A', 'B', 'C', 'D'], ['B', 'D'], ['A', 'D'], ['A', 'B'], ['A', 'B', 'C']]`
- **Rules:** `[Init(A), CoExistence(A, B), Response(B, D), NotCoExistence(C, D)]`

### Key mining decision

- Candidate cut
  `->` with groups `[['A'], ['C', 'B'], ['D']]`
  was rejected because of `NotCoExistence(C, D)`.
- The accepted constrained structure is:
  `->` with groups `[['A'], ['B'], ['C', 'D']]`
- Final repair simplifies to `->( 'A', 'B', 'D' )`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A'], ['B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B)], [Existence(D), NotCoExistence(C, D)]]`

### Projected sublogs

- `A`: `{'acts': ['A'], 'n_traces': 5, 'n_empty': 1}`
- `B`: `{'acts': ['B'], 'n_traces': 5, 'n_empty': 1}`
- `['C', 'D']`: `{'acts': ['C', 'D'], 'n_traces': 5, 'n_empty': 1}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), X( tau, ->( 'B', X( tau, 'C' ) ) ), X( tau, 'D' ) )`
- **RIM:** `->( 'A', 'B', 'D' )`

### Effect of the constraints

Positive dependencies and negative coexistence together eliminate the noisy optional behavior and collapse the model to a strict three-step sequence.

### Similarity

- **Semantic similarity with IM:** `0.4`

---

## 19. Combined `Init(A)`, `CoExistence(A, B)`, `Precedence(B, C)`, and `End(E)`

### Goal

Require `A` first, require `A` and `B` together, allow `C` only after `B`, and force `E` to be the final activity.

### Input

- **Log:** `[['A', 'B', 'C', 'E'], ['A', 'B', 'E'], ['B', 'A', 'E'], ['A', 'C', 'E'], ['A', 'B', 'E', 'C'], ['A', 'B', 'D', 'C', 'E']]`
- **Rules:** `[Init(A), CoExistence(A, B), Precedence(B, C), End(E)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A', 'B'], ['D'], ['C', 'E']]`
- On `['A', 'B']`, candidate `+` is rejected because of `Init(A)` and repaired to:
  `->( 'A', 'B' )`
- On `['C', 'E']`, candidate `+` is rejected because of `End(E)` and repaired to:
  `->( X( tau, 'C' ), 'E' )`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A', 'B'], ['D'], ['C', 'E']]`
- **Projected rules:** `[[Init(A), CoExistence(A, B), Existence(B)], [], [End(E)]]`

Nested `['A', 'B']`:

- **Operator:** `->`
- **Groups:** `[['A'], ['B']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B), Existence(B)]]`

Nested `['C', 'E']`:

- **Operator:** `->`
- **Groups:** `[['C'], ['E']]`
- **Projected rules:** `[[], [End(E)]]`

### Projected sublogs

Top level:

- `['A', 'B']`: `{'acts': ['A', 'B'], 'n_traces': 6, 'n_empty': 0}`
- `['D']`: `{'acts': ['D'], 'n_traces': 6, 'n_empty': 5}`
- `['C', 'E']`: `{'acts': ['C', 'E'], 'n_traces': 6, 'n_empty': 0}`

Nested `['A', 'B']`:

- `A`: `{'acts': ['A'], 'n_traces': 5, 'n_empty': 0}`
- `B`: `{'acts': ['B'], 'n_traces': 5, 'n_empty': 1}`

Nested `['C', 'E']`:

- `C`: `{'acts': ['C'], 'n_traces': 5, 'n_empty': 2}`
- `E`: `{'acts': ['E'], 'n_traces': 5, 'n_empty': 0}`

### Resulting models

- **IM:** `->( +( 'A', X( tau, 'B' ) ), X( tau, 'D' ), +( X( tau, 'C' ), 'E' ) )`
- **RIM:** `->( ->( 'A', 'B' ), X( tau, 'D' ), ->( X( tau, 'C' ), 'E' ) )`

### Effect of the constraints

The repaired model makes the prefix and suffix structurally ordered, while preserving only the optional middle activity `D`.

### Similarity

- **Semantic similarity with IM:** `0.36`

---

## 20. Combined `Init(A)`, `CoExistence(A, B)`, `RespondedExistence(B, D)`, and `AtMost1(B)`

### Goal

Require `A` first, require `A` and `B` together, require `D` whenever `B` occurs, and forbid repeated `B`.

### Input

- **Log:** `[['A', 'B', 'D'], ['A', 'B'], ['A', 'D'], ['B', 'D'], ['A', 'B', 'B', 'D'], ['A', 'B', 'C']]`
- **Rules:** `[Init(A), CoExistence(A, B), RespondedExistence(B, D), AtMost1(B)]`

### Key mining decision

- Accepted top-level cut:
  `->` with groups `[['A'], ['B'], ['C', 'D']]`
- Projected obligations:
  - `A`: `Init(A)` and `Existence(A)`
  - `B`: `Existence(B)` and `AtMost1(B)`
  - `['C', 'D']`: `Existence(D)`
- Rightmost branch is unconstrainedly decomposed as:
  `X` with groups `[['C'], ['D']]`

### Constraint projection

Top level:

- **Operator:** `->`
- **Groups:** `[['A'], ['B'], ['C', 'D']]`
- **Projected rules:** `[[Init(A), Existence(A)], [Existence(B), AtMost1(B)], [Existence(D)]]`

Nested right branch:

- **Operator:** `X`
- **Groups:** `[['C'], ['D']]`

### Projected sublogs

- `A`: `{'acts': ['A'], 'n_traces': 6, 'n_empty': 1}`
- `B`: `{'acts': ['B'], 'n_traces': 6, 'n_empty': 1}`
- `['C', 'D']`: `{'acts': ['C', 'D'], 'n_traces': 6, 'n_empty': 1}`

Nested:

- `C`: `{'acts': ['C'], 'n_traces': 1, 'n_empty': 0}`
- `D`: `{'acts': ['D'], 'n_traces': 4, 'n_empty': 0}`

### Resulting models

- **IM:** `->( X( tau, 'A' ), X( tau, *( 'B', tau ) ), X( tau, X( 'C', 'D' ) ) )`
- **RIM:** `->( 'A', 'B', 'D' )`

### Effect of the constraints

The repaired model removes both the optionality and repetition around `B`, and it makes the `D` obligation explicit, yielding a strict `A → B → D` core.

### Similarity

- **Semantic similarity with IM:** `0.33`

---

# Notes

The rule-based Inductive Miner behaves in the following way:

- **local unary rules** such as `Existence`, `Init`, `End`, and `AtMost1` are often enforced by making optional behavior mandatory or by removing repetition;
- **binary relational rules** such as `Precedence`, `Response`, and `RespondedExistence` are translated into **projected existence constraints** on one branch;
- **negative relation constraints** such as `NotCoExistence` and `NotSuccession` frequently force **structural repair**, replacing a sequence by an exclusive choice or collapsing behavior into a stricter branch structure.
- When **multiple constraints interact**, the repaired model often becomes much smaller and stricter than the unconstrained IM. In the most restrictive combinations, e.g., #14, the result may **collapse to a single activity** or a very short mandatory sequence.
