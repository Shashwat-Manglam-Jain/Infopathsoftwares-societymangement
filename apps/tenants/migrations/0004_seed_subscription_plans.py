from django.db import migrations


def seed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('tenants', 'SubscriptionPlan')
    plans = [
        {
            'name': 'Starter',
            'max_members': 200,
            'max_users': 5,
            'max_branches': 2,
            'price_monthly': 2000,
            'features': {
                'banking': 'All banking features',
                'support': 'Email support',
            },
        },
        {
            'name': 'Professional',
            'max_members': 1000,
            'max_users': 15,
            'max_branches': 5,
            'price_monthly': 5000,
            'features': {
                'sms': 'SMS notifications',
                'support': 'Priority support',
            },
        },
        {
            'name': 'Enterprise',
            'max_members': 100000,
            'max_users': 50,
            'max_branches': 20,
            'price_monthly': 12000,
            'features': {
                'support': 'Dedicated support',
                'branding': 'Custom branding',
            },
        },
    ]
    for p in plans:
        SubscriptionPlan.objects.get_or_create(name=p['name'], defaults=p)


def unseed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('tenants', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(name__in=['Starter', 'Professional', 'Enterprise']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0003_society_fax_society_name_regional'),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]
