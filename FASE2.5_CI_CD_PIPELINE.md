# Fase 2.5 - CI/CD Pipeline

## Objetivo
Implementar un pipeline de CI/CD con GitHub Actions que garantice la calidad del código en cada push mediante tests, linters y validaciones automáticas.

## Estado Actual
- ❌ No hay CI/CD configurado
- ❌ Tests se ejecutan manualmente
- ❌ No hay validación automática de código
- ❌ No hay protección de branches
- ❌ No hay validación de Docker builds

## Resultado Esperado
Pipeline completo que ejecuta:
1. ✅ Linting (flake8, pylint)
2. ✅ Formateo (black, isort)
3. ✅ Type checking (mypy)
4. ✅ Tests unitarios (pytest)
5. ✅ Tests de integración
6. ✅ Coverage reports
7. ✅ Docker build validation
8. ✅ Security scanning

## Pipeline Propuesto

### 📋 Workflow: CI Pipeline

**Triggers:**
- Push a cualquier branch
- Pull requests a main/master
- Scheduled (nightly builds)

**Jobs:**

#### 1. **Lint & Format Check**
```yaml
- Flake8: Style guide enforcement
- Black: Code formatting check
- isort: Import sorting
- pylint: Code quality analysis
```

#### 2. **Type Checking**
```yaml
- mypy: Static type checking
- Verifica tipos en código crítico
```

#### 3. **Unit Tests**
```yaml
- pytest: Ejecuta tests unitarios
- Coverage: Reporte de cobertura (mínimo 70%)
- Parallel execution: Tests en paralelo
```

#### 4. **Integration Tests**
```yaml
- Docker Compose: Levanta stack completo
- Tests de integración con DB real
- Tests de APIs endpoints
```

#### 5. **Security Scanning**
```yaml
- bandit: Security issues en Python
- safety: Vulnerabilidades en dependencias
- trivy: Escaneo de Docker images
```

#### 6. **Build Validation**
```yaml
- Docker build: Valida que imagen se construye
- Multi-stage build optimization
- Layer caching
```

## Estructura de Archivos

```
.github/
├── workflows/
│   ├── ci.yml                 # Pipeline principal
│   ├── deploy-staging.yml     # Deploy a staging
│   └── deploy-production.yml  # Deploy a producción
├── actions/                   # Custom actions
└── dependabot.yml             # Dependencias automáticas

scripts/
├── ci/
│   ├── run_tests.sh          # Script de tests
│   ├── run_linters.sh        # Script de linting
│   └── check_coverage.sh     # Validación de coverage
```

## Configuración de Herramientas

### 1. pytest.ini (ya existe)
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --cov=core --cov=api --cov-report=html --cov-report=term
```

### 2. .flake8
```ini
[flake8]
max-line-length = 120
exclude = .git,__pycache__,venv,.venv,migrations
ignore = E203,W503,E501
```

### 3. pyproject.toml (Black + isort)
```toml
[tool.black]
line-length = 120
target-version = ['py39']
exclude = '''
/(
    \.git
  | \.venv
  | migrations
)/
'''

[tool.isort]
profile = "black"
line_length = 120
```

### 4. mypy.ini
```ini
[mypy]
python_version = 3.9
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False
ignore_missing_imports = True
```

## GitHub Actions Workflow

### Pipeline Principal (ci.yml)

```yaml
name: CI Pipeline

