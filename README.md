[![Pylint Error](https://github.com/pep-un/Oxomium/actions/workflows/pylint.yml/badge.svg)](https://github.com/pep-un/Oxomium/actions/workflows/pylint.yml)
[![Django CI](https://github.com/pep-un/Oxomium/actions/workflows/django.yml/badge.svg)](https://github.com/pep-un/Oxomium/actions/workflows/django.yml)
[![CodeQL](https://github.com/pep-un/Oxomium/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/pep-un/Oxomium/actions/workflows/codeql-analysis.yml)
[![Dependency Review](https://github.com/pep-un/Oxomium/actions/workflows/dependency-review.yml/badge.svg?branch=main)](https://github.com/pep-un/Oxomium/actions/workflows/dependency-review.yml)

# Oxomium Project

Oxomium is an opensource projet build to help company to manage the cybersecurity compliance of organisations. 

It provide help to CISO or other security people to follow conformity to a Policy.

Lot of opther feature is plan as managing unconformity, action plan, provider auditing, etc...


# Instalation 

## Pre-reqisit :  
you should have python v3.8+

on a Debian 11 system : 
```Shell
apt install python3 python3-pip python3-venv
```


Not tested yet but it should be working like that : 

```Shell
git clone https://github.com/pep-un/Oxomium.git
cd Oxomium
python3 -m venv .
source bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

If you want to load the default data (ISO27001 and NIST Policy): 
```Shelll
python manage.py loaddata conformity/fixture/Template-Policy-ISO-27k1.yaml
python manage.py loaddata conformity/fixture/Template-Policy-NIST.yaml
```

For non-production usage
```Shell
python manage.py runserver
```

For production usage
Change the following parameter of `oxomium/settings.py`:
- `SECURITY_KEY` with a uniq key, a script avayable under scripts folder
- `DEBUG` from `False` to `True`
- `ALLOWED_HOSTS` according to your configuration
