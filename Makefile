.PHONY: test-smoke test-api test-automation

PYTEST = JWT_SECRET_KEY=dev-secret pytest -q

smoke_cmds = \
	$(PYTEST) tests/test_api.py && \
	$(PYTEST) tests/test_automation_endpoints.py

## Run API smoke tests
test-api:
	$(PYTEST) tests/test_api.py

## Run automation smoke tests
test-automation:
	$(PYTEST) tests/test_automation_endpoints.py

## Run both smoke suites
test-smoke:
	@$(smoke_cmds)
