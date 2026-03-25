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

## First Public Push Cleanup (Maintainers)

If generated/runtime files were already tracked in git before `.gitignore` was updated, untrack them once:

```powershell
git rm -r --cached dist build .venv .pytest_cache profiles
git commit -m "chore: stop tracking local/build artifacts"
```

## Commit Style (Recommended)

- `feat: ...` for new features
- `fix: ...` for bug fixes
- `chore: ...` for tooling/docs/refactors without behavior change
- `test: ...` for test-only changes
