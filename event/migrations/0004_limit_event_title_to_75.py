import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("event", "0003_limit_event_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="title",
            field=models.CharField(
                max_length=100,
                validators=[django.core.validators.MaxLengthValidator(75)],
            ),
        ),
    ]
