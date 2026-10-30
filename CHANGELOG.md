# Changelog

## [Unreleased]

- Add `gst-tax-rates` commands (`list`, `get`) to look up the `gst_tax_rate_id` for line items, filterable by `--country`, `--treatment`, `--active/--inactive`, and `--updated-after/--updated-before`. Rates show as percentages, with the component split for rates such as CGST + SGST
- Line-item tables label the quantity column Quantity
- Update the CLI greeting logo to DualEntry
- Add `export-jobs` commands (`create`, `list`, `get`, `wait`) for on-demand destination data refreshes via the public API

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
