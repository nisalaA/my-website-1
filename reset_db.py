import os
from app import app, db

# Delete the existing database file
db_path = 'instance/shop_v2.db'
if os.path.exists(db_path):
    os.remove(db_path)
    print("Removed existing database")

# Create all tables
with app.app_context():
    db.create_all()
    print("Created new database with updated schema")

    # Add sample data
    from app import add_sample_data
    add_sample_data()
