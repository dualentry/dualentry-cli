# Contributing

## Development setup

```bash
git clone git@github.com:dualentry/dualentry-cli.git
cd dualentry-cli
uv sync --dev
uv run pre-commit install
```

## Running locally

```bash
uv run dualentry --help
uv run dualentry invoices list
```

## Linting

```bash
uv run ruff check .
uv run ruff format --check .
```

## Tests

```bash
uv run pytest
uv run pytest --cov=dualentry_cli --cov-report=term-missing
```

## Pull requests

1. Create a branch from `main`
2. Make your changes
3. Ensure linting and tests pass
4. Open a PR against `main`

## Releasing

Releases are triggered by publishing a GitHub Release. CI builds binaries and updates the Homebrew tap automatically.

1. Update `CHANGELOG.md` with the new version and changes
2. Commit and push to `main`
3. Go to GitHub → Releases → **Draft a new release**
4. Click **Choose a tag** → type the new version (e.g., `v0.2.0`) → **Create new tag**
5. Set the title: `DualEntry CLI v0.2.0 — <summary>`
6. Paste the changelog entry as the release body
7. Click **Publish release**

CI will:
- Build binaries for macOS (arm64, x86_64) and Linux (x86_64)
- Stamp the version from the tag into the binary
- Upload binaries to the GitHub Release
- Update the Homebrew tap formula with new SHA256 hashes

Users upgrade via `brew upgrade dualentry` or re-running the install script.

## Versioning

We use [Semantic Versioning](https://semver.org/):
- **Patch** (`0.1.1`) — bug fixes
- **Minor** (`0.2.0`) — new features, backward compatible
- **Major** (`1.0.0`) — breaking changes
