# Generated by Django 3.2.19 on 2023-10-30 02:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0016_alter_componentsubscription_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='missingcomponent',
            name='retry_count',
            field=models.IntegerField(default=0),
        ),
    ]
