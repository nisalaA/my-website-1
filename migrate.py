from app import app, db
from flask_migrate import Migrate
from alembic.command import init as alembic_init
from alembic.command import revision as alembic_revision
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config

# Initialize migration
migrate = Migrate(app, db)

if __name__ == '__main__':
    with app.app_context():
        # Create alembic.ini
        config = Config()
        config.set_main_option("script_location", "migrations")
        config.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])
        
        try:
            # Create the migrations directory
            alembic_init(config, "migrations")
            
            # Create an automatic migration
            alembic_revision(config, autogenerate=True, message="Add shipping info and order item price")
            
            # Apply the migration
            alembic_upgrade(config, "head")
            
            print("Migration completed successfully!")
        except Exception as e:
            print(f"Error during migration: {str(e)}")
