[![Main CI](https://github.com/pep-un/Oxomium/actions/workflows/ci-main.yml/badge.svg?branch=main)](https://github.com/pep-un/Oxomium/actions/workflows/ci-main.yml)\n\n[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Technical Debt](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=sqale_index)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=pep-un_Oxomium&metric=coverage)](https://sonarcloud.io/summary/new_code?id=pep-un_Oxomium)


# Oxomium Project

Oxomium is an opensource project build to help company to manage the cybersecurity compliance of organisations. 

It provides help to CISO or other security people to follow conformity to a Framework.

More information on [Oxomium Website](https://www.oxomium.org).

An online demonstration in available with user `demo` and password `6NLYm6F4PBBQBjc`:  [Oxomium Demo](https://demo.oxomium.org)

A wiki page detail the process of [installation](https://github.com/pep-un/Oxomium/wiki/Instalation).\n\nThe CI/CD workflow responsibilities and trigger strategy are documented in [docs/ci.md](docs/ci.md).

## Docker image and releases

Publishing a GitHub Release for a `v<semver>` tag builds the exact released tag and publishes
`docker.io/pepun/oxomium` with semantic-version tags and `latest`.

The release workflow also attaches these files to the GitHub Release:

- `oxomium-<version>.tar.gz`, built directly from the released Git commit;
- `oxomium-<version>.sbom.cdx.json`, a CycloneDX SBOM generated from the delivered tarball;
- `oxomium-<version>-docker.sbom.cdx.json`, a CycloneDX SBOM generated from the final Docker image;
- `SHA256SUMS`, containing SHA-256 checksums for the GitHub release artifacts.

Before publication, the final Docker image is scanned with Trivy for HIGH and
CRITICAL vulnerabilities. SBOM publication is deferred until the explicit final
release-upload step. A build, SBOM, vulnerability scan, checksum, Docker
publication, or release-upload failure fails the release workflow.

Docker Hub publication requires the `DOCKERHUB_USERNAME` and
`DOCKERHUB_TOKEN` repository secrets. The workflow uses the GitHub token only
to attach artifacts to the release.

Pull and run the latest image with:

```shell
docker pull docker.io/pepun/oxomium:latest
docker run --rm --env-file env-exemple -p 8000:8000 docker.io/pepun/oxomium:latest
```

For the included Compose setup, run `docker compose up --build`.
