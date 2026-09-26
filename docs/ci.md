# Continuous Integration and Delivery Strategy

This document defines how Oxomium uses GitHub Actions and the responsibility of each workflow.

The design goal is to make the trigger and purpose of every workflow obvious from its filename while keeping pull-request checks compatible with the main branch ruleset.

## Python version source of truth

Python versions are defined once in `.github/ci-python-versions.json`:

- `current` is the Python version used for normal branch CI, main CI and Sonar coverage;
- `supported` is the compatibility matrix enforced on pull requests.

Each workflow starts with a small `Python version configuration` job that reads and validates this file. The current version must also be present in the supported list.

To adopt or retire a Python version, update this file first. Pull-request job names are generated from the supported matrix, so changing that list may require a coordinated update of the `main` ruleset required status checks.

## Workflow map

| Workflow | Trigger | Purpose | Python policy | Docker policy |
| --- | --- | --- | --- | --- |
| `.github/workflows/ci-branch.yml` | Push to any branch except main | Fast developer feedback | Current only | None |
| `.github/workflows/ci-pull-request.yml` | Pull request targeting main | Compatibility and merge gate | All supported versions | Lint/config validation only, when Docker files change |
| `.github/workflows/ci-main.yml` | Push to main | Canonical post-merge integration validation | Current only | Full build, security scan and smoke test |
| `.github/workflows/docker-publish.yml` | Manual `workflow_dispatch` | Explicit Docker Hub publication outside the release flow | N/A | Build and publish |
| `.github/workflows/release.yml` | Published GitHub Release | Build, scan, publish and attach release artifacts | N/A | Release build and publication |

CI workflows are intentionally separated by event. A contributor should be able to infer when a workflow runs without first reading its YAML.

## Branch push CI

`ci-branch.yml` runs on every push to a branch other than `main`. Its purpose is fast feedback before or outside a pull request.

It runs Django tests, the migration consistency check and Pylint using the `current` Python version from `.github/ci-python-versions.json`.

Older runs for the same branch are cancelled when a newer commit is pushed, avoiding runner time on stale revisions.

## Pull-request CI

`ci-pull-request.yml` runs for pull requests targeting `main` and is the merge gate.

It runs:

- Django tests and migration checks on every Python version in `supported`;
- Pylint on every Python version in `supported`;
- GitHub dependency review;
- SonarQube/SonarCloud analysis using the current Python version;
- Docker lint/config validation only when Docker-related files changed.

The compatibility matrices use `fail-fast: false` so one incompatible version does not hide results from other supported versions.

### Required status checks

The current `main` ruleset requires:

- Django (Python 3.10)
- Django (Python 3.11)
- Django (Python 3.12)
- Django (Python 3.13)
- Django (Python 3.14)
- Pylint (Python 3.10)
- Pylint (Python 3.11)
- Pylint (Python 3.12)
- Pylint (Python 3.13)
- Pylint (Python 3.14)
- DependencyCheck

The ruleset also requires the SonarCloud code-analysis check produced by the SonarCloud integration.

These names must not be changed casually. When `supported` changes, update the ruleset together with the workflow matrix.

### Docker checks on pull requests

A pull request does not build a Docker image.

A lightweight `Detect Docker-file changes` job enables `Docker Lint` only when the pull request changes:

- `Dockerfile`
- `.dockerignore`
- `docker-compose.yml`
- `docker/**`
- `env-exemple`

The pull-request Docker job runs only:

1. Hadolint on `Dockerfile`;
2. `docker compose config --quiet`.

The purpose is to catch Dockerfile style/errors and invalid Compose configuration cheaply before merge. Runtime integration, image vulnerability scanning and HTTP smoke testing are deliberately deferred to the canonical `main` commit.

Application-only changes and dependency-only changes do not run Docker checks in the pull request.

## Main push CI

`ci-main.yml` runs on every push to `main`.

Django, migrations, Pylint and Sonar use the configured `current` Python version. Compatibility across every supported Python version has already been enforced by the pull-request gate.

Docker validation always runs on `main`, regardless of which files changed. This validates the exact canonical commit after integration.

## Docker validation on main

The full Docker job proves that the repository can produce and run a deployable container without known HIGH or CRITICAL vulnerabilities.

Its stages are:

1. lint `Dockerfile` with Hadolint;
2. validate `docker-compose.yml`;
3. build the Compose web image once;
4. run `python manage.py check` inside that image;
5. scan the validated image with Trivy;
6. fail on HIGH or CRITICAL findings;
7. start the already-built Compose stack with `--no-build`;
8. smoke-test the application root and an admin static asset;
9. tear the Compose stack down.

The Compose image is built once and reused for Django checks, Trivy and the smoke test.

## Security and reliability rules

All CI workflows follow these rules:

- `GITHUB_TOKEN` defaults to `contents: read`;
- third-party actions remain pinned to full commit SHAs;
- repository secrets are not exposed to fork pull requests;
- Sonar explicitly handles the absence of `SONAR_TOKEN` on forks;
- jobs have explicit timeouts;
- Python dependency caching uses `actions/setup-python` with `cache: pip`;
- stale branch and pull-request runs are cancelled with `concurrency`;
- no CI workflow uses `pull_request_target` to execute pull-request code.

## Why common jobs are not reusable workflows yet

GitHub recommends reusable workflows when workflows share the same implementation.

Oxomium currently protects `main` using exact status-check names. Moving Django or Pylint matrices behind reusable workflow calls can change the displayed check context and would require a coordinated ruleset migration.

For this refactor, preserving merge-gate compatibility is more important than eliminating YAML duplication. Shared Python policy is therefore centralized as data in `.github/ci-python-versions.json`, while the event entrypoints remain self-contained.

## Maintaining the workflows

When adding a check, classify it first:

- every branch commit: `ci-branch.yml`, only for cheap immediate feedback;
- before merge: `ci-pull-request.yml`;
- canonical integration verification: `ci-main.yml`;
- release/publication: `release.yml` or `docker-publish.yml`.

When changing Python support:

1. update `.github/ci-python-versions.json`;
2. validate the generated PR job names;
3. update the `main` ruleset required checks if the supported matrix changed;
4. merge only after the ruleset and matrix agree.

When adding a new required status check:

1. add and validate the job;
2. verify its exact check name in a pull request;
3. update the `main` ruleset;
4. only then remove or rename an old required check.

## Local equivalents

Before opening a pull request, use the current Python version from `.github/ci-python-versions.json`:

~~~bash
python manage.py test
python manage.py makemigrations --check --dry-run
pylint -E --load-plugins pylint_django \
  --django-settings-module=oxomium \
  --ignore-paths='.*/migrations/' \
  --ignore=__init__.py,manage.py \
  $(git ls-files '*.py')
~~~

For Docker-file changes:

~~~bash
docker compose config --quiet
hadolint Dockerfile
~~~

The full Docker build and runtime smoke test are performed after merge on `main`.

## References

- Workflow syntax and filtering: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Workflow trigger events: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Job conditions and skipped jobs: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions
- Required status check troubleshooting: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- Reusable workflows: https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- Secure use of Actions: https://docs.github.com/en/actions/reference/security/secure-use
- Python caching: https://docs.github.com/en/actions/tutorials/build-and-test-code/python
- Dependency review: https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-dependency-changes-in-a-pull-request
