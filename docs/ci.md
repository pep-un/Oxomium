# Continuous Integration and Delivery Strategy

This document defines how Oxomium uses GitHub Actions and the responsibility of each workflow.

The design goal is to make the trigger and purpose of every workflow obvious from its filename while keeping pull-request checks compatible with the main branch ruleset.

## Workflow map

| Workflow | Trigger | Purpose | Expected cost |
| --- | --- | --- | --- |
| <code>.github/workflows/ci-branch.yml</code> | Push to any branch except main | Fast developer feedback on a representative Python version | Low |
| <code>.github/workflows/ci-pull-request.yml</code> | Pull request targeting main | Full merge gate and code-quality validation | Medium; Docker is conditional |
| <code>.github/workflows/ci-main.yml</code> | Push to main | Full post-merge validation of the canonical branch, including Docker | High |
| <code>.github/workflows/docker-publish.yml</code> | Manual workflow_dispatch | Explicit Docker Hub publication outside the release flow | On demand |
| <code>.github/workflows/release.yml</code> | Published GitHub Release | Build, scan, publish and attach release artifacts | Release only |

CI workflows are intentionally separated by event. A contributor should be able to infer when a workflow runs without first reading its YAML.

## Branch push CI

<code>ci-branch.yml</code> runs on every push to a branch other than main. Its purpose is fast feedback before or outside a pull request.

It runs Django tests, the migration consistency check and Pylint on Python 3.12. Python 3.12 is the representative fast-feedback runtime; the full supported-version matrix is checked on pull requests and main.

Older runs for the same branch are cancelled when a newer commit is pushed, avoiding runner time on stale revisions.

## Pull-request CI

<code>ci-pull-request.yml</code> runs for pull requests targeting main and is the merge gate.

It runs:

- Django tests and migration checks on Python 3.10, 3.11, 3.12, 3.13 and 3.14;
- Pylint on the same matrix;
- GitHub dependency review;
- SonarQube/SonarCloud analysis;
- Docker validation only for Docker-impacting changes.

The Python matrices use <code>fail-fast: false</code> so one incompatible version does not hide results from other supported versions.

### Required status checks

The current main ruleset requires:

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

These names must not be changed casually. Renaming a required job without updating the ruleset can block all pull requests.

### Conditional Docker validation

Docker validation is intentionally not filtered with <code>on.pull_request.paths</code>. The pull-request workflow always starts and a lightweight Detect Docker-impacting changes job decides whether Docker Validation runs.

Docker validation runs when a pull request changes one of:

- .github/workflows/ci-pull-request.yml
- .github/workflows/ci-main.yml
- Dockerfile
- .dockerignore
- docker-compose.yml
- docker/**
- env-exemple
- requirements.txt

Application-only changes under conformity/**, oxomium/** or manage.py do not run the expensive container pipeline on every pull-request update. They remain covered by Django, Pylint and Sonar before merge, while the canonical main commit is still validated in Docker after merge.

This job-level condition is deliberate. GitHub documents that a whole workflow skipped by branch/path filtering can leave required checks pending, while a job skipped by an if condition reports a successful skipped result.

## Main push CI

<code>ci-main.yml</code> runs on every push to main. It repeats the full supported Python matrix and Sonar analysis because main is the canonical integration state and may also receive administrative or automated updates.

Docker validation always runs on main regardless of which files changed, providing a final integration signal for the exact canonical commit.

## Docker validation stages

The Docker job proves that the repository can produce and run a deployable container without known HIGH or CRITICAL vulnerabilities.

Its stages are:

1. lint Dockerfile with Hadolint;
2. validate docker-compose.yml;
3. build the Compose web image once;
4. run python manage.py check inside that image;
5. scan the validated image with Trivy;
6. fail on HIGH or CRITICAL findings;
7. start the already-built Compose stack with --no-build;
8. smoke-test the application root and an admin static asset;
9. tear the Compose stack down.

The previous workflow built an image explicitly and later called docker compose up --build, which could perform redundant build work. The new flow builds the Compose image once and reuses it for Django checks, scanning and the smoke test.

## Security and reliability rules

All CI workflows follow these rules:

- GITHUB_TOKEN defaults to contents: read;
- third-party actions remain pinned to full commit SHAs;
- repository secrets are not exposed to fork pull requests;
- Sonar explicitly handles the absence of SONAR_TOKEN on forks;
- jobs have explicit timeouts;
- Python dependency caching uses actions/setup-python with cache: pip;
- stale branch and pull-request runs are cancelled with concurrency;
- no CI workflow uses pull_request_target to execute pull-request code.

## Why common jobs are not reusable workflows yet

GitHub recommends reusable workflows when workflows share the same implementation.

Oxomium currently protects main using exact status-check names. Moving Django or Pylint matrices behind reusable workflow calls can change the displayed check context and would require a coordinated ruleset migration.

For this refactor, preserving merge-gate compatibility is more important than eliminating YAML duplication. The three event entrypoints therefore remain self-contained.

A later refactor can extract common implementation after the branch ruleset is intentionally migrated and the resulting check names are verified.

## Maintaining the workflows

When adding a check, classify it first:

- every branch commit: ci-branch.yml, only for cheap immediate feedback;
- before merge: ci-pull-request.yml;
- canonical integration verification: ci-main.yml;
- release/publication: release.yml or docker-publish.yml.

When adding a new required status check:

1. add and validate the job;
2. verify its exact check name in a pull request;
3. update the main ruleset;
4. only then remove or rename an old required check.

When Docker inputs change, update the Docker-impacting file detector in ci-pull-request.yml.

## Local equivalents

Before opening a pull request:

~~~bash
python manage.py test
python manage.py makemigrations --check --dry-run
pylint -E --load-plugins pylint_django \
  --django-settings-module=oxomium \
  --ignore-paths='.*/migrations/' \
  --ignore=__init__.py,manage.py \
  $(git ls-files '*.py')
~~~

For Docker-impacting changes:

~~~bash
docker compose config --quiet
docker compose build web
docker compose up --no-build --detach --wait --wait-timeout 60
curl --fail http://127.0.0.1:3000/
docker compose down --volumes --remove-orphans
~~~

## References

- Workflow syntax and filtering: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Workflow trigger events: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Job conditions and skipped jobs: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions
- Required status check troubleshooting: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- Reusable workflows: https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- Secure use of Actions: https://docs.github.com/en/actions/reference/security/secure-use
- Python caching: https://docs.github.com/en/actions/tutorials/build-and-test-code/python
- Dependency review: https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-dependency-changes-in-a-pull-request
