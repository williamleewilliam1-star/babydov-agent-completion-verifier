# Curl example

This example only requests the x402 quote. It does **not** send a payment.

```bash
curl -i -G \
  'https://vps-62-120.cloudhosting.lv:8443/postcondition-verify' \
  --data-urlencode 'url=https://example.com' \
  --data-urlencode 'expect_status=200' \
  --data-urlencode 'contains=Example' \
  --data-urlencode 'content_type_contains=text/html' \
  --data-urlencode 'max_latency_ms=5000' \
  --data-urlencode 'logic=all'
```

Expected first response:

```text
HTTP/1.1 402 Payment Required
payment-required: <base64 x402 v2 requirements>
```

The payment requirement currently advertises:
- network: Base mainnet (`eip155:8453`)
- asset: USDC
- amount: 3000 atomic USDC = **$0.003**

An x402 v2 buyer signs the quoted payment and retries the **same request** with its payment proof. The paid response returns deterministic JSON including `passed`, per-check evidence, `verification_id`, and `evidence_sha256`.

For a zero-cost preview of the production evaluator:

```bash
curl -sS https://vps-62-120.cloudhosting.lv:8443/api/postcondition-demo | jq .
```
