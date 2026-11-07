from django.db import migrations


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION rules_reject_history_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Rule revisions are append-only';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER rules_revision_append_only
        BEFORE UPDATE OR DELETE ON rules_rulerevision
        FOR EACH ROW EXECUTE FUNCTION rules_reject_history_mutation();
    """)


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER IF EXISTS rules_revision_append_only ON rules_rulerevision;")
        schema_editor.execute("DROP FUNCTION IF EXISTS rules_reject_history_mutation();")


class Migration(migrations.Migration):
    dependencies = [("rules", "0003_rulecreaterequest")]
    operations = [migrations.RunPython(protect, unprotect)]
