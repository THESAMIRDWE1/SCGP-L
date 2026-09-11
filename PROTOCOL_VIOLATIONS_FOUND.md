# PROTOCOL VIOLATIONS FOUND — Implementation Halted

**Date:** 2026-09-11  
**Status:** IMPLEMENTATION HALTED BEFORE COMMIT  
**Reason:** Critical epistemic violations identified in Phase 2 draft

---

## Summary

Phase 2 implementation (agents, coordinator, generator, isolation) was drafted but NOT committed.

**Critical decision:** Do not push until violations are corrected.

The violations are not minor naming issues. They are core architectural mistakes that would allow the system to fool itself into reporting false discoveries.

---

## Violations Identified in Uncommitted Phase 2 Code

### 1. ❌ IsolationGate: Execution ≠ Verification

**Current broken logic:**
```python
if all(t.executed for t in self.test_results.values()):
    self.status = IsolationStatus.PROPERTIES_VERIFIED
```

**Problem:**
- `executed=True` means the probe ran, not that the property passed
- A test can execute and fail
- "Test ran" ≠ "Property verified"
- Unverified sandbox → candidate must not execute
- Current code does not distinguish PASS/FAIL result from execution attempt

**What it should be:**
For each required isolation property:
```
RAW_OBSERVATION:
  - property_id
  - test_executed: yes/no
  - test_result: PASS / FAIL / UNKNOWN
  - evidence (stdout, stderr, measurements)

CLASSIFICATION:
  - IF (test_executed AND test_result == PASS) → PROPERTY_VERIFIED
  - IF (NOT test_executed OR test_result != PASS) → PROPERTY_NOT_VERIFIED

CANDIDATE EXECUTION:
  - IF (all required properties == PROPERTY_VERIFIED) → allow execution
  - ELSE → BLOCKED_ISOLATION (no candidate runs)
```

**Current state:** NOT IMPLEMENTED CORRECTLY. Would allow execution without verified isolation.

---

### 2. ❌ ProcessExecutor: No Isolation Gate

**Current broken code:**
```python
def execute(self, cmd: list, input_data: str, ...) -> RawObservation:
    # Just executes the command
    # NO check if isolation is verified
    # NO BLOCKED_ISOLATION fallback
```

**Problem:**
- Candidate code is untrusted
- Could escape, read files, modify system, leak data
- ProcessExecutor calls subprocess.Popen directly
- No verification gate before execution
- No fallback to BLOCKED_ISOLATION if gate fails

**What it should be:**
```python
def execute(self, cmd: list, ..., isolation_gate: IsolationGate) -> RawObservation:
    if not isolation_gate.can_execute_candidate():
        return RawObservation(
            layer=RAW_OBSERVATION,
            crashed=True,
            stderr="BLOCKED_ISOLATION: Sandbox properties not verified"
        )
    # Only then: execute in subprocess
```

**Current state:** NO isolation gate passed. ALL execution paths bypass security.

---

### 3. ❌ Generator: API Key ≠ Reachable

**Current broken logic:**
```python
def _is_service_reachable(self) -> bool:
    # For cloud LLMs, assume reachable if API key present
    return self._has_api_key()
```

**Problem:**
- API key exists (env variable set) ≠ service is online
- Could be misconfigured, expired, rate-limited, backend down
- Current code maps: API_KEY_EXISTS → BACKEND_REACHABLE
- Then generation raises NotImplementedError anyway
- But status() reported "reachable" before attempted generation

**What it should be:**
```
BACKEND_CONFIGURED
  API key/credential present (not sufficient)
  
REACHABLE
  Actual health check performed, service responds
  
EXECUTED
  Generation function attempted
  
OBSERVED
  Raw output received
  
BLOCKED
  Unavailable or failed
```

No mapping from configuration to reachability.

**Current state:** FAKES reachability status without actual verification.

---

### 4. ❌ Agent._run_blind_phase(): Not Actually Blind

**Current broken architecture:**
```
Iteration 0:
  → Generate candidate
  → Freeze SHA256
  → Run training (public cases)
  → Run blind_phase (random inputs)
  → Pass/fail feedback to agent
  → Agent sees feedback and modifies candidate
→ [Loop back]
```

