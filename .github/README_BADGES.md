# GitHub Actions Status Badges

Add these badges to your README.md file to show build status:

```markdown
![Tests](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/tests.yml/badge.svg)
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual GitHub username and repository name.

## Example:

```markdown
# MCP Expense Management System

![Tests](https://github.com/danielgoes96/mcp-server/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

...rest of README...
```

## Available Workflows

- **Tests** (.github/workflows/tests.yml): Runs all test suites on Python 3.9, 3.10, and 3.11
  - Unit tests
  - E2E tests
  - Duplicate validation tests
  - Stats endpoint tests
  - Cleanup script tests
  - Code linting (flake8, black, isort)

## Local Testing

Before pushing, you can run tests locally:

```bash
# Run all tests
python3 tests/test_structured_logging.py
python3 tests/test_duplicate_validation.py
python3 tests/test_placeholder_full_flow_e2e.py
python3 tests/test_detailed_stats_endpoint.py
python3 tests/test_cleanup_script.py

# Test cleanup script
python3 scripts/cleanup_stale_placeholders.py --dry-run --verbose
```
