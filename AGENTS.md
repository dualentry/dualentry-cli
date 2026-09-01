# Agent Guidelines

## Public repository — information exposure policy

This repository is public. Everything in it — source code, commit messages, PR titles and bodies, issues, and the CHANGELOG — is world-readable. Follow these rules for anything you write here.

### Commits and pull requests

- Describe what changed and why it matters to users of the CLI, not the internal discussion behind it.
- Never paste content from internal tickets, Slack threads, meeting notes, or call recordings.
- Never mention customer or organization names, employee names or emails, or internal URLs (Linear, Notion, Slack, Grain).
- Never reference internal hostnames, AWS account IDs, environment names, or infrastructure topology.

### Security wording

- Never name a vulnerability class, exploit path, or impact in commit or PR text (e.g., "fix injection in X endpoint").
- Use neutral wording instead ("harden input validation", "improve request handling") and keep the details in the private tracker.

### Secrets

- Never include tokens, API keys, JWTs, cookies, or connection strings anywhere: messages, code, examples, test fixtures, or recorded HTTP mocks.
- If a secret lands in history, treat it as compromised: rotate it and tell the maintainers. Deleting the line is not enough.

### No AI attribution

- No `Co-authored-by`, `Generated-with`, `Made-with`, or any other agent/tool trailer in commits or PRs.
- Commits are authored by the user's configured git identity. Never change `git config user.name` / `user.email`.

### Source is public too

The same rules apply inside the code: comments, docstrings, error strings, and CHANGELOG entries. Examples in the README and tests use fake organization names and `example.com` emails — never real customer data.
