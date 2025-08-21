from django.db import migrations

def backfill_menu_item(apps, schema_editor):
    OrderItem = apps.get_model("orders", "OrderItem")
    MenuItem = apps.get_model("menu", "MenuItem")

    # Pick the first available MenuItem to assign (you can change the logic if needed)
    first_item = MenuItem.objects.order_by("id").first()

    if first_item is None:
        # No menu items exist; safest is to delete orphan order items with NULL menu_item
        OrderItem.objects.filter(menu_item__isnull=True).delete()
        return

    # Backfill any NULL menu_item with the first menu item
    OrderItem.objects.filter(menu_item__isnull=True).update(menu_item_id=first_item.id)

def noop_reverse(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_alter_orderitem_menu_item"),
    ]

    operations = [
        migrations.RunPython(backfill_menu_item, noop_reverse),
    ]
