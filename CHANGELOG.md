# Changelog

## [Unreleased]

- Added `dualentry quotes` for CPQ quotes: `list` (search, status, approval status, company, customer, valid-until range, ordering), `get` by number or `QT-` ID, `create`, `update` (partial, with `--display-options`), `submit`, `send` (with `--pdf` or `--no-pdf`), and `template`.
- `quotes get` shows lines with billing frequency and service period, totals (one-time, recurring per cadence, MRR, ARR, first invoice, TCV or Ongoing, per year), and the signing order.

## [0.1.18] - 2026-09-01


## [0.1.17] - 2026-04-15


## [0.1.16] - 2026-04-14


## [0.1.15] - 2026-04-14


## [0.1.14] - 2026-04-14


## [0.1.13] - 2026-04-14


## [0.1.12] - 2026-04-14


## [0.1.11] - 2026-04-10


## [0.1.10] - 2026-04-09


## [0.1.1] - 2026-04-09


## [0.1.7] - 2026-04-01

- Added CONTRIBUTING.md with contribution guidelines
- Updated README with contribution section
- CLI refactoring and code improvements

## [0.1.0] - 2026-03-31

- OAuth browser login with API key storage in system keychain
- List, get, create, and update for all transaction types
- Table and JSON output formats
- Pagination, search, and date/status filtering
- Homebrew tap and install script distribution