on:
  push:
    branches: [ main, master, develop, feature/** ]
  pull_request:
    branches: [ main, master, develop ]
  schedule:
    - cron: '0 2 * * *'  # Nightly build a las 2 AM

env:
  PYTHON_VERSION: '3.9'
  POSTGRES_VERSION: '15'

jobs:
  lint:
    name: 🔍 Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install flake8 black isort pylint
          pip install -r requirements.txt

      - name: Run flake8
        run: flake8 core/ api/ --max-line-length=120

      - name: Check black formatting
        run: black --check core/ api/

      - name: Check isort
        run: isort --check-only core/ api/

  type-check:
    name: 🔎 Type Checking
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install mypy
          pip install -r requirements.txt

      - name: Run mypy
        run: mypy core/ api/ --ignore-missing-imports

  test:
    name: 🧪 Run Tests
    runs-on: ubuntu-latest
    needs: [lint, type-check]

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}

      - name: Install dependencies
        run: |
          pip install pytest pytest-cov pytest-asyncio
          pip install -r requirements.txt

      - name: Run unit tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/ -v --cov=core --cov=api --cov-report=xml --cov-report=html

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unittests
          name: codecov-umbrella

  security:
    name: 🔒 Security Scanning
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install bandit safety
          pip install -r requirements.txt

      - name: Run Bandit
        run: bandit -r core/ api/ -f json -o bandit-report.json || true

      - name: Run Safety
        run: safety check --json || true

      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            bandit-report.json

  docker:
    name: 🐳 Docker Build
    runs-on: ubuntu-latest
    needs: [test]
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Build Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          file: ./Dockerfile
          push: false
          tags: mcp-server:test
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Test Docker image
        run: |
          docker run --rm mcp-server:test python --version
          docker run --rm mcp-server:test pip list

  integration:
    name: 🔗 Integration Tests
    runs-on: ubuntu-latest
    needs: [test, docker]
    steps:
      - uses: actions/checkout@v3

      - name: Start Docker Compose stack
        run: |
          docker-compose -f docker-compose.yml up -d
          sleep 10

      - name: Wait for services
        run: |
          docker-compose ps
          docker-compose logs

      - name: Run integration tests
        run: |
          # Test health endpoints
          curl -f http://localhost:8000/health || exit 1

      - name: Cleanup
        if: always()
        run: docker-compose down -v

  report:
    name: 📊 Generate Report
    runs-on: ubuntu-latest
    needs: [lint, type-check, test, security, docker, integration]
    if: always()
    steps:
      - name: Create summary
        run: |
          echo "## CI Pipeline Summary" >> $GITHUB_STEP_SUMMARY
          echo "✅ All checks passed!" >> $GITHUB_STEP_SUMMARY
```

## Scripts de CI

### 1. scripts/ci/run_tests.sh
```bash
#!/bin/bash
set -e

echo "🧪 Running tests..."
pytest tests/ -v --cov=core --cov=api --cov-report=html --cov-report=term

echo "📊 Coverage report generated at htmlcov/index.html"
```

### 2. scripts/ci/run_linters.sh
```bash
#!/bin/bash
set -e

echo "🔍 Running flake8..."
flake8 core/ api/ --max-line-length=120

echo "🎨 Checking black formatting..."
black --check core/ api/

echo "📦 Checking isort..."
isort --check-only core/ api/

echo "✅ All linters passed!"
```

### 3. scripts/ci/check_coverage.sh
```bash
#!/bin/bash
set -e

MIN_COVERAGE=70

coverage run -m pytest tests/
COVERAGE=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')

echo "Coverage: ${COVERAGE}%"

if (( $(echo "$COVERAGE < $MIN_COVERAGE" | bc -l) )); then
    echo "❌ Coverage ${COVERAGE}% is below minimum ${MIN_COVERAGE}%"
    exit 1
fi

echo "✅ Coverage ${COVERAGE}% meets minimum ${MIN_COVERAGE}%"
```

## Badges para README.md

```markdown
![CI](https://github.com/USERNAME/mcp-server/workflows/CI%20Pipeline/badge.svg)
![Coverage](https://codecov.io/gh/USERNAME/mcp-server/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
```

## Protección de Branches

### Configuración en GitHub
1. Settings → Branches → Branch protection rules
2. Aplicar a `main` y `master`:
   - ✅ Require pull request reviews before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Include administrators
   - ✅ Require linear history

### Status Checks Requeridos
- lint
- type-check
- test
- security
- docker
- integration

## Dependabot Configuration

### .github/dependabot.yml
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

## Plan de Implementación

### Fase 1: Configuración Básica (1 hora)
1. ✅ Crear estructura .github/workflows/
2. ✅ Configurar pytest, flake8, black
3. ✅ Crear workflow básico de CI

### Fase 2: Tests y Coverage (1 hora)
4. ✅ Configurar pytest con coverage
5. ✅ Integrar Codecov
6. ✅ Validar tests existentes

### Fase 3: Security y Docker (1 hora)
7. ✅ Configurar bandit y safety
8. ✅ Validar Docker builds
9. ✅ Tests de integración

### Fase 4: Optimización (30 min)
10. ✅ Cache de dependencias
11. ✅ Parallel execution
12. ✅ Branch protection rules

## Métricas de Éxito

- ✅ Pipeline ejecuta en < 10 minutos
- ✅ Coverage > 70%
- ✅ Zero security issues críticos
- ✅ Docker build exitoso
- ✅ Todos los tests pasan

## Beneficios Esperados

1. **Calidad**: Código validado automáticamente
2. **Seguridad**: Escaneo de vulnerabilidades
3. **Confianza**: Tests ejecutan en cada push
4. **Velocidad**: CI feedback en minutos
5. **Documentación**: Pipeline como documentación viva

## Integración con Fases Anteriores

- **Fase 2.1**: Tests sobre código limpio
- **Fase 2.2**: Validación de Docker builds
- **Fase 2.3**: Tests con PostgreSQL real
- **Fase 2.4**: Tests organizados por dominio ✅
- **Fase 2.5**: CI/CD completo ⏳

## Próximos Pasos

1. Crear archivos de configuración
2. Implementar workflow de CI
3. Validar pipeline localmente
4. Push y verificar ejecución
5. Configurar protección de branches
