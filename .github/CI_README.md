# CI/CD Pipeline Documentation

## 🚀 Quick Start

### Running CI Checks Locally

```bash
# 1. Run linters
./scripts/ci/run_linters.sh

# 2. Run tests
./scripts/ci/run_tests.sh

# 3. Check coverage
./scripts/ci/check_coverage.sh
```

### Fix Common Issues

```bash
# Fix formatting
black core/ api/ app/ --line-length=120
isort core/ api/ app/ --profile black

# View coverage report
open htmlcov/index.html
```

## 📋 Pipeline Overview

The CI pipeline runs automatically on:
- Every push to `main`, `master`, `develop`, or `feature/**` branches
- Every pull request to `main`, `master`, or `develop`
- Nightly at 2 AM UTC (scheduled)

### Jobs

1. **🔍 Lint** - Code style and formatting
2. **🔎 Type Check** - Static type analysis
3. **🧪 Tests** - Unit tests + coverage
4. **🔒 Security** - Vulnerability scanning
5. **🐳 Docker** - Build validation
6. **🔗 Integration** - Integration tests
7. **📊 Report** - Summary generation

## 🛠️ Configuration Files

### .flake8
```ini
max-line-length = 120
exclude = venv, migrations, node_modules
ignore = E203, W503, E501, E402
```

### pyproject.toml
```toml
[tool.black]
line-length = 120
target-version = ['py39']

[tool.isort]
profile = "black"
line_length = 120

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=core --cov=api"
```

## 📊 Coverage Requirements

- **Minimum**: 60%
- **Target**: 70%+
- **Reports**: HTML, XML, Terminal

To view coverage:
```bash
pytest --cov=core --cov=api --cov-report=html
open htmlcov/index.html
```

## 🔒 Security Scanning

### Bandit
Scans Python code for security issues:
```bash
bandit -r core/ api/ app/
```

### Safety
Checks dependencies for vulnerabilities:
```bash
safety check
```

## 🐳 Docker Validation

The pipeline validates that:
1. Dockerfile builds successfully
2. Image can run Python
3. Dependencies are installed

Local testing:
```bash
docker build -t mcp-server:test .
docker run --rm mcp-server:test python --version
```

## 🔗 Integration Tests

Tests run with full Docker Compose stack:
```bash
docker-compose up -d
# Tests run here
docker-compose down -v
```

## 🤖 Dependabot

Automated dependency updates run weekly (Mondays 9 AM):
- Python packages (pip)
- Docker images
- GitHub Actions

PRs are automatically created with:
- Labels: `dependencies`, `python`, `docker`, `github-actions`
- Reviewer: danielgoes96
- Commit prefix: `chore:`

## 📈 Monitoring

### GitHub Actions
View pipeline status at: `https://github.com/USERNAME/REPO/actions`

### Artifacts
After each run, download:
- Coverage reports (`coverage-report/`)
- Security reports (`security-reports/`)

## 🚨 Troubleshooting

### Pipeline Fails on Lint
```bash
# Fix locally
./scripts/ci/run_linters.sh

# Auto-fix formatting
black core/ api/ app/ --line-length=120
isort core/ api/ app/ --profile black

# Commit fixes
git add .
git commit -m "style: fix linting issues"
git push
```

### Tests Fail
```bash
# Run locally to debug
./scripts/ci/run_tests.sh

# Run specific test
pytest tests/test_specific.py -v

# Debug with pdb
pytest tests/test_specific.py --pdb
```

### Coverage Too Low
```bash
# View coverage report
./scripts/ci/check_coverage.sh
open htmlcov/index.html

# Add tests for uncovered code
# Focus on critical paths first
```

### Docker Build Fails
```bash
# Test build locally
docker build -t mcp-server:test .

# Check logs
docker-compose logs api

# Validate docker-compose
docker-compose config
```

## 🎯 Best Practices

### Before Committing
1. Run linters: `./scripts/ci/run_linters.sh`
2. Run tests: `./scripts/ci/run_tests.sh`
3. Check coverage: `./scripts/ci/check_coverage.sh`

### Pull Requests
1. Keep changes focused and small
2. Ensure all CI checks pass
3. Maintain or improve coverage
4. Update tests for new features

### Adding New Tests
1. Place in appropriate `tests/` subdirectory
2. Follow naming: `test_*.py`
3. Use fixtures for setup
4. Keep tests isolated

### Updating Dependencies
1. Update `requirements.txt`
2. Test locally
3. Check security with `safety check`
4. Update if Dependabot creates PR

## 📚 Resources

- GitHub Actions docs: https://docs.github.com/actions
- pytest docs: https://docs.pytest.org
- black docs: https://black.readthedocs.io
- flake8 docs: https://flake8.pycqa.org

## 🆘 Support

If CI issues persist:
1. Check GitHub Actions logs
2. Run locally to reproduce
3. Review recent commits
4. Check for dependency conflicts
5. Contact team lead

---

**Last Updated**: November 4, 2025
**Maintained by**: DevOps Team
