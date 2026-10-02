# Synthetic verification report

Release gate executed against the exact production helper `_postcondition_evaluate`.

- Cases: **5,000,000**
- Errors: **0**
- all-mode cases: **2,499,904**
- any-mode cases: **2,500,096**
- Runtime: **197.24 s**
- Throughput: **25,349.9 cases/s**

Each synthetic case varied nine assertion dimensions: status, positive text, negative text, dotted JSON equality, body SHA-256, final URL fragment, content-type fragment, latency bound, and redirect bound. The harness independently calculated the expected verdict and compared it with the production helper.

The run was entirely local/synthetic. It did **not** send five million network requests and did not spend USDC.

Additional smoke checks verified:
- valid public request returns HTTP 402 at 0.003 USDC
- invalid request is rejected with HTTP 400 before payment
- `logic=all` and `logic=any` behave correctly
- deterministic `verification_id` prefix and 64-hex `evidence_sha256`
- live OpenAPI, llms.txt, static x402 manifest and landing discovery
