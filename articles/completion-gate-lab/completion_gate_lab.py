"""Offline completion-gate teaching example. Python 3.10+, standard library only.

Run: python3 completion_gate_lab.py
This is NOT the production verifier, an HTTP client, or a payment client.
All observations in the tests are synthetic. No network access is needed.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import unittest
from dataclasses import dataclass, replace
from enum import Enum


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Contract:
    resource: str
    revision: str
    action_at: float
    max_age_s: float = 30.0


@dataclass(frozen=True)
class Observation:
    resource: str
    observed_at: float
    status: int | None
    body: bytes | None
    transport_error: str | None = None


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str
    body_sha256: str | None = None


def finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON constant: " + value)


def evaluate(contract: Contract, observation: Observation, now: float) -> Decision:
    """Evaluate trusted-adapter evidence against intent fixed before the action.

    PASS alone permits completion. An invalid contract is a caller error.
    Invalid, stale, wrong-resource or unavailable evidence is INCONCLUSIVE.
    Fresh valid evidence that contradicts the contract is FAIL.
    """
    if not isinstance(contract.resource, str) or not contract.resource.strip():
        raise ValueError("resource must be a nonempty string")
    if not isinstance(contract.revision, str) or not contract.revision.strip():
        raise ValueError("revision must be a nonempty string")
    if not all(finite_number(x) for x in (contract.action_at, contract.max_age_s, now)):
        raise ValueError("contract times must be finite numbers, not booleans")
    if contract.max_age_s < 0 or now < contract.action_at:
        raise ValueError("invalid contract time interval")
    if observation.transport_error is not None:
        return Decision(Verdict.INCONCLUSIVE, "transport_unavailable")
    if observation.resource != contract.resource:
        return Decision(Verdict.INCONCLUSIVE, "wrong_resource")
    if not finite_number(observation.observed_at):
        return Decision(Verdict.INCONCLUSIVE, "invalid_observation_time")
    if not (contract.action_at <= observation.observed_at <= now
            and now - observation.observed_at <= contract.max_age_s):
        return Decision(Verdict.INCONCLUSIVE, "evidence_outside_time_window")
    if type(observation.status) is not int:
        return Decision(Verdict.INCONCLUSIVE, "invalid_status")
    if observation.status != 200:
        return Decision(Verdict.FAIL, "unexpected_http_status")
    if not isinstance(observation.body, bytes) or len(observation.body) > 65_536:
        return Decision(Verdict.INCONCLUSIVE, "missing_or_oversized_body")
    digest = hashlib.sha256(observation.body).hexdigest()
    try:
        payload = json.loads(observation.body.decode("utf-8"),
                             object_pairs_hook=unique_object,
                             parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError):
        return Decision(Verdict.INCONCLUSIVE, "invalid_json", digest)
    if (not isinstance(payload, dict) or type(payload.get("ready")) is not bool
            or type(payload.get("revision")) is not str):
        return Decision(Verdict.INCONCLUSIVE, "invalid_response_schema", digest)
    matched = payload["ready"] is True and payload["revision"] == contract.revision
    return Decision(Verdict.PASS if matched else Verdict.FAIL,
                    "contract_matches" if matched else "contract_mismatch", digest)


class CompletionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = Contract("docs-site", "r2", action_at=90.0)
        self.observation = Observation("docs-site", 99.0, 200,
                                       b'{"ready":true,"revision":"r2"}')

    def decision(self, **changes: object) -> Decision:
        return evaluate(self.contract, replace(self.observation, **changes), 100.0)

    def test_exact_match_passes(self) -> None:
        self.assertEqual(self.decision().verdict, Verdict.PASS)

    def test_not_ready_fails(self) -> None:
        self.assertEqual(self.decision(body=b'{"ready":false,"revision":"r2"}').verdict,
                         Verdict.FAIL)

    def test_wrong_revision_fails_even_with_http_200(self) -> None:
        self.assertEqual(self.decision(body=b'{"ready":true,"revision":"r1"}').verdict,
                         Verdict.FAIL)

    def test_unexpected_status_fails(self) -> None:
        self.assertEqual(self.decision(status=503).verdict, Verdict.FAIL)

    def test_transport_failure_is_not_success(self) -> None:
        self.assertEqual(self.decision(transport_error="timeout").verdict,
                         Verdict.INCONCLUSIVE)

    def test_wrong_resource_is_not_target_evidence(self) -> None:
        self.assertEqual(self.decision(resource="another-site").verdict,
                         Verdict.INCONCLUSIVE)

    def test_observation_before_action_is_inconclusive(self) -> None:
        self.assertEqual(self.decision(observed_at=89.0).verdict, Verdict.INCONCLUSIVE)

    def test_stale_observation_is_inconclusive(self) -> None:
        contract = replace(self.contract, action_at=0.0)
        observed = replace(self.observation, observed_at=69.0)
        self.assertEqual(evaluate(contract, observed, 100.0).verdict,
                         Verdict.INCONCLUSIVE)

    def test_future_observation_is_inconclusive(self) -> None:
        self.assertEqual(self.decision(observed_at=101.0).verdict, Verdict.INCONCLUSIVE)

    def test_freshness_boundary_is_inclusive(self) -> None:
        contract = replace(self.contract, action_at=0.0)
        observed = replace(self.observation, observed_at=70.0)
        self.assertEqual(evaluate(contract, observed, 100.0).verdict, Verdict.PASS)

    def test_observation_at_action_boundary_is_allowed(self) -> None:
        self.assertEqual(self.decision(observed_at=90.0).verdict, Verdict.PASS)

    def test_missing_body_is_inconclusive(self) -> None:
        self.assertEqual(self.decision(body=None).verdict, Verdict.INCONCLUSIVE)

    def test_oversized_body_is_inconclusive(self) -> None:
        self.assertEqual(self.decision(body=b" " * 65_537).verdict, Verdict.INCONCLUSIVE)

    def test_malformed_json_is_inconclusive(self) -> None:
        self.assertEqual(self.decision(body=b"{").verdict, Verdict.INCONCLUSIVE)

    def test_bad_utf8_is_inconclusive(self) -> None:
        self.assertEqual(self.decision(body=b"\xff").verdict, Verdict.INCONCLUSIVE)

    def test_duplicate_keys_are_rejected(self) -> None:
        raw = b'{"ready":false,"ready":true,"revision":"r2"}'
        self.assertEqual(self.decision(body=raw).verdict, Verdict.INCONCLUSIVE)

    def test_nonfinite_json_constant_is_rejected(self) -> None:
        raw = b'{"ready":true,"revision":"r2","latency":NaN}'
        self.assertEqual(self.decision(body=raw).verdict, Verdict.INCONCLUSIVE)

    def test_wrong_json_roots_are_rejected(self) -> None:
        for raw in (b"null", b"[]", b"42", b'"ready"'):
            with self.subTest(raw=raw):
                self.assertEqual(self.decision(body=raw).verdict, Verdict.INCONCLUSIVE)

    def test_missing_fields_are_rejected(self) -> None:
        for raw in (b"{}", b'{"ready":true}', b'{"revision":"r2"}'):
            with self.subTest(raw=raw):
                self.assertEqual(self.decision(body=raw).verdict, Verdict.INCONCLUSIVE)

    def test_truthy_non_boolean_ready_is_rejected(self) -> None:
        for value in ("true", "false", 1, 0, [], {}, None):
            with self.subTest(value=value):
                raw = json.dumps({"ready": value, "revision": "r2"}).encode()
                self.assertEqual(self.decision(body=raw).verdict, Verdict.INCONCLUSIVE)

    def test_invalid_status_types_are_rejected(self) -> None:
        for value in (True, None, 200.0, "200"):
            with self.subTest(value=value):
                self.assertEqual(self.decision(status=value).verdict, Verdict.INCONCLUSIVE)

    def test_nonfinite_observation_times_are_rejected(self) -> None:
        for value in (True, "99", None, float("nan"), float("inf"), 10**1000):
            with self.subTest(value=value):
                self.assertEqual(self.decision(observed_at=value).verdict,
                                 Verdict.INCONCLUSIVE)

    def test_invalid_contract_is_a_caller_error(self) -> None:
        changes = ({"revision": ""}, {"resource": " "}, {"max_age_s": -1},
                   {"max_age_s": True}, {"action_at": 101}, {"action_at": float("nan")})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                evaluate(replace(self.contract, **change), self.observation, 100.0)

    def test_hash_binds_the_observed_bytes(self) -> None:
        self.assertEqual(self.decision().body_sha256,
                         hashlib.sha256(self.observation.body).hexdigest())

    def test_inputs_are_not_mutated_and_result_is_repeatable(self) -> None:
        before = (repr(self.contract), repr(self.observation))
        self.assertEqual(self.decision(), self.decision())
        self.assertEqual(before, (repr(self.contract), repr(self.observation)))

    def test_six_dimension_matrix_64_distinct_cases(self) -> None:
        seen = set()
        for transport_ok, correct_resource, fresh, http_ok, ready, correct_revision in itertools.product(
                (False, True), repeat=6):
            bits = (transport_ok, correct_resource, fresh, http_ok, ready, correct_revision)
            seen.add(bits)
            observation = Observation(
                "docs-site" if correct_resource else "another-site",
                99.0 if fresh else 69.0, 200 if http_ok else 503,
                json.dumps({"ready": ready, "revision": "r2" if correct_revision else "r1"}).encode(),
                None if transport_ok else "timeout")
            contract = replace(self.contract, action_at=0.0)
            if not transport_ok or not correct_resource or not fresh:
                expected = Verdict.INCONCLUSIVE
            elif not http_ok or not ready or not correct_revision:
                expected = Verdict.FAIL
            else:
                expected = Verdict.PASS
            with self.subTest(bits=bits):
                self.assertEqual(evaluate(contract, observation, 100.0).verdict, expected)
        self.assertEqual(len(seen), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
