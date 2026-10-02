# OpenAI Agents / Codex integration pattern

Use the verifier as a **postcondition gate**, not as another planning tool.

1. Let the coding/automation agent perform the write, deploy, or external action.
2. Convert the intended final state into explicit public assertions.
3. Call the x402 endpoint from your payment-capable tool layer.
4. Only mark the parent task complete when `passed=true`.
5. Persist `verification_id` and `evidence_sha256` next to the run trace.

Example policy:

```text
Never treat a tool exit code or subagent "success" as completion.
After any externally visible mutation, run Agent Completion Verifier.
If passed=false, continue recovery instead of closing the task.
```

Example verification URL:

```text
https://vps-62-120.cloudhosting.lv:8443/postcondition-verify
 ?url=https%3A%2F%2Fexample.com%2Fhealth
 &expect_status=200
 &json_key=status
 &equals=ready
 &max_latency_ms=1500
 &logic=all
```

The first unpaid request returns x402 v2 payment requirements. Retry with any compatible x402 v2 client.
