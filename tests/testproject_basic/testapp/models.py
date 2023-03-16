from django.db import models


class Reporter(models.Model):
    full_name = models.CharField(max_length=71)
    handle = models.CharField(max_length=50, null=True)
