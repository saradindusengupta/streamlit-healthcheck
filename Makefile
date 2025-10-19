# Publish the package to PyPI
.PHONY: publish
publish: build ## Publish the package to PyPI (requires PYPI_TOKEN env var)
	twine upload dist/* --verbose --username __token__ --password "$$PYPI_TOKEN"
.ONESHELL:
ENV_PREFIX := $(shell [ -f .venv/bin/pip ] && echo ".venv/bin/" || echo "")
project_name := streamlit_healthcheck

.PHONY: help
help:             ## Show the help.
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@fgrep "##" Makefile | fgrep -v fgrep


.PHONY: show
show:             ## Show the current environment.
	@echo "Current environment:"
	@echo "Running using: $(ENV_PREFIX)"
	@$(ENV_PREFIX)python -V
	@$(ENV_PREFIX)python -m site

.PHONY: install
install:          ## Install the project in dev mode.
	@echo "Don't forget to run 'make virtualenv' if you got errors."
	pip install -e .[test]

.PHONY: build
build:          ## Build the project.
	@echo "Build wheel file"
	python -m build

.PHONY: lint
lint:             ## Run pep8, black, mypy linters.
	flake8 src/$(project_name)/
	black -l 79 --check src/$(project_name)/
	black -l 79 --check tests/

.PHONY: test_coverage
test_coverage:    ## Run tests and generate coverage report.
	pytest -v --cov-config .coveragerc --cov=src/$(project_name) -l --tb=short --maxfail=1 tests/

.PHONY: test
test:    ## Run tests.
	pytest -v -l --tb=short --maxfail=1 tests/

.PHONY: watch
watch:            ## Run tests on every change.
	ls **/**.py | entr pytest -s -vvv -l --tb=long --maxfail=1 tests/

.PHONY: clean
clean:            ## Clean unused files.
	@find ./ -name '*.pyc' -exec rm -f {} \;
	@find ./ -name '__pycache__' -exec rm -rf {} \;
	@find ./ -name 'Thumbs.db' -exec rm -f {} \;
	@find ./ -name '*~' -exec rm -f {} \;
	@rm -rf .cache
	@rm -rf .pytest_cache
	@rm -rf .mypy_cache
	@rm -rf build
	@rm -rf distsoc_estimation
	@rm -rf *.egg-info
	@rm -rf htmlcov
	@rm -rf .tox/
	@rm -rf docs/_build

.PHONY: release
release:          ## Create a new tag for release.
	@echo "WARNING: This operation will create s version tag and push to github"
	@read -p "Version? (provide the next x.y.z semver) : " TAG
	@echo "$${TAG}" > src/$(project_name)/VERSION
	@git commit -m "release: version $${TAG} 🚀"
	@echo "creating git tag : $${TAG}"
	@git tag $${TAG}
	@git push -u origin HEAD --tags
	@echo "Github Actions will detect the new tag and release the new version."

.PHONY: docs
docs:             ## Build the documentation.
	@echo "building documentation with PyDoc ..."
	@pdoc src/$(project_name) --output docs/
