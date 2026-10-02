# Agent completion gate

Use the verifier as a separate acceptance step, not as another action tool.

```text
perform_action()
        |
        v
define observable postconditions
        |
        v
BABYDOV Completion Verifier
        |
   +----+----+
   |         |
passed     failed
   |         |
close      repair /
task       retry
```

## Pseudocode

```python
result = perform_external_action()

verification_url = build_completion_verification_url(
    url="https://service.example/health",
    expect_status=200,
    json_key="release.version",
    equals=EXPECTED_VERSION,
    max_latency_ms=2000,
    logic="all",
)

verification = x402_client.get(verification_url)

if not verification["passed"]:
    raise CompletionGateFailed(
        verification["failed_checks"],
        verification["verification_id"],
    )

trace["completion_verification_id"] = verification["verification_id"]
trace["completion_evidence_sha256"] = verification["evidence_sha256"]
return "done"
```

## Design principle

The actor that performed the write should not be the only source claiming the write succeeded. Independent read-back reduces false completion, stale-state assumptions, and silent tool failures.

The verifier is read-only and public-URL-only. It does not log in to the target, mutate it, or pay it.
