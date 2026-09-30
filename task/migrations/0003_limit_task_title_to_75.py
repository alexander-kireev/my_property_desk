import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("task", "0002_limit_task_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="title",
            field=models.CharField(
                max_length=100,
                validators=[django.core.validators.MaxLengthValidator(75)],
            ),
        ),
    ]
