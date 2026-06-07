from datetime import time

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mood', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='ai_personalization',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='checkin_reminders',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='crisis_resources_region',
            field=models.CharField(choices=[('uk', 'United Kingdom'), ('in', 'India'), ('us', 'United States'), ('global', 'Global')], default='uk', max_length=20),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='email_notifications',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='language',
            field=models.CharField(choices=[('en', 'English'), ('hi', 'Hindi'), ('ta', 'Tamil'), ('bn', 'Bengali'), ('te', 'Telugu'), ('mr', 'Marathi')], default='en', max_length=10),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='private_profile',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='reduce_motion',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='reminder_time',
            field=models.TimeField(blank=True, default=time(20, 0), null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='show_progress_stats',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='theme',
            field=models.CharField(choices=[('system', 'Use device setting'), ('dark', 'Dark'), ('light', 'Light'), ('calm', 'Calm')], default='dark', max_length=20),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='weekly_summary',
            field=models.BooleanField(default=True),
        ),
    ]
