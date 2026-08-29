# Changelog

## [Unreleased]

- Added `patch` for the twelve resources whose API exposes PATCH, so a partial
  JSON file changes only the fields it contains
- `update` now warns which populated fields its PUT would clear, and confirms
  when run from a terminal
- `update` warns when omitting `record_status` would post a draft record
- `post` field lists are declared per resource instead of being shared, so the
  intercompany-journal-entry shape can no longer be applied to another resource

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
