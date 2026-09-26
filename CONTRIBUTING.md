# Continuous integration and merge checks

Pull requests targeting `main` are validated by GitHub Actions and SonarQube Cloud before they are merged.

## Required checks

Repository branch protection should require the following checks on `main`:

- **Django CI** — the complete Python matrix defined in `.github/workflows/django.yml`. It runs the Django test suite on every supported Python version and runs `python manage.py makemigrations --check --dry-run` so model changes without committed migrations fail CI.
- **Pylint** — the complete Python matrix defined in `.github/workflows/pylint.yml`. It runs Pylint with the Django plugin on pull requests and reports Python errors before merge.
- **Dependency Review** — reviews dependency changes introduced by pull requests and reports vulnerable dependencies.
- **SonarQube Cloud Quality Gate** — the SonarQube Cloud quality gate for the pull request. The GitHub Actions `SonarCloud` job performs the analysis; the quality-gate check reported by SonarQube Cloud is the result that must be required for merge.

The Docker workflow remains a useful CI signal, but it is not part of the minimum required checks defined by issue #140.

## SonarCloud credentials

For pushes and pull requests whose head branch belongs to this repository, a missing `SONAR_TOKEN` is a CI configuration error and the `SonarCloud` workflow fails explicitly.

GitHub does not expose repository secrets to workflows triggered by pull requests from forks. Such pull requests therefore cannot run the token-based SonarCloud scan with the current workflow. They still run checks that do not require repository secrets. Maintainers must account for this GitHub security restriction when defining the required SonarQube Cloud check.

## Branch protection

Workflow files alone do not make checks mandatory. The `main` branch protection/ruleset must be configured in GitHub so the required checks above must pass before merging.

After changing a workflow name or job name, verify the branch-protection configuration: required checks are identified by their reported check names and a rename can leave protection pointing at an obsolete check.

## Validation procedure

Use a pull request as the reference validation and confirm that:

1. Django CI runs for every supported Python version and a deliberately missing migration makes the corresponding CI run fail.
2. A deliberately failing Django test makes Django CI fail.
3. Pylint runs for every supported Python version and a deliberately introduced Pylint error makes the corresponding check fail.
4. A dependency change rejected by Dependency Review makes that check fail.
5. SonarCloud analysis runs for repository pull requests, and a failed SonarQube Cloud Quality Gate is visible as a failing check.
6. GitHub prevents merging while any configured required check is failing or pending.

Do not merge the deliberately broken validation commits. Revert or replace them after confirming the expected blocking behaviour.
