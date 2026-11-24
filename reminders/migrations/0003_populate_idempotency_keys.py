
from django.db import migrations


def populate_idempotency_keys(apps, schema_editor):
    ReminderLog = apps.get_model("reminders", "ReminderLog")
    database = schema_editor.connection.alias

    logs = (
        ReminderLog.objects.using(database)
        .filter(idempotency_key__isnull=True)
        .only("pk")
        .iterator()
    )

    for log in logs:
        log.idempotency_key = f"legacy-{log.pk}"
        log.save(
            using=database,
            update_fields=["idempotency_key"],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("reminders", "0002_reminderlog_attempt_number_and_more"),
    ]

    operations = [
        migrations.RunPython(
            populate_idempotency_keys,
            migrations.RunPython.noop,
        ),
    ]
