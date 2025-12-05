# MatVerse Enterprise: Ω-Gateway Toolkit

Utilities for experimenting with the MatVerse "Omega Gateway" governance model. The toolkit focuses on lightweight, testable primitives for calculating Omega scores, estimating QCVaR (Quantum Conditional Value at Risk), validating governance barriers, tracking antifragility, and aggregating rolling assessments via `OmegaValidator`.

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
  - [Omega score calculation](#omega-score-calculation)
  - [Quantum CVaR estimation](#quantum-cvar-estimation)
  - [Governance barrier validation](#governance-barrier-validation)
  - [Antifragility metrics](#antifragility-metrics)
  - [Rolling validation with `OmegaValidator`](#rolling-validation-with-omegavalidator)
- [Testing](#testing)
- [Contributing](#contributing)

## Overview
The Omega Gateway model combines epistemic strength (`ψ`), latency (`θ`), and risk (`CVaR`) into a normalized Omega score. Governance checks use configurable thresholds for Omega and QCVaR to decide whether a system is production ready. This repository provides:

- A small Python library (see `src/matverse/omega_gateway.py`).
- A comprehensive pytest suite that exercises edge cases and defensive copying.
- Minimal dependencies to keep the toolkit easy to run in constrained environments.

## Key Features
- **Omega score computation**: configurable weights with automatic normalization and clamping of invalid inputs.
- **QCVaR estimation**: simple tail-mean estimator that ignores non-finite samples.
- **Governance barrier checks**: Omega/QCVaR thresholds with a boolean readiness verdict.
- **Antifragility indicator**: tracks performance deltas when stress is applied.
- **Rolling validator**: maintains a bounded history, computes QCVaR over recent samples, and exposes read-only snapshots for safe consumption.

## Project Structure
```
./src/matverse/omega_gateway.py  # Core Omega, QCVaR, governance, antifragility, and validator logic
./tests/test_omega_gateway.py    # Pytest suite covering calculations and history handling
```

## Installation
Use any Python 3.10+ environment. A virtual environment is recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt  # if available
```

If `requirements.txt` is not present, no additional dependencies are required for the library or the tests.

## Usage
Import the helpers from `matverse.omega_gateway`.

### Omega score calculation
```python
from matverse.omega_gateway import compute_omega, OmegaWeights

omega = compute_omega(psi=0.92, theta=0.87, cvar=0.08)
print(f"Omega score: {omega:.3f}")

# Custom weighting
weights = OmegaWeights(psi=0.6, theta=0.2, cvar=0.2)
weighted = compute_omega(psi=0.85, theta=0.90, cvar=0.05, weights=weights)
```

### Quantum CVaR estimation
```python
from matverse.omega_gateway import compute_qcvar

samples = [0.9, 0.82, 0.75, 0.93, 0.88]
qcvar = compute_qcvar(samples, alpha=0.95)
print(f"QCVaR (95% tail mean): {qcvar:.4f}")
```

### Governance barrier validation
```python
from matverse.omega_gateway import validate_governance_barrier

barriers = validate_governance_barrier(omega_score=0.96, qcvar=0.07, omega_threshold=0.9, qcvar_limit=0.1)
if barriers["production_ready"]:
    print("System passes governance thresholds.")
else:
    print("System requires further hardening.")
```

### Antifragility metrics
```python
from matverse.omega_gateway import antifragile_metric

metrics = antifragile_metric(before=0.90, after=0.95, stress_applied=True)
# metrics => {'improvement': 0.05, 'is_antifragile': True, 'antifragile_coefficient': 0.05}
```

### Rolling validation with `OmegaValidator`
```python
from matverse.omega_gateway import OmegaValidator

validator = OmegaValidator(omega_threshold=0.9, qcvar_limit=0.1, qcvar_alpha=0.9, max_history=50, min_samples=5)

for _ in range(12):
    validator.validate_system(psi=0.9, theta=0.88, cvar=0.08)

health = validator.get_system_health()
summary = validator.get_validation_summary()
print(health)
print(summary["latest"])

# Clear the sliding window and start fresh
validator.reset()
```

The validator:
- clamps invalid thresholds to safe ranges;
- stores history with defensive copies to prevent external mutation;
- computes QCVaR over the sliding window and reports readiness via `production_ready`.

## Testing
Run the pytest suite from the repository root:

```bash
pytest
```

The tests cover Omega calculations, QCVaR behavior (including non-finite samples), governance barrier checks, antifragility metrics, history trimming, and defensive copying in the validator API.

## Contributing
- Keep functions side-effect free and defensively handle invalid inputs.
- Update or add tests in `test_omega_gateway.py` for new behavior.
- Use type hints and preserve backward compatibility for existing function signatures.
