#!/usr/bin/env bash
# This script ensures the database is created BEFORE Gunicorn runs.

# 1. Activate the Python virtual environment
source .venv/bin/activate

# 2. Run database migration/creation command
# Note: Render often automatically runs this in the build, but running it here
# ensures it happens before the app tries to connect.
python -c "from app import create_app, db; app = create_app(); with app.app_context(): db.create_all()"

# 3. Start Gunicorn using the correct factory command
# Gunicorn standard way to run a factory: call the resulting object 'app'
gunicorn --chdir app app:create_app
```
**2. Update Render Start Command**

Go to Render Web Service **Settings** and update the **Start Command** field to execute this script:

```bash
bash start.sh
```

**3. Commit and Push Changes:**

```bash
git add start.sh
git commit -m "FIX: Using start.sh script for reliable Gunicorn execution"
git push origin main
