# Generated by Django 5.1 on 2024-09-14 07:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_alter_ticketsstatusmodel_comments_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticketsstatusmodel',
            name='date_reported',
            field=models.DateField(auto_now_add=True),
        ),
    ]
