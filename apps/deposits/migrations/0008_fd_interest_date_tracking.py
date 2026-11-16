from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('deposits', '0007_rd_locking_and_frequency'),
    ]

    operations = [
        migrations.AddField(
            model_name='fixeddeposit',
            name='last_interest_calculated_date',
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='fixeddeposit',
            name='last_interest_posted_date',
            field=models.DateField(null=True, blank=True),
        ),
    ]
