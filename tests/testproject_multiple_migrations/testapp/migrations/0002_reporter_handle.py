# Generated by Django 4.1.7 on 2023-03-03 16:46

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("testapp", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="reporter",
            name="handle",
            field=models.CharField(max_length=50, null=True),
        )
    ]
