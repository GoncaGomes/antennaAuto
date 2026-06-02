# Development Workflow

This repository is managed by one maintainer.

## Stable branch

`main` should represent the latest stable project state.

Small documentation changes may be committed directly to `main`.

Code changes, refactors, and Codex-generated changes should happen in a separate branch.

## Branch names

Use clear branch names:

- `chore/...` for repository maintenance
- `docs/...` for documentation
- `fix/...` for bug fixes
- `refactor/...` for controlled refactors
- `experiment/...` for experiments

## Before committing code changes

Run:

```powershell
.\scripts\check.ps1