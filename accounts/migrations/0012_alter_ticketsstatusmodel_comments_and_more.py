# Generated by Django 5.1 on 2024-09-14 07:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_ticketsstatusmodel_comments_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticketsstatusmodel',
            name='comments',
            field=models.CharField(max_length=800),
        ),
        migrations.AlterField(
            model_name='ticketsstatusmodel',
            name='date_reported',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
