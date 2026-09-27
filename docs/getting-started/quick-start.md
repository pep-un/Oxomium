# Quick start

This guide describes a practical first workflow after installing Oxomium.

## 1. Sign in

Open the Oxomium instance and sign in with an account allowed to manage the application.

For administrative operations, the Django administration interface is available under:

```text
/django-backend/
```

## 2. Create an organization

From the Oxomium interface:

1. open **Organizations**;
2. create a new organization;
3. complete the organization information and save it.

An organization is the main scope used to evaluate conformity and to manage audits, controls, findings, actions, and indicators.

## 3. Add a framework

There are two common ways to start with a framework.

### Load a framework shipped with Oxomium

The repository contains Django fixtures for example/reference frameworks.

To load ISO 27001:

```shell
python manage.py loaddata conformity/fixtures/iso-27001.yaml
```

To load the NIST Cybersecurity Framework fixture:

```shell
python manage.py loaddata conformity/fixtures/nist-csf.yaml
```

For Docker deployments, run the same command inside the application container:

```shell
docker compose exec web python manage.py loaddata conformity/fixtures/iso-27001.yaml
```

Loading a fixture changes application data. Review the fixture and back up an existing production database before loading data into an established instance.

### Create or import a framework

Frameworks and requirements can also be managed through the Django administration interface.

1. Open **Frameworks** and create the framework.
2. Open **Requirements**.
3. Use the import/export actions provided by the Django import/export integration to obtain or populate a dataset.
4. Import the completed requirements into Oxomium.

The exact columns available during import/export follow the current Oxomium data model.

## 4. Apply the framework to the organization

Edit the organization and associate the relevant framework.

Oxomium then creates the conformity data needed to evaluate the framework requirements for that organization.

## 5. Start the assessment

Once the organization and framework are available, the main functional areas can be used together:

- **Conformity** to evaluate framework requirements;
- **Audits** and **Findings** to record assessment activity and observations;
- **Controls** and **Control points** to track verification activities;
- **Actions** to manage remediation work;
- **Indicators** to track measurable values over time.

A useful starting sequence is to establish the conformity baseline first, then record controls, audits, findings, actions, and indicators as needed.

## Next steps

- [Installation documentation](../installation/main.md)
- [Upgrade and maintenance](../operations/upgrade.md)
- [Security architecture](../security/architecture.md)
