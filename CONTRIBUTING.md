# Contributing

## Development Setup

```powershell
make dev
```

## Run Locally

```powershell
make run
```

## Test

```powershell
.venv/Scripts/python.exe -m pytest
```

## Pull Request Expectations

- Keep changes focused and scoped.
- Add/update tests for behavior changes.
- Do not commit generated artifacts (`dist/`, `build/`, local `profiles/`, `.venv/`).
- Keep user-facing behavior documented in `README.md` if relevant.

## Commit Style (Recommended)

- `feat: ...` for new features
- `fix: ...` for bug fixes
- `chore: ...` for tooling/docs/refactors without behavior change
- `test: ...` for test-only changes
