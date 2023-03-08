#!/bin/bash

flake8 --count django_auto_rebase
isort -rc -c django_auto_rebase
black --check django_auto_rebase
mypy
