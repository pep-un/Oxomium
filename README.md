[![Main CI](https://github.com/pep-un/Oxomium/actions/workflows/ci-main.yml/badge.svg?branch=main)](https://github.com/pep-un/Oxomium/actions/workflows/ci-main.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=coverage)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)

# Oxomium

Oxomium is an open-source governance, risk, and compliance (GRC) application built with Django. It helps security teams manage cybersecurity frameworks, requirements, controls, audits, findings, and remediation actions from a single application.

More information is available on the [Oxomium website](https://www.oxomium.org).

## Documentation

The repository documentation is the canonical documentation source. Start with [docs/main.md](docs/main.md).

Start with the [Quick start](docs/getting-started/quick-start.md) after installation.

The installation documentation covers:

- [manual Linux installation](docs/installation/manual-linux.md);
- [Docker with system Nginx](docs/installation/docker-system-nginx.md);
- [Docker with integrated Nginx](docs/installation/docker-integrated-nginx.md).

Operational guidance is available in [Upgrade Oxomium](docs/operations/upgrade.md), and implementation-level security information is documented in [Security architecture](docs/security/architecture.md).

The historical GitHub Wiki has been consolidated into the versioned documentation stored in this repository.

## Quick start with Docker

Create a local environment file and start the default development stack:

```shell
cp .env.example .env
docker compose up --build
```

The default Compose file is `compose.yaml`.

For production deployments, use an explicit Oxomium release tag instead of `latest` and follow one of the deployment guides above.

A published image is available from Docker Hub:

```shell
docker pull docker.io/pepun/oxomium:latest
docker run --rm --env-file .env -p 8000:8000 docker.io/pepun/oxomium:latest
```

## Online demonstration

An online demonstration is available at [demo.oxomium.org](https://demo.oxomium.org) with:

- username: `demo`
- password: `6NLYm6F4PBBQBjc`

Do not reuse these credentials for any other environment.

## Development

Create a virtual environment and install the dependencies:

```shell
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the test suite with:

```shell
python manage.py test
```

Development and CI guidance is documented in [docs/development/ci.md](docs/development/ci.md). Contribution guidelines are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Deployment resources

Reusable deployment resources are grouped by technology:

```text
deploy/
├── docker/
├── nginx/
└── systemd/
```

Utility scripts that are not deployment configuration live under `scripts/`.

## Docker images and releases

Publishing a GitHub Release for a `v<semver>` tag builds the exact released tag and publishes `docker.io/pepun/oxomium` with semantic-version tags and `latest`.

The release workflow also attaches:

- `oxomium-<version>.tar.gz`, built directly from the released Git commit;
- `oxomium-<version>.sbom.cdx.json`, a CycloneDX SBOM generated from the delivered tarball;
- `oxomium-<version>-docker.sbom.cdx.json`, a CycloneDX SBOM generated from the final Docker image;
- `SHA256SUMS`, containing SHA-256 checksums for the release artifacts.

Before publication, the final Docker image is scanned with Trivy for HIGH and CRITICAL vulnerabilities. A build, SBOM, vulnerability scan, checksum, Docker publication, or release-upload failure fails the release workflow.

## Security

See [SECURITY.md](SECURITY.md) for the current security policy.

## License

Oxomium is distributed under the terms in [LICENSE](LICENSE).