**Problem:**
- Same "blind" set used for feedback AND correction
- Agent receives pass/fail counts from this set
- Agent then modifies candidate to fit this set
- That set is no longer blind; it's a development set
- Need: Development set (can feedback), Final holdout (frozen, never fed to agent)

**What it should be:**
```
Development/Training:
  - Public training cases
  - Random development cases
  - Agent receives feedback from development results
  - Agent modifies candidate based on development feedback

Final Holdout:
  - Frozen before agent sees results
  - Never fed to agent
  - Evaluated once after convergence
  - Not used for iteration decisions
  - Genuine blind evaluation
```

**Current state:** ONLY ONE "blind" phase. Cannot distinguish development from final evaluation.

---

### 5. ❌ Blind Inputs: Hard-Coded Ontology (Integers 1..10000)

**Current broken code:**
```python
def _generate_blind_inputs(self, count: int) -> List[str]:
    rng = secrets.SystemRandom()
    inputs = set()
    while len(inputs) < count:
        val = rng.randint(1, 10000)  # ← ONTOLOGY LEAKAGE
        inputs.add(str(val))
    return sorted(inputs, key=lambda x: int(x))  # ← INT ASSUMPTION
```

**Problem:**
- Hard-codes integer domain (1..10000)
- Assumes inputs should be sorted as integers
- This IS a predefined ontology
- Should be completely external to the system
- Problem.test_case_generator must be supplied; not invented here

**What it should be:**
- Agent.py has NO test generation logic
- Problem.test_case_generator is mandatory and external
- Agent calls problem.generate_test_cases(count)
- System records: "using externally supplied generator"

**Current state:** ONTOLOGY EMBEDDED in core agent logic.

---

### 6. ❌ Convergence Analysis: Measurements → Claims

**Current broken code (Phase 2 draft):**
```python
# Layer 1: measurements
textual_sim = compute_textual_similarity(...)  # float, 0-1

# Layer 3: interpretation (but mixed into Layer 2 classification)
if textual_sim >= 0.35:
    convergence_class = "STRUCTURAL_CONVERGENCE_CANDIDATE"
```

**Problem:**
- Treats similarity score as structural evidence
- No interpretation separation
- "Similarity >= 0.35" is arbitrary threshold
- Does not distinguish:
  - TEXTUAL_SIMILARITY_OBSERVED (Layer 1)
  - SIMILARITY_THRESHOLD_MET (Layer 2, if threshold is predeclared)
  - POSSIBLE_STRUCTURAL_CONVERGENCE (Layer 3, inferred, separate)

**Current state:** LAYERS MIXED. Hard to audit where conclusions come from.

---

### 7. ❌ Discovery Classifications: Backwards Inference

**Current broken code (attempted):**
```python
if all(pr >= 0.90 for pr in pass_rates):
    convergence_class = "BEHAVIORAL_CONVERGENCE"
elif all(pr >= 0.50 for pr in pass_rates):
    convergence_class = "PARTIAL_CONVERGENCE"
else:
    convergence_class = "DIVERGENT_DISCOVERY"  # ← INVALID
```

**Problem:**
- Low pass rate ≠ divergent discovery
- Divergence requires evidence of different structures, not just poor performance
- "50% success" is arbitrary threshold with no justification
- Forces every outcome into one of three boxes
- Misuses "discovery" terminology

**Valid outcomes:**
```
BEHAVIORAL_CONVERGENCE
  Multiple agents achieve similar pass rates
  
BEHAVIORAL_DIVERGENCE
  Agents achieve different pass rates
  
INSUFFICIENT_DATA
  Cannot determine
  
UNKNOWN
  Need more information
  
NO_DISCOVERY
  Agents failed across the board
```

NOT: "DIVERGENT_DISCOVERY" from low pass rate.

**Current state:** MISCLASSIFIES low performance as evidence of divergent discovery.

---

### 8. ❌ No Distinction: Observation → Classification → Interpretation

