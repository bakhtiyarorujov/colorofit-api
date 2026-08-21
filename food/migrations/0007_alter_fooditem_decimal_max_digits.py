from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('food', '0006_alter_waterintake_intake_type_delete_waterintaketype'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fooditem',
            name='calories',
            field=models.DecimalField(max_digits=10, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='protein',
            field=models.DecimalField(max_digits=10, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='carbohydrates',
            field=models.DecimalField(max_digits=10, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='fats',
            field=models.DecimalField(max_digits=10, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='trans_fat',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='saturated_fat',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='vitamin_a',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='vitamin_c',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='vitamin_d',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='vitamin_e',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='vitamin_k',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='mineral_calcium',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='mineral_iron',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='mineral_sodium',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='mineral_potassium',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
        migrations.AlterField(
            model_name='fooditem',
            name='mineral_zink',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0.0),
        ),
    ]
