from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="customer",
            old_name="phone",
            new_name="primary_phone",
        ),
        migrations.AddField(
            model_name="customer",
            name="secondary_phone",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
