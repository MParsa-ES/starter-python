from django.db import migrations


def protect_decision_events(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rsk_decision_event_created_desc
        ON rsk_decision_events (created_at DESC, event_id DESC);

        CREATE INDEX IF NOT EXISTS idx_rsk_decision_event_decision_created
        ON rsk_decision_events (decision, created_at DESC);

        CREATE FUNCTION assessments_reject_decision_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Decision events are append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER assessments_decision_event_append_only
        BEFORE UPDATE OR DELETE ON rsk_decision_events
        FOR EACH ROW EXECUTE FUNCTION assessments_reject_decision_event_mutation();
    """)


def unprotect_decision_events(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        DROP TRIGGER IF EXISTS assessments_decision_event_append_only ON rsk_decision_events;
        DROP FUNCTION IF EXISTS assessments_reject_decision_event_mutation();
        DROP INDEX IF EXISTS idx_rsk_decision_event_decision_created;
        DROP INDEX IF EXISTS idx_rsk_decision_event_created_desc;
    """)


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0002_assessmentcreaterequest"),
    ]

    operations = [
        migrations.RunPython(protect_decision_events, unprotect_decision_events),
    ]