**Example of current mixing:**
```python
# Raw observation
candidates_textually_similar = 0.35

# Should be kept separate:
# Layer 1 (raw): textual_similarity_score = 0.35
# Layer 2 (if threshold defined): meets_similarity_threshold = False (threshold 0.40)
# Layer 3 (interpretation): "May indicate similar design approaches" (INFERRED)

# Current code:
# (all mixed together in one classification function)
```

**Current state:** NO SYSTEMATIC SEPARATION of layers. Hard to audit epistemic status.

---

## What WAS Implemented (Phase 1 - Committed)

✅ **Committed (in repository):**
- `IMPLEMENTATION_SPEC.md` (v2.1)
- `scgp_l/__init__.py`
- `scgp_l/core/__init__.py`
- `scgp_l/core/types.py` — Data types with explicit layer labels (GOOD)
- `scgp_l/core/ledger.py` — Provenance recording (GOOD)
- `scgp_l/core/executor.py` — Process execution (LACKS ISOLATION GATE)
- `scgp_l/core/isolation_detector.py` — Tests isolation (LOGIC INCORRECT)
- `IMPLEMENTATION_STATUS.md` (earlier status report)

**Commit hash:** c5b031dcc4a2f7f872dc4a9c75fac522e0cfbbda

---

## What Was Drafted (Phase 2 - NOT Committed)

❌ **NOT committed (violations identified):**
- `scgp_l/core/generator.py` — Generator interface (STATUS LOGIC WRONG)
- `scgp_l/core/isolation_gate.py` — Isolation gate (LOGIC INCOMPLETE)
- `scgp_l/problems/__init__.py` — Problem definition (PARTIAL FIX, needs review)
- `scgp_l/problems/problem.py` — Problem abstraction (stub)
- `scgp_l/agents/__init__.py` — Agents module init (stub)
- `scgp_l/agents/agent.py` — Agent loop (ARCHITECTURE WRONG)
- `scgp_l/agents/coordinator.py` — Three-agent coordinator (ARCHITECTURE WRONG)

**Status:** Held locally. NOT pushed to repository.

---

## Required Corrections Before Next Push

### Tier 1: Critical (blocks all execution)

- [ ] **IsolationGate**: Implement RAW_OBSERVATION for each property (executed + result + evidence)
- [ ] **IsolationGate**: Implement proper CLASSIFICATION (all properties must have PASS)
- [ ] **ProcessExecutor**: Add isolation_gate parameter to execute()
- [ ] **ProcessExecutor**: Return BLOCKED_ISOLATION if gate fails
- [ ] **ProcessExecutor**: ALL candidate execution paths must check gate
- [ ] **Generator**: Remove API_KEY → REACHABLE mapping
- [ ] **Generator**: Implement actual status checks (not just config presence)
- [ ] **Generator**: Return BLOCKED_GENERATOR if status not REACHABLE

### Tier 2: Critical (architecture)

- [ ] **Agent**: Separate development set from final holdout
- [ ] **Agent**: Remove blind input generation from agent code
- [ ] **Agent**: Call problem.generate_test_cases() for all test input generation
- [ ] **Agent**: Never feed holdout results back to generator
- [ ] **Agent**: Add development/holdout split configuration
- [ ] **Problem**: Mark test_case_generator as EXTERNAL in serialization
- [ ] **Problem**: Raise error if test_case_generator not provided before use

### Tier 3: Critical (epistemic)

- [ ] **Coordinator**: Separate layers strictly (RAW / CLASS / INTERP)
- [ ] **Coordinator**: Use neutral classifications (avoid "DIVERGENT_DISCOVERY" from low performance)
- [ ] **Coordinator**: Mark all interpretations explicitly as INFERRED / ANALYTICAL_HYPOTHESIS
- [ ] **All code**: No arbitrary thresholds (95%, 90%, 50%) without explicit parameter documentation
- [ ] **All code**: Remove hard-coded ontology assumptions

### Tier 4: Validation

