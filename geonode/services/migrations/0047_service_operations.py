# Generated by Django 3.2.4 on 2021-09-03 08:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0046_service_extra_queryparams'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='operations',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]