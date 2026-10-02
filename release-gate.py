#!/usr/bin/env python3
"""BABYDOV Completion Verifier deterministic release gate.

Run from the production x402-seller environment where `server` exposes
`_postcondition_evaluate`.

Example:
  PYTHONPATH=. python release-gate.py --cases 5000000 --out release-gate.json
"""
import argparse, hashlib, json, time
from collections import Counter
import server

def mk(name, raw, probe, kwargs, passes):
    return {"name": name, "raw": raw, "probe": probe, "kwargs": kwargs, "passes": passes}

base_raw = b'{"status":"ready","version":2,"artifact":"published"}'
base_probe = {
    "status": 200,
    "final_url": "https://example.invalid/deployment/ready",
    "latency_ms": 42.0,
    "content_type": "application/json; charset=utf-8",
    "redirects": [],
}
sha = hashlib.sha256(base_raw).hexdigest()
S = []
S.append(mk("all_pass", base_raw, base_probe, dict(expect_status=200, contains="published", not_contains="error", json_key="status", equals="ready", expected_sha256=sha, final_url_contains="/ready", content_type_contains="APPLICATION/JSON", max_latency_ms=42, max_redirects=0, logic="all"), [1]*9))
S.append(mk("status_fail_all", base_raw, base_probe, dict(expect_status=201, contains="published", logic="all"), [0,1]))
S.append(mk("status_fail_any", base_raw, base_probe, dict(expect_status=201, contains="published", logic="any"), [0,1]))
S.append(mk("contains_fail", base_raw, base_probe, dict(contains="missing", logic="all"), [0]))
S.append(mk("not_contains_fail", base_raw, base_probe, dict(not_contains="published", logic="all"), [0]))
nested = b'{"a":{"b":[{"c":"yes"}]},"flag":true,"n":2}'
nested_probe = {**base_probe, "content_type": "application/json"}
S.append(mk("nested_json_pass", nested, nested_probe, dict(json_key="a.b.0.c", equals="yes", logic="all"), [1]))
S.append(mk("nested_json_missing", nested, nested_probe, dict(json_key="a.b.1.c", equals="yes", logic="all"), [0]))
S.append(mk("sha_pass", base_raw, base_probe, dict(expected_sha256=sha, logic="all"), [1]))
S.append(mk("sha_fail", base_raw, base_probe, dict(expected_sha256="0"*64, logic="all"), [0]))
S.append(mk("final_url_pass", base_raw, base_probe, dict(final_url_contains="deployment", logic="all"), [1]))
S.append(mk("content_type_casefold", base_raw, base_probe, dict(content_type_contains="JSON", logic="all"), [1]))
S.append(mk("latency_fail", base_raw, base_probe, dict(max_latency_ms=41.999, logic="all"), [0]))
redir_probe = {**base_probe, "redirects":[{"from":"a","to":"b","status":302},{"from":"b","to":"c","status":301}]}
S.append(mk("redirect_pass", base_raw, redir_probe, dict(max_redirects=2, logic="all"), [1]))
S.append(mk("redirect_fail", base_raw, redir_probe, dict(max_redirects=1, logic="all"), [0]))
S.append(mk("json_bool", nested, nested_probe, dict(json_key="flag", equals="true", logic="all"), [1]))
S.append(mk("any_all_fail", base_raw, base_probe, dict(expect_status=201, contains="absent", logic="any"), [0,0]))

def validate_output(sc, out):
    exp = sc["passes"]
    got = [bool(x.get("passed")) for x in out.get("checks", [])]
    expected_overall = (all(exp) if sc["kwargs"].get("logic","all") == "all" else any(exp)) if exp else False
    errs = []
    if got != [bool(x) for x in exp]: errs.append("check_pass_vector")
    if bool(out.get("passed")) != bool(expected_overall): errs.append("overall_pass")
    if out.get("check_count") != len(exp): errs.append("check_count")
    failed = [x.get("check") for x in out.get("checks", []) if not x.get("passed")]
    if out.get("failed_checks") != failed: errs.append("failed_checks")
    if out.get("evidence", {}).get("body_sha256") != hashlib.sha256(sc["raw"]).hexdigest(): errs.append("body_sha256")
    ev = out.get("evidence_sha256", "")
    if len(ev) != 64 or out.get("verification_id") != "pv_" + ev[:24]: errs.append("verification_id")
    return errs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=5_000_000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    errors = 0
    first = []
    counts = Counter()
    checksum = 0
    started = time.perf_counter()

    for i in range(a.cases):
        sc = S[i % len(S)]
        out = server._postcondition_evaluate(sc["probe"], sc["raw"], sc["raw"].decode(), **sc["kwargs"])
        es = validate_output(sc, out)
        counts[sc["name"]] += 1
        if es:
            errors += 1
            if len(first) < 20:
                first.append({"i": i, "scenario": sc["name"], "errors": es})
        checksum ^= int(out["evidence_sha256"][:16], 16)

    elapsed = time.perf_counter() - started
    artifact = {
        "schema_version": "babydov.postcondition_release_gate.v1",
        "cases": a.cases,
        "scenario_families": len(S),
        "errors": errors,
        "passed": errors == 0,
        "elapsed_seconds": round(elapsed, 3),
        "cases_per_second": round(a.cases / elapsed, 1),
        "scenario_counts": dict(sorted(counts.items())),
        "covered_checks": ["status","contains","not_contains","json_key_equals","body_sha256","final_url_contains","content_type_contains","max_latency_ms","max_redirects","logic_all","logic_any"],
        "first_errors": first,
        "checksum_xor64": f"{checksum:016x}",
        "production_helper": "server._postcondition_evaluate",
    }
    raw = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    artifact["artifact_sha256"] = hashlib.sha256(raw).hexdigest()
    with open(a.out, "w") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)
    print(json.dumps(artifact, sort_keys=True))
    raise SystemExit(0 if errors == 0 else 1)

if __name__ == "__main__":
    main()
