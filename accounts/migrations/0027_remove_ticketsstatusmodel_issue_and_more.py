# Generated by Django 5.1 on 2024-10-20 06:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0026_alter_ticketsstatusmodel_commenthistory'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticketsstatusmodel',
            name='issue',
        ),
        migrations.AlterField(
            model_name='ticketsstatusmodel',
            name='ticket_status',
            field=models.CharField(choices=[('PENDING', 'PENDING'), ('INPROGRESS', 'INPROGRESS'), ('COMPLETED', 'COMPLETED')], default='PENDING', max_length=20),
        ),
    ]
