# Generated by Django 5.1 on 2024-09-28 06:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0019_ticketsstatusmodel_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantmodel',
            name='email_template',
            field=models.CharField(default='   ', max_length=5000),
            preserve_default=False,
        ),
    ]
