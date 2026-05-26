# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pg-channel` is a Python library that generates PL/pgSQL scripts for creating PostgreSQL LISTEN/NOTIFY trigger channels. The single public function `plsql()` in `pg_channel/__init__.py` produces SQL for INSERT/DELETE/UPDATE triggers on a given table.

## Commands

```bash
# Setup (creates venv, installs dev deps, sets up pre-commit hooks)
make install

# Run tests
make test
# Or directly:
pytest tests -v

# Build package
make build

# Build + upload to PyPI
make twine

# Tag current version
make patch
```

The makefile expects a `.env` file (copy from `.env.dist`) defining `VENV=venv`.

## Architecture

Single-module library: all logic lives in `pg_channel/__init__.py`.

- `Act(IntEnum)` — bitmask enum: `DEL=1`, `NEW=2`, `UPD=4`. The `ops` parameter (default `7` = all three) controls which trigger types to generate.
- `plsql(table, ops, updates)` — generates SQL strings for trigger functions and triggers. The `updates` dict controls conditional update channel routing:
  - `tuple` values → AND conditions (all fields must change)
  - `list` values → OR conditions (any field must change)
  - Keys prefixed with `_` → generate `ELSIF` branches instead of separate `IF` blocks

## Pre-commit Hooks

- **pre-commit**: runs `pytest tests -v`, then `ruff --fix` and `ruff-format`
- **post-commit**: auto-tags if commit message starts with `feat:` or `fix:` (via `make patch`)
- **pre-push**: auto-builds and uploads to PyPI on pushes to `main` branch

## Code Style

Ruff with `line-length = 120`. Linting and formatting enforced via pre-commit hooks.