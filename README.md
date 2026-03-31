# DualEntry CLI

Command-line interface for the DualEntry accounting API.

## Install

**Production** (default — connects to `api.dualentry.com`):

```bash
uv tool install git+https://github.com/dualentry/dualentry-cli.git
```

**Development** (connects to `api-dev.dualentry.com`):

```bash
uv tool install git+https://github.com/dualentry/dualentry-cli.git
dualentry config set-env dev
```

### Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/)

### Upgrade

```bash
uv tool upgrade dualentry-cli
```

### Uninstall

```bash
uv tool uninstall dualentry-cli
```

## Authentication

### Browser login (OAuth)

```bash
dualentry auth login
```

Opens a browser window for WorkOS AuthKit authentication. Tokens are stored in your system keychain.

### API key (environment variable)

For dev/CI environments, you can skip OAuth and use an API key directly:

```bash
export X_API_KEY=your_api_key
dualentry invoices list
```

Combine with a dev API URL:

```bash
export X_API_KEY=your_api_key
export DUALENTRY_API_URL=https://api-dev.dualentry.com
dualentry invoices list
```

### Check status

```bash
dualentry auth status
dualentry auth logout
```

## Configuration

```bash
# Show current config
dualentry config show

# Switch to dev environment
dualentry config set-env dev

# Switch back to prod
dualentry config set-env prod

# Set a custom API URL
dualentry config set-url https://my-staging.example.com
```

**Environment variables** (override config file):

| Variable | Description |
|----------|-------------|
| `DUALENTRY_API_URL` | API base URL (overrides config) |
| `X_API_KEY` | API key (skips OAuth) |

**Config file** is stored at `~/.dualentry/config.toml`.

## Usage

### Common options

All `list` commands support:

| Flag | Short | Description |
|------|-------|-------------|
| `--limit` | `-l` | Max items to return (default: 20) |
| `--offset` | | Offset for pagination |
| `--all` | `-a` | Fetch all pages |
| `--search` | `-s` | Free text search |
| `--status` | | Filter by status (draft, posted, archived) |
| `--start-date` | | Filter from date (YYYY-MM-DD) |
| `--end-date` | | Filter to date (YYYY-MM-DD) |
| `--format` | `-o` | Output format: `human` or `json` |

### Examples

```bash
# List invoices
dualentry invoices list

# Get a specific invoice by number
dualentry invoices get 1001

# Search with filters
dualentry invoices list --status posted --start-date 2025-01-01 --format json

# Fetch all pages
dualentry bills list --all

# Create from JSON file
dualentry invoices create --file invoice.json
```

### Available resources

**Money-in:** invoices, sales-orders, customer-payments, customer-credits, customer-prepayments, customer-prepayment-applications, customer-deposits, customer-refunds, cash-sales

**Money-out:** bills, purchase-orders, vendor-payments, vendor-credits, vendor-prepayments, vendor-prepayment-applications, vendor-refunds, direct-expenses

**Accounting:** accounts, journal-entries, bank-transfers, fixed-assets, depreciation-books

**Entities:** customers, vendors, items, companies, classifications

**Recurring:** recurring invoices, recurring bills, recurring journal-entries

**Other:** contracts, budgets, workflows

Each resource supports `list` and `get`. Most also support `create` and `update`.

## Development

### Development setup

```bash
uv sync --extra dev
```

### Pre-commit hooks

```bash
uv run pre-commit install
```

Hooks run `ruff check --fix` and `ruff format` on each commit.

### Linting

```bash
uv run ruff check .
uv run ruff format --check .
```

### Tests

Unit tests (mocked, no API needed):

```bash
uv run pytest
```

Integration tests (requires running API server):

```bash
X_API_KEY=your_key DUALENTRY_API_URL=https://api-dev.dualentry.com uv run pytest tests/test_integration.py -v
```

With coverage:

```bash
uv run pytest --cov=dualentry_cli --cov-report=term-missing
```
