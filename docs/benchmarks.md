---
title: Benchmarks
---

# Benchmarks

Benchmarks are recorded with `pytest --benchmark-only` (see `benchmarks/test_validate_env.py`).

| Suite | Scenario | Mean (ms) | Std Dev (ms) |
| ----- | -------- | --------- | ------------ |
| Validation | Validate 4-variable spec | 0.28 | 0.03 |

> Measurements captured on a 2022 MacBook Pro (M2, Python 3.12). Re-run locally with `make bench`.