- [ ] **Test**: Execution blocked when isolation not verified
- [ ] **Test**: API key presence does NOT permit generation
- [ ] **Test**: Failed isolation property blocks candidate execution
- [ ] **Test**: Final holdout never fed to generator
- [ ] **Test**: No hard-coded input generation
- [ ] **Test**: Low pass rate ≠ discovery classification
- [ ] **Test**: Textual similarity ≠ structural convergence
- [ ] **Test**: External generator cannot be serialized/deserialized

---

## Decision: NO PUSH UNTIL CORRECTIONS

**DO NOT PUSH Phase 2 code until:**

1. ✗ All Tier 1 corrections implemented and tested
2. ✗ All Tier 2 corrections implemented and tested
3. ✗ All Tier 3 corrections implemented and tested
4. ✗ All Tier 4 validation tests execute and pass
5. ✗ Independent review confirms no layer mixing
6. ✗ Independent review confirms no ontology leakage
7. ✗ Independent review confirms isolation gate blocks properly

All of the above remain **NOT YET DONE**.

---

## Current Repository State (Factual)

```
✅ COMMITTED TO MAIN BRANCH (c5b031dcc4a2f7f872dc4a9c75fac522e0cfbbda):
  - IMPLEMENTATION_SPEC.md
  - IMPLEMENTATION_STATUS.md
  - README.md
  - scgp_l/__init__.py
  - scgp_l/core/__init__.py
  - scgp_l/core/types.py
  - scgp_l/core/ledger.py
  - scgp_l/core/executor.py
  - scgp_l/core/isolation_detector.py

❌ PHASE 2 DRAFT (NOT COMMITTED):
  - scgp_l/core/generator.py
  - scgp_l/core/isolation_gate.py
  - scgp_l/problems/__init__.py
  - scgp_l/problems/problem.py
  - scgp_l/agents/__init__.py
  - scgp_l/agents/agent.py
  - scgp_l/agents/coordinator.py

📄 THIS FILE:
  - PROTOCOL_VIOLATIONS_FOUND.md (just created)
```

---

## Epistemic Commitment

This implementation is being halted because:

**It is better to have working-but-incomplete code with known limitations than to have code that quietly violates its own epistemic contract.**

The current Phase 2 draft would allow the system to:
- Execute untrusted candidate code without isolation verification
- Report generators as available without actually testing them
- Treat low performance as evidence of discovery
- Mix observations with interpretations invisibly
- Encode ontology in "neutral" test generation

These are not minor bugs. They undermine the entire purpose of SCGP-L.

---

## Next Steps

1. **This session:** Halt implementation. Create this document. Report status.
2. **Review phase:** User reviews violations and correction requirements.
3. **When authorized:** Fix violations according to Tier 1-4 requirements.
4. **Validation:** Run test suite. Verify all corrections execute correctly.
5. **Final:** Only push after all tests pass and code review confirms epistemic correctness.

---

## Summary Table

| Component | Status | Committed | Issue |
|-----------|--------|-----------|-------|
| types.py | IMPLEMENTED | ✅ Yes | None identified |
| ledger.py | IMPLEMENTED | ✅ Yes | None identified |
| executor.py | IMPLEMENTED | ✅ Yes | No isolation gate |
| isolation_detector.py | IMPLEMENTED | ✅ Yes | Logic incorrect |
| generator.py | DRAFTED | ❌ No | API key ≠ reachable |
| isolation_gate.py | DRAFTED | ❌ No | Execution ≠ verification |
| problems/__init__.py | DRAFTED | ❌ No | Needs external generator |
| agent.py | DRAFTED | ❌ No | Not actually blind |
| coordinator.py | DRAFTED | ❌ No | Layers mixed |

---

## Status Code

**Overall Implementation Status:**
```
PHASE_1: PARTIALLY_IMPLEMENTED (7/9 files committed, 2 with violations)
PHASE_2: BLOCKED_PROTOCOL_VIOLATIONS (7 files drafted, 0 committed)
TEST_SUITE: NOT_YET_IMPLEMENTED

REPOSITORY_STATUS: HALT_BEFORE_NEXT_PUSH
REASON: Critical epistemic violations identified
AUTHORIZATION_REQUIRED: Yes, before proceeding with corrections
```
