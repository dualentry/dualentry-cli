# DualEntry CLI

**Automate your accounting workflows from the command line.**

The DualEntry CLI brings the full power of the DualEntry API to your terminal. Create invoices, sync transactions, and manage your books—all without leaving your workflow.

## Why DualEntry CLI?

- **Scriptable accounting** — Automate repetitive tasks like invoice creation, payment reconciliation, and monthly closes
- **CI/CD ready** — Integrate financial operations into your deployment pipelines
- **Secure by default** — OAuth authentication with credentials stored in your system keychain
- **Works everywhere** — macOS, Linux, and Windows support

## Quick Start

### Install

```bash
uv tool install git+https://github.com/dualentry/dualentry-cli.git
```

### Authenticate

```bash
dualentry auth login
```

This opens your browser for secure authentication. That's it—you're ready to go.

### Your first command

```bash
dualentry invoices list
```

## Common Workflows

### Create and send an invoice

```bash
dualentry invoices create --file invoice.json
```

### Export transactions for a date range

```bash
dualentry journal-entries list --start-date 2025-01-01 --end-date 2025-03-31 --format json
```

### Automate in CI/CD

Set `X_API_KEY` in your environment for non-interactive authentication:

```bash
export X_API_KEY=your_api_key
dualentry bills list --status posted --format json
```

## Available Resources

| Category | Resources |
|----------|-----------|
| **Receivables** | Invoices, Sales Orders, Customer Payments, Credits, Deposits |
| **Payables** | Bills, Purchase Orders, Vendor Payments, Credits, Refunds |
| **Accounting** | Journal Entries, Bank Transfers, Fixed Assets, Depreciation |
| **Master Data** | Customers, Vendors, Items, Accounts, Classifications |
| **Automation** | Recurring Invoices, Recurring Bills, Workflows, Contracts |

All resources support `list`, `get`, `create`, and `update` operations.

## Output Formats

```bash
# Human-readable (default)
dualentry invoices list

# JSON for scripting
dualentry invoices list --format json

# Fetch all pages
dualentry invoices list --all
```

## Configuration

```bash
# View current settings
dualentry config show

# Switch environments
dualentry config set-env dev    # Development
dualentry config set-env prod   # Production
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or [pipx](https://pipx.pypa.io/)

## Upgrade

```bash
uv tool upgrade dualentry-cli
```

## Documentation

- [API Reference](https://docs.dualentry.com/api)
- [Authentication Guide](https://docs.dualentry.com/cli/auth)
- [Webhook Integration](https://docs.dualentry.com/webhooks)

## Support

- [GitHub Issues](https://github.com/dualentry/dualentry-cli/issues)
- [Community Discord](https://discord.gg/dualentry)
- Enterprise support: support@dualentry.com

---

Built by [DualEntry](https://dualentry.com) — Modern accounting infrastructure for developers.
