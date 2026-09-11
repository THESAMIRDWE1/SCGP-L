# SCGP-L Implementation Architecture v2.1 — Three-Layer Epistemic Separation

**Date:** 2026-09-11  
**Implementation Status:** ACTIVE  
**Objective:** Three-agent autonomous discovery with strict epistemological layering

---

## Core Epistemological Principle

All statements and records must be classified into exactly ONE of three layers:

### Layer 1: RAW OBSERVATION
**What the verifier directly measures:**
- Input/output agreement: yes/no
- Execution success/failure: yes/no, with exit code
- Timing: wall-clock time in seconds
- Hash values: SHA256, BLAKE2b, etc.
- Return codes and signal numbers
- Counts: number of tests passed, failed, timed out, crashed

**Properties:**
- Reproducible by identical execution
- Independent of observer interpretation
- No semantic judgment
- No classification implied

### Layer 2: CLASSIFICATION
**Researcher-defined experimental protocol conclusions:**
- PASS / FAIL (for individual tests)
- CONVERGED / NOT_CONVERGED (explicit rule required)
- BLOCKED / NOT_BLOCKED (environmental gate)
- TRANSFER_SUCCESS / PARTIAL_TRANSFER / TRANSFER_FAILURE
- BEHAVIORAL_CONVERGENCE / BEHAVIORAL_DIVERGENCE

**Properties:**
- Requires explicit experimental rule/threshold
- Never a discovery claim
- Justified in EXPERIMENTAL_PARAMETERS.md

### Layer 3: INTERPRETATION
**Analyst propositions (post-hoc, separate):**
- Marked explicitly as INFERRED or ANALYTICAL_HYPOTHESIS
- Cannot be derived from single observation
- Requires independent testing to validate

---

## Terminal Discovery Classifications

One of exactly nine outcomes:

```
BLOCKED_ISOLATION              - Environmental gate failed, experiment incomplete
BLOCKED_GENERATOR              - Generator backend unavailable
NO_DISCOVERY                   - Hypotheses failed to achieve threshold
BEHAVIORAL_CONVERGENCE         - Multiple agents solve similarly well (NOT structural)
PARTIAL_TRANSFER               - Hypothesis transfers partially to different problem
DIVERGENT_DISCOVERY            - Different solutions, similar performance
CONVERGENT_BEHAVIORAL          - High pass rate + output equivalence (NOT structural)
STRUCTURAL_CONVERGENCE_CANDIDATE - Metrics align, requires independent validation
UNKNOWN_INSUFFICIENT_DATA      - Cannot classify
```

---

## Critical Rules

1. **Layer 1 only:** Verifier outputs raw observations with explicit layer label
2. **No interpretation in measurement:** Classification uses explicit rules
3. **Diagnosis is optional:** Agent commentary never fed to analysis
4. **No predefined ontology:** Problems and solutions unconstrained
5. **Strict separation:** Raw data, classifications, interpretations physically separate
6. **Discovery requires multiple gates:** No single metric proves discovery
7. **Record raw first:** Never overwrite observations with interpretations
8. **Label explicitly:** Every claim states its layer: RAW_OBSERVATION|CLASSIFICATION|INTERPRETATION
