from django.db import migrations


def standardize_max_amount(apps, schema_editor):
    RiskRule = apps.get_model("rules", "RiskRule")
    for rule in RiskRule.objects.select_for_update().filter(type="AMOUNT_LIMIT").iterator():
        parameters = rule.parameters
        if not isinstance(parameters, dict) or "max_amount_irr" not in parameters:
            continue
        old = parameters["max_amount_irr"]
        if "max_amount" in parameters:
            new = parameters["max_amount"]
            if type(old) is not type(new) or old != new:
                raise ValueError(f"Conflicting max_amount values in rule {rule.pk}; resolve before migration.")
        else:
            parameters["max_amount"] = old
        del parameters["max_amount_irr"]
        RiskRule.objects.filter(pk=rule.pk).update(parameters=parameters)


class Migration(migrations.Migration):
    dependencies = [("rules", "0004_protect_rule_revision")]
    operations = [migrations.RunPython(standardize_max_amount, migrations.RunPython.noop)]
