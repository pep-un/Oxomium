[![Pylint Error](https://github.com/pep-un/Oxomium/actions/workflows/pylint.yml/badge.svg)](https://github.com/pep-un/Oxomium/actions/workflows/pylint.yml)
[![Django CI](https://github.com/pep-un/Oxomium/actions/workflows/django.yml/badge.svg)](https://github.com/pep-un/Oxomium/actions/workflows/django.yml)
[![CodeQL](https://github.com/pep-un/Oxomium/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/pep-un/Oxomium/actions/workflows/codeql-analysis.yml)
[![Dependency Review](https://github.com/pep-un/Oxomium/actions/workflows/dependency-review.yml/badge.svg?branch=main)](https://github.com/pep-un/Oxomium/actions/workflows/dependency-review.yml)

# Oxomium Project

Oxomium is an opensource projet build to help company to manage the cybersecurity compliance of organisations. 

It provide help to CISO or other security people to follow conformity to a Policy.

Lot of opther feature is plan as managing unconformity, action plan, provider auditing, etc...


# Instalation 

Pre-reqisit :  you should have python v3.8+

Not tested yet but it should be working like that : 

```Shell
git clone https://github.com/pep-un/Oxomium.git
cd oxomium
pip install -r requirements.txt
python manage.py createsuperuser
python manage.py loaddata
```

for non-production usage
```Shell
python manage.py runserver
```
