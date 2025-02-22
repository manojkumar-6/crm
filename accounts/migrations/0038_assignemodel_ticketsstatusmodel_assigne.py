# Generated by Django 5.1 on 2025-02-23 03:35

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0037_remove_ticketsmodel_image_path_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssigneModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.tenantmodel')),
            ],
        ),
        migrations.AddField(
            model_name='ticketsstatusmodel',
            name='assigne',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='accounts.assignemodel'),
        ),
    ]
