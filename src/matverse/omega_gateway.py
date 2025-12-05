"""Omega Gateway primitives for MatVerse.

This module implements small, dependency-light utilities for calculating
Omega scores, estimating Quantum CVaR, validating governance thresholds,
tracking antifragility, and performing rolling validation through
:class:`OmegaValidator`.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Dict, Iterable, List, MutableSequence, Optional


@dataclass(frozen=True)
class OmegaWeights:
    """Weighting factors for the Omega score.

    The values are normalized at runtime so callers do not need to supply
    perfectly scaled numbers. Defaults bias epistemic strength and latency
    equally while slightly discounting risk.
    """

    psi: float = 0.45
    theta: float = 0.35
    cvar: float = 0.20

    def normalized(self) -> "OmegaWeights":
        total = max(self.psi + self.theta + self.cvar, 1e-12)
        return OmegaWeights(self.psi / total, self.theta / total, self.cvar / total)


_DEF_MIN = 0.0
_DEF_MAX = 1.0


def _clamp(value: float, min_value: float = _DEF_MIN, max_value: float = _DEF_MAX) -> float:
    if not isfinite(value):
        return min_value
    return max(min_value, min(max_value, value))


def compute_omega(
    *, psi: float, theta: float, cvar: float, weights: Optional[OmegaWeights] = None
) -> float:
    """Compute a normalized Omega score.

    - ``psi`` and ``theta`` are clamped to ``[0, 1]``.
    - ``cvar`` is clamped to ``[0, 1]`` and inverted so that smaller risk increases
      the final score.
    - weights are normalized automatically. If none are provided, defaults are used.
    """

    weights = (weights or OmegaWeights()).normalized()

    safe_psi = _clamp(psi)
    safe_theta = _clamp(theta)
    safe_cvar = 1.0 - _clamp(cvar)

    omega = safe_psi * weights.psi + safe_theta * weights.theta + safe_cvar * weights.cvar
    return _clamp(omega)


def compute_qcvar(samples: Iterable[float], *, alpha: float = 0.95) -> float:
    """Compute a simple tail-mean Quantum CVaR estimator.

    Non-finite samples are ignored. If no valid samples remain, returns ``0.0``.
    The ``alpha`` parameter is clamped to ``(0, 1)`` and determines the coverage
    level: the function averages the worst ``(1 - alpha)`` fraction of samples.
    """

    clamped_alpha = _clamp(alpha, 1e-6, 1 - 1e-6)
    clean: List[float] = [value for value in samples if isfinite(value)]
    if not clean:
        return 0.0

    sorted_values = sorted(clean, reverse=True)
    # Use an inclusive tail size so small sample sets retain signal even when
    # alpha is high (e.g., alpha=0.95 on fewer than 20 samples).
    tail_count = max(1, int(len(sorted_values) * (1 - clamped_alpha)) + 1)
    tail_slice = sorted_values[:tail_count]
    return sum(tail_slice) / len(tail_slice)


def validate_governance_barrier(
    *,
    omega_score: float,
    qcvar: float,
    omega_threshold: float = 0.9,
    qcvar_limit: float = 0.1,
) -> Dict[str, object]:
    """Validate Omega and QCVaR scores against governance thresholds."""

    safe_threshold = _clamp(omega_threshold)
    safe_qcvar_limit = _clamp(qcvar_limit)
    omega_ok = _clamp(omega_score) >= safe_threshold
    qcvar_ok = _clamp(qcvar) <= safe_qcvar_limit

    return {
        "omega_ok": omega_ok,
        "qcvar_ok": qcvar_ok,
        "production_ready": bool(omega_ok and qcvar_ok),
        "omega_threshold": safe_threshold,
        "qcvar_limit": safe_qcvar_limit,
    }


def antifragile_metric(*, before: float, after: float, stress_applied: bool) -> Dict[str, float | bool]:
    """Compute antifragility metrics given before/after measurements."""

    safe_before = _clamp(before)
    safe_after = _clamp(after)
    improvement = safe_after - safe_before
    coefficient = improvement if stress_applied else 0.0
    return {
        "improvement": improvement,
        "is_antifragile": stress_applied and improvement > 0,
        "antifragile_coefficient": coefficient,
    }


class OmegaValidator:
    """Rolling governance validator with defensive history handling."""

    def __init__(
        self,
        *,
        omega_threshold: float = 0.9,
        qcvar_limit: float = 0.1,
        qcvar_alpha: float = 0.9,
        max_history: int = 100,
        min_samples: int = 5,
    ) -> None:
        self.omega_threshold = _clamp(omega_threshold)
        self.qcvar_limit = _clamp(qcvar_limit)
        self.qcvar_alpha = _clamp(qcvar_alpha, 1e-6, 1 - 1e-6)
        self.max_history = max(1, int(max_history))
        self.min_samples = max(1, int(min_samples))
        self._history: List[Dict[str, float]] = []
        self._omega_history: List[float] = []
        self._cvar_history: List[float] = []

    def _trim_history(self) -> None:
        while len(self._history) > self.max_history:
            self._history.pop(0)
        while len(self._omega_history) > self.max_history:
            self._omega_history.pop(0)
        while len(self._cvar_history) > self.max_history:
            self._cvar_history.pop(0)

    def _compute_qcvar_history(self) -> float:
        return compute_qcvar(self._cvar_history, alpha=self.qcvar_alpha)

    def validate_system(self, *, psi: float, theta: float, cvar: float, weights: Optional[OmegaWeights] = None) -> Dict[str, object]:
        omega = compute_omega(psi=psi, theta=theta, cvar=cvar, weights=weights)
        safe_cvar = _clamp(cvar)

        record = {"psi": _clamp(psi), "theta": _clamp(theta), "cvar": safe_cvar, "omega": omega}
        self._history.append(record)
        self._omega_history.append(omega)
        self._cvar_history.append(safe_cvar)
        self._trim_history()

        qcvar_value = self._compute_qcvar_history()
        readiness = validate_governance_barrier(
            omega_score=omega, qcvar=qcvar_value, omega_threshold=self.omega_threshold, qcvar_limit=self.qcvar_limit
        )

        return {
            "omega": omega,
            "qcvar": qcvar_value,
            "production_ready": readiness["production_ready"],
            "history_size": len(self._history),
        }

    def get_system_health(self) -> Dict[str, object]:
        qcvar_value = self._compute_qcvar_history() if self._cvar_history else 0.0
        latest_omega = self._omega_history[-1] if self._omega_history else 0.0
        ready = validate_governance_barrier(
            omega_score=latest_omega,
            qcvar=qcvar_value,
            omega_threshold=self.omega_threshold,
            qcvar_limit=self.qcvar_limit,
        )["production_ready"]

        return {
            "latest_omega": latest_omega,
            "qcvar": qcvar_value,
            "production_ready": ready if len(self._history) >= self.min_samples else False,
            "sample_count": len(self._history),
        }

    def get_validation_summary(self) -> Dict[str, object]:
        history_copy: List[Dict[str, float]] = [dict(entry) for entry in self._history]
        return {
            "latest": history_copy[-1] if history_copy else {},
            "history": history_copy,
            "qcvar": self._compute_qcvar_history() if self._cvar_history else 0.0,
            "omega_threshold": self.omega_threshold,
            "qcvar_limit": self.qcvar_limit,
        }

    def reset(self) -> None:
        self._history.clear()
        self._omega_history.clear()
        self._cvar_history.clear()
