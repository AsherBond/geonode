# Generated by Django 4.2.9 on 2024-06-24 15:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("upload", "0046_dataset_migration"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resourcehandlerinfo",
            name="id",
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
        ),
        migrations.AlterField(
            model_name="uploadparallelismlimit",
            name="max_number",
            field=models.PositiveSmallIntegerField(
                default=5, help_text="The maximum number of parallel uploads (0 to 32767)."
            ),
        ),
        migrations.DeleteModel(
            name="Upload",
        ),
    ]