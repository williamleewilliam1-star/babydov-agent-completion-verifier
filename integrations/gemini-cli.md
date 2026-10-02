# Gemini-style tool runner integration

Subagents and tool runners can terminate because of turn limits, retries, or internal status mapping. Treat internal `success` / `GOAL` metadata as advisory until the externally observable state is verified.

Recommended parent-agent rule:

```text
If a subagent claims completion after a tool-producing action:
1. derive public postconditions,
2. verify them independently,
3. accept success only when passed=true.
```

Example checks:
- deployment URL returns 200
- response must contain the release marker
- JSON `version` equals the intended version
- redirect count remains below the expected bound
- latency stays below an operational threshold

The endpoint is read-only and public-URL-only, so it is safe to call as a completion gate without giving the verifier credentials to the target system.
