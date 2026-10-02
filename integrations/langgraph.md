# LangGraph integration pattern

Place verification in a terminal node between **action** and **done**.

Recommended graph:

```text
plan -> act -> verify_postcondition
                  | passed=true  -> done
                  | passed=false -> recover -> act
```

Useful state fields:

```json
{
  "verification_id": "pv_...",
  "evidence_sha256": "...",
  "passed": true,
  "failed_checks": []
}
```

Keep the verifier independent of the node that performed the mutation. This prevents a tool wrapper from validating its own optimistic success state.

For critical flows, combine several assertions with `logic=all`: expected status + JSON field + body hash or final URL.
