# Generated by Django 3.2.19 on 2023-10-18 04:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0015_auto_20230911_1103'),
    ]

    operations = [
        migrations.AlterField(
            model_name='componentsubscription',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
