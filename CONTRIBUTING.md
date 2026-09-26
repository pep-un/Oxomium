# Contributing to Oxomium

Contributions are welcome. Please keep changes focused, tested, and easy to review.

## Before starting

- Check existing issues and pull requests to avoid duplicate work.
- Open or reference an issue for significant changes so the scope is clear.
- Base your work on the latest `main` branch.
- Keep unrelated refactoring or formatting out of a functional change.

## Development setup

Create a virtual environment and install the project dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Windows, activate the virtual environment with the appropriate command for your shell.

## Making changes

- Add or update tests for changed behaviour.
- Include Django migrations when model changes require them.
- Keep commits and pull requests scoped to one coherent change.
- Follow the existing project structure and coding conventions.
- Do not commit local configuration, credentials, virtual environments, caches, or generated files unless they are intentionally part of the project.

## Checks before opening a pull request

Run the test suite:

```bash
python manage.py test
```

Verify that model changes do not leave uncommitted migrations:

```bash
python manage.py makemigrations --check --dry-run
```

When modifying Python code, run Pylint with the project settings:

```bash
pylint -E --load-plugins pylint_django --django-settings-module=oxomium --ignore-paths='.*/migrations/' --ignore=__init__.py,manage.py $(git ls-files '*.py')
```

## Pull requests

- Target `main`.
- Use a clear title and explain the purpose and scope of the change.
- Link the relevant issue when one exists.
- Describe how the change was tested.
- Call out migrations, dependency changes, or compatibility considerations when relevant.
- Address review feedback with focused follow-up commits or an updated branch.
