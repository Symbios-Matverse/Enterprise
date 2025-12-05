import math

import pytest

from matverse.omega_gateway import (
    OmegaValidator,
    OmegaWeights,
    antifragile_metric,
    compute_omega,
    compute_qcvar,
    validate_governance_barrier,
)


def test_compute_omega_clamps_inputs_and_normalizes_weights():
    weights = OmegaWeights(psi=2, theta=1, cvar=1)
    result = compute_omega(psi=1.2, theta=-0.5, cvar=0.3, weights=weights)
    # psi should clamp to 1, theta to 0, cvar inverted from 0.3 -> 0.7
    expected = 1 * 0.5 + 0 * 0.25 + 0.7 * 0.25
    assert math.isclose(result, expected, rel_tol=1e-9)


def test_compute_qcvar_ignores_non_finite_and_takes_tail_mean():
    samples = [0.1, 0.2, 0.8, float("nan"), float("inf"), 0.5]
    qcvar = compute_qcvar(samples, alpha=0.5)
    # alpha=0.5 keeps worst 50% of values -> 0.8, 0.5, 0.2
    assert math.isclose(qcvar, (0.8 + 0.5 + 0.2) / 3, rel_tol=1e-9)


def test_validate_governance_barrier_combines_conditions():
    res = validate_governance_barrier(omega_score=0.95, qcvar=0.05, omega_threshold=0.9, qcvar_limit=0.1)
    assert res["production_ready"] is True
    res_fail = validate_governance_barrier(omega_score=0.8, qcvar=0.15, omega_threshold=0.9, qcvar_limit=0.1)
    assert res_fail["production_ready"] is False


def test_antifragile_metric_handles_stress_flag():
    metrics = antifragile_metric(before=0.6, after=0.8, stress_applied=True)
    assert metrics["is_antifragile"] is True
    assert math.isclose(metrics["antifragile_coefficient"], 0.2)
    metrics_no_stress = antifragile_metric(before=0.6, after=0.8, stress_applied=False)
    assert metrics_no_stress["antifragile_coefficient"] == 0.0


def test_validator_tracks_history_and_readiness():
    validator = OmegaValidator(omega_threshold=0.5, qcvar_limit=0.6, qcvar_alpha=0.8, max_history=3, min_samples=2)
    validator.validate_system(psi=0.7, theta=0.6, cvar=0.2)
    validator.validate_system(psi=0.65, theta=0.55, cvar=0.25)
    health = validator.get_system_health()
    assert health["sample_count"] == 2
    assert health["production_ready"] is True
    summary = validator.get_validation_summary()
    assert len(summary["history"]) == 2


def test_validator_enforces_max_history_and_defensive_copy():
    validator = OmegaValidator(max_history=2)
    validator.validate_system(psi=0.9, theta=0.9, cvar=0.05)
    validator.validate_system(psi=0.8, theta=0.85, cvar=0.1)
    validator.validate_system(psi=0.7, theta=0.8, cvar=0.15)

    summary = validator.get_validation_summary()
    assert len(summary["history"]) == 2
    # mutate returned history and ensure internal state unaffected
    summary["history"][0]["omega"] = 0
    refreshed = validator.get_validation_summary()
    assert refreshed["history"][0]["omega"] != 0


def test_validator_reset_clears_state_and_readiness():
    validator = OmegaValidator(min_samples=3)
    for _ in range(2):
        validator.validate_system(psi=0.9, theta=0.9, cvar=0.05)

    # Not enough samples yet; production_ready should be gated
    health_before = validator.get_system_health()
    assert health_before["sample_count"] == 2
    assert health_before["production_ready"] is False

    validator.reset()
    health_after = validator.get_system_health()
    assert health_after["sample_count"] == 0
    assert health_after["production_ready"] is False
