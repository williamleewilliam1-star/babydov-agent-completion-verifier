# Security model

Agent Completion Verifier is intentionally narrow.

## Allowed
- read-only HTTP/HTTPS observation of public targets
- bounded response sampling
- deterministic assertions over observable response state
- x402 payment for the verifier itself

## Rejected / unsupported
- loopback, private, link-local or otherwise SSRF-sensitive targets
- logging into target systems
- credentials for target services
- mutation of the target
- target-side payments or wallet signatures
- claims about hidden/private state

Invalid query input is rejected before the x402 quote whenever possible.

A `passed=true` result means only that the supplied public postconditions matched the point-in-time observation.
