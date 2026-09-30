# Contributing

## Development setup

```bash
git clone git@github.com:dualentry/dualentry-cli.git
cd dualentry-cli
uv sync --dev
uv run pre-commit install
```

## Dependencies

`uv.lock` is committed, and CI runs `uv sync --dev --locked`, which fails if the lockfile
is out of date with `pyproject.toml`. So whenever you add, remove, or change a dependency:

```bash
uv lock          # regenerate uv.lock
```

Commit the updated `uv.lock` alongside your `pyproject.toml` change, or CI will fail with
`The lockfile at uv.lock needs to be updated, but --locked was provided`.

To pick up newer versions of existing dependencies, run `uv lock --upgrade` deliberately —
it is not something that happens on its own. Expect to fix new `ruff` findings when you do,
since the lint config selects `ALL` rules and each `ruff` release can add more.

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
4. For user-facing changes, add a bullet under `## [Unreleased]` in `CHANGELOG.md`. CI fails PRs that touch `src/` without one; apply the `skip-changelog` label when the change isn't user-facing
5. If you touched dependencies, run `uv lock` and commit `uv.lock`
6. Open a PR against `main`

## Releasing

Releases are triggered by publishing a GitHub Release. CI builds binaries and updates the Homebrew tap automatically.

Run `python scripts/release.py patch` (or `minor`, `major`, or an explicit version) from `main`. It:

1. Moves the `## [Unreleased]` entries in `CHANGELOG.md` under the new version heading
2. Bumps the version, commits, tags, and pushes
3. Creates the GitHub Release with those entries above the auto-generated PR list

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
