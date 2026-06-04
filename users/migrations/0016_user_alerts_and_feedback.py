from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_waterintaketype_amount_ml'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='alert_meal_reminders',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='alert_water_reminders',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='alert_weekly_summary',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='alert_goal_achievements',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(default=0)),
                ('message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='feedback_entries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
    ]
