from django.db import migrations

def backfill_menu_item(apps, schema_editor):
    OrderItem = apps.get_model("orders", "OrderItem")

    # Try common legacy field names to auto-backfill if your table had another field earlier.
    # If none exist, we leave it NULL for now; the next migration will fail only if NULLs remain.
    legacy_fields = ["item", "product", "menuitem_id", "menuitem", "menu_item_id"]

    # Does OrderItem have any of these legacy fields? If yes, copy values into the new menu_item.
    # (Using raw SQL-ish access via .values() keeps it safe even if the ORM fields don’t exist.)
    has_any = False
    for lf in legacy_fields:
        try:
            # Quick existence check by trying to evaluate a values list including that key
            OrderItem.objects.values(lf)[:1]
            has_any = True
            legacy_field = lf
            break
        except Exception:
            continue

    if has_any:
        # Bulk backfill from legacy field (id field if value is a dict)
        for oi in OrderItem.objects.all().only("id"):
            try:
                old_val = OrderItem.objects.filter(pk=oi.pk).values_list(legacy_field, flat=True).first()
                if old_val and getattr(oi, "menu_item_id", None) is None:
                    oi.menu_item_id = old_val  # expect an integer PK
                    oi.save(update_fields=["menu_item"])
            except Exception:
                pass
    else:
        # If there is NO legacy field, and you know all existing rows are safe to keep NULL,
        # we just leave them as is. The next migration will enforce NOT NULL,
        # so make sure there are no remaining NULLs or delete bad rows.
        pass

def noop_reverse(apps, schema_editor):
    # No reverse operation
    pass

class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_alter_order_options_remove_order_amount_paid_and_more"),  # replace with the file generated in Step 2
    ]

    operations = [
        migrations.RunPython(backfill_menu_item, noop_reverse),
    ]
