# A green response isn't a finished deployment

**Ivan Babydov / BABYDOV Labs · 2 October 2026**

*AI-assisted technical writing sample. The companion example and its tests were implemented and executed by an AI coding assistant with the operator's authorization. They have not undergone independent human engineering review. This is a new educational sample, not a previously commissioned article or a production incident report.*

A deployment agent asks a status endpoint whether the site is ready. The endpoint returns HTTP 200 and `{"ready":true,"revision":"r1"}`. The agent announces success.

There is one problem: the requested deployment was `r2`.

Nothing about that response requires HTTP to be broken. The server successfully answered the request; it did not certify the agent's larger assignment. HTTP 200 describes the outcome of the request and its method-specific response, not an arbitrary workflow's acceptance criteria. [1]

The useful fix is not a more emphatic instruction to “double-check.” It is a small decision boundary: record what must become true before the action, collect an observation afterward, and evaluate that observation without letting the agent rewrite the target.

This is the idea behind the completion-gate policy in this repository. The example below isolates that decision boundary. It deliberately does **not** claim to test the hosted verifier, fetch live URLs, or validate payments.

## Freeze the target before looking at the result

The lab uses a contract with four fields: resource identity, expected revision, action time, and maximum observation age. Its values come from the requested task, not from whichever response happened to arrive.

That ordering matters. Reading `r1` and then setting the expectation to `r1` creates a test that passes for the wrong reason. A verifier cannot rescue an acceptance criterion derived from the result it is supposed to challenge.

Here is a complete, runnable use of the companion module. Run it from the directory containing `completion_gate_lab.py`:

```python
from completion_gate_lab import Contract, Observation, Verdict, evaluate

contract = Contract("docs-site", "r2", action_at=90.0, max_age_s=30.0)
observed = Observation(
    resource="docs-site",
    observed_at=99.0,
    status=200,
    body=b'{"ready":true,"revision":"r1"}',
)
decision = evaluate(contract, observed, now=100.0)
print(decision.verdict.value, decision.reason)
assert decision.verdict is Verdict.FAIL
```

The output is `fail contract_mismatch`. Changing the observation to the requested revision makes this particular contract pass. Changing the contract to excuse the old revision defeats the point.

The timestamps are synthetic values on one observer's time axis. A real collector must use a consistent clock and trusted resource mapping; it cannot accept either from arbitrary page content.

## “Not verified” is not the same as “wrong”

The evaluator returns three outcomes. **Pass** means fresh, parseable evidence matches the contract. **Fail** means usable evidence contradicts a required condition. **Inconclusive** means the evidence cannot establish the result.

A timeout belongs in the third category. So does an observation of the wrong resource, an old snapshot, an invalid response schema, or a body that cannot be decoded. None permits completion. But treating them all as a definitive failed deployment would also discard useful information.

The distinction tells the orchestrator what to investigate. A valid `r1` observation calls for checking the deployment. An unreadable response calls for checking the evidence path. Neither authorizes an automatic redeploy: retries need their own limits, and repeating a side-effecting operation needs an idempotency policy.

In this example, a fresh HTTP 503 is a failure because HTTP 200 is itself part of the contract. This is a policy decision, not a universal claim that every 503 proves an entire product is down.

## Parse the evidence, not its optimism

There is a tempting shortcut: turn a returned field into a Boolean. In Python, a nonempty string such as `"false"` is truthy. The standard library's truth-value rules are useful; they just are not a substitute for a response schema. [2]

The example requires `ready` to be an actual Boolean and `revision` to be a string. Missing fields, `ready: 1`, and a JSON list where an object was expected are inconclusive. Additional fields are allowed, but they cannot substitute for the required ones.

Parsing also has policy choices. Python's JSON decoder accepts repeated object names by keeping the last value, and it accepts non-finite constants by default. [3] For this evidence format, that is too ambiguous. The lab rejects duplicate keys and non-finite constants, enforces UTF-8, and caps the supplied body at 65,536 bytes. A real HTTP adapter must apply a streaming size limit **before** buffering; this pure function only limits what it will parse.

A SHA-256 digest records which response bytes were evaluated. It is not a signature, proof of origin, proof of settlement, or evidence that the bytes were true. Those are different claims with different verification requirements.

## Test the false success paths

The companion file includes 26 named tests. One of those tests enumerates 64 distinct combinations of six binary dimensions: transport availability, resource identity, freshness, HTTP status, readiness, and revision match. The 64 combinations are **inside** that test; they are not 64 additional named tests.

Only one matrix combination passes. Missing or unsuitable evidence is inconclusive. Suitable evidence with any required condition unmet fails. The expected results are declared by a separate decision table in the test, not calculated by calling the function under test again.

Other tests cover the edges the binary matrix misses: observations just at the time boundary, future timestamps, malformed JSON, duplicate keys, invalid UTF-8, oversized bodies, missing fields, and truthy non-Booleans. Invalid contracts raise a caller error rather than quietly producing a success verdict.

The extra check is to make the code wrong on purpose. The QA runner evaluates four isolated local variants: ignoring HTTP status, replacing the final conjunction with an OR, ignoring evidence age, and ignoring release identity. Each variant must cause assertion failures rather than merely crash.

The recorded run used Python 3.13.5 on Linux:

| Check | Observed result |
| --- | --- |
| Syntax parsing and compilation | Passed |
| Unmodified example | 26 tests; 0 failures; 0 errors |
| Six-dimensional matrix | All 64 cases met their declared verdict |
| Four deliberately incorrect variants | All four caught by assertions; no test errors |
| Network socket creation during the suites | Disabled by the QA runner |

The full [source](completion_gate_lab.py), [reproduction runner](run_lab_qa.py), and [machine-readable report](qa-report.json) are beside this article. From this directory:

```bash
python3 completion_gate_lab.py
python3 run_lab_qa.py
```

Both commands use only the Python standard library. The second writes a new `qa-report.json`, including the source hash, so a reader can tell exactly which example produced the result. Python 3.10+ syntax is used; only the recorded 3.13.5 environment was executed in this run.

## What this gate still cannot prove

The pure evaluator trusts its adapter to identify the resource and timestamp the observation honestly. It does not resolve URLs, authenticate servers, prevent unsafe fetch destinations, or examine cache headers. A recently received cached response is not necessarily recently generated evidence. Those responsibilities remain in the collector and its tests.

It also verifies one observation, not continuing availability. Another deployment can supersede the result a moment later. Nor does `r2` on one status endpoint prove that every edge location serves the same release. A multi-region acceptance criterion needs multi-region evidence.

These limitations are not reasons to remove the gate. They are reasons to keep its claim narrow. “This observation met this contract” is both useful and testable. “The agent finished everything correctly” is not what this lab establishes.

My design preference is a small gate that can explain its refusal over a larger green badge that cannot explain its evidence. Freeze the target, preserve uncertainty, and make at least one test fail when the evaluator starts accepting the wrong result. That turns “done” from a conversational habit into a decision a reviewer can inspect.

### Sources and evidence

[1] [RFC 9110, section 15.3.1 — 200 OK](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.1).

[2] [Python documentation — Truth Value Testing](https://docs.python.org/3/library/stdtypes.html#truth-value-testing).

[3] [Python documentation — JSON decoder compliance, repeated names and non-finite values](https://docs.python.org/3/library/json.html#standard-compliance-and-interoperability).

Experimental results refer only to the accompanying lab and `qa-report.json`. No earlier production benchmark or payment claim was reproduced for this article.
