.PHONY: install lint fmt test typecheck docs build bench clean release-notes

install:
	pip install -e .[dev]

lint:
	ruff check src tests

fmt:
	ruff format src tests
	black src tests

fix:
	ruff check --fix src tests
	black src tests

typecheck:
	mypy src

test:
	pytest -q

bench:
	pytest benchmarks -q --benchmark-only

coverage:
	pytest -q --cov=envkeep --cov-report=term-missing

docs:
	mkdocs build --strict

build:
	python -m build

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage*

release-notes:
	python scripts/generate_release_notes.py
