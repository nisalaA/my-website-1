from flask.cli import FlaskGroup
import click
from app import app, db, User, Product, Order, OrderItem, bcrypt

cli = FlaskGroup(app)

@cli.command("create_db")
def create_db():
    """Creates the database tables."""
    db.create_all()
    print("Database tables created!")

@cli.command("drop_db")
def drop_db():
    """Drops the database tables."""
    if click.confirm('Are you sure you want to drop all tables?', abort=True):
        db.drop_all()
        print("Database tables dropped!")

@cli.command("create_admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
def create_admin(username, email, password):
    """Creates an admin user."""
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(
        username=username,
        email=email,
        password=hashed_password,
        is_admin=True
    )
    db.session.add(user)
    db.session.commit()
    print(f"Admin user {username} created successfully!")

@cli.command("create_test_products")
def create_test_products():
    """Creates some test products."""
    products = [
        {
            "name": "Gaming Laptop",
            "description": "High-performance gaming laptop with RTX 3080",
            "price": 1499.99,
            "stock": 10,
            "image_url": "/static/images/laptop.jpg"
        },
        {
            "name": "Wireless Mouse",
            "description": "Ergonomic wireless mouse with long battery life",
            "price": 29.99,
            "stock": 50,
            "image_url": "/static/images/mouse.jpg"
        },
        {
            "name": "Mechanical Keyboard",
            "description": "RGB mechanical keyboard with Cherry MX switches",
            "price": 99.99,
            "stock": 30,
            "image_url": "/static/images/keyboard.jpg"
        }
    ]

    for product_data in products:
        product = Product(**product_data)
        db.session.add(product)
    
    db.session.commit()
    print(f"Created {len(products)} test products!")

@cli.command("list_users")
def list_users():
    """Lists all users in the database."""
    users = User.query.all()
    if not users:
        print("No users found.")
        return

    print("\nUsers:")
    print("-" * 50)
    for user in users:
        print(f"ID: {user.id}")
        print(f"Username: {user.username}")
        print(f"Email: {user.email}")
        print(f"Admin: {user.is_admin}")
        if user.full_name:
            print(f"Full Name: {user.full_name}")
            print(f"Address: {user.address}")
            print(f"City: {user.city}, {user.state} {user.zip_code}")
        print("-" * 50)

@cli.command("list_products")
def list_products():
    """Lists all products in the database."""
    products = Product.query.all()
    if not products:
        print("No products found.")
        return

    print("\nProducts:")
    print("-" * 50)
    for product in products:
        print(f"ID: {product.id}")
        print(f"Name: {product.name}")
        print(f"Price: ${product.price}")
        print(f"Stock: {product.stock}")
        print("-" * 50)

if __name__ == '__main__':
    cli()
