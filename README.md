# DualEntry CLI

Command-line interface for the DualEntry accounting API.

## Install

```bash
brew install dualentry/tap/dualentry
```

Or with uv:

```bash
uv tool install git+https://github.com/dualentry/dualentry-cli.git
```

Or via the install script:

```bash
curl -fsSL https://raw.githubusercontent.com/dualentry/dualentry-cli/main/install.sh | sh
```

### Prerequisites

- macOS (arm64, x86_64) or Linux (x86_64)

### Upgrade

```bash
brew upgrade dualentry
```

### Uninstall

```bash
brew uninstall dualentry
```

## Authentication

### Browser login (OAuth)

```bash
dualentry auth login
```

Opens a browser window for authentication. API key is stored in your system keychain.

### API key (environment variable)

For CI environments, you can skip OAuth and use an API key directly:

```bash
export X_API_KEY=your_api_key
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

# Set a custom API URL
dualentry config set-url https://api.dualentry.com
```

**Environment variables** (override config file):

| Variable | Description |
|----------|-------------|
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

### Setup

```bash
uv sync --dev
uv run pre-commit install
```

### Linting

```bash
uv run ruff check .
uv run ruff format --check .
```

### Tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=dualentry_cli --cov-report=term-missing
```
