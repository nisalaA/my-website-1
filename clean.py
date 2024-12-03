import shutil
import os

# Remove migrations directory if it exists
if os.path.exists('migrations'):
    shutil.rmtree('migrations')
    print("Removed existing migrations directory")
