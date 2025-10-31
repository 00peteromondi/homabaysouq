from django.db import migrations

def skip_if_exists(apps, schema_editor):
    # Get the database being used
    db = schema_editor.connection.alias
    
    # Check if the table already exists
    table_name = 'listings_listing_favorited_by'
    if table_name in schema_editor.connection.introspection.table_names():
        # Table exists, skip creation
        return
    
    # If table doesn't exist, the regular migration (0020) will create it
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('listings', '0022_orderitem_shipped_orderitem_shipped_at_and_more'),
    ]

    operations = [
        migrations.RunPython(skip_if_exists, reverse_code=migrations.RunPython.noop),
    ]