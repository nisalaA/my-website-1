from app import app, bcrypt
from models import db, User, ChatMessage

with app.app_context():
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()
    
    # Create admin user
    hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
    admin = User(username='admin', email='admin@example.com', password=hashed_password, is_admin=True)
    db.session.add(admin)
    db.session.commit()
    
    print("Database tables recreated successfully!")
    print("Admin user created successfully!")
    
    # Add sample data
    from app import add_sample_data
    add_sample_data()
    print("Sample data added successfully!")
