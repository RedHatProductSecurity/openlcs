# Generated by Django 3.2.14 on 2022-08-16 06:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_producttreenode_unique_parent_content_object'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ReleasePackage',
        ),
    ]
