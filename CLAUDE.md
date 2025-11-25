# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Point of Sales (POS) system with **dual implementations**: both Python/Flask and Node.js/Express versions exist in the same repository. The Flask version (app.py) is the primary production implementation deployed via Waitress. The Node.js version (app.js) exists as a parallel implementation but is not actively used.

**Database**: Azure SQL Server (accessed via ODBC Driver 18 for SQL Server)
**Primary Stack**: Python 3.x + Flask + Jinja2 templates
**Secondary Stack**: Node.js + Express + EJS (not actively deployed)

## Running the Application

### Python/Flask (Production)

```bash
# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export DB_HOST=your-azure-sql-server.database.windows.net
export DB_USER=your-username
export DB_PASSWORD=your-password
export DB_NAME=PosApp
export SECRET_KEY=your-secret-key

# Run development server
python app.py

# Run production server (Waitress)
waitress-serve --listen=0.0.0.0:5000 app:app
```

The application runs on port 5000 by default.

### Node.js/Express (Alternative - Not Deployed)

The Node.js version exists in app.js but is not the primary deployment target. If you need to work with it:

```bash
# Create .env file with database credentials
# Install dependencies (package.json would be needed)
# Run: node app.js
```

## Architecture

### Database Layer (db.py)

The `@with_db` decorator is used throughout the Flask app to manage database connections:
- Automatically opens/closes connections and cursors
- Handles exceptions and returns JSON error responses
- Usage: Decorate route functions with `@with_db` which injects `cursor` and `conn` parameters

```python
@app.route('/some-route')
@with_db
def my_route(cursor, conn):
    cursor.execute("SELECT * FROM Table")
    # Connection automatically closed after function returns
```

Helper function `rows_to_dict_list(cursor)` converts pyodbc cursor results to list of dictionaries.

### User Roles and Authentication

Three distinct user roles with separate database tables:
- **Administrator** (table: Administrator) - Full system access, manages employees/products
- **Employee** (table: Employee) - Department-based access, processes transactions
- **Customer** (table: Customer) - Shopping, orders, wishlists

Authentication is implemented in app.py:87-127:
- Login checks all three user tables (Administrator, Employee, Customer)
- Session stores `user_id` and `role`
- Passwords stored in plain text (security issue - no hashing)

### Shopping Bag/Cart System

The Bag table has dual ownership - customers OR employees can have bags:
- Customer bags: `CustomerID IS NOT NULL, EmployeeID IS NULL`
- Employee bags: `EmployeeID IS NOT NULL, CustomerID IS NULL`

Function `get_bag_owner_from_session()` in app.py:16-23 determines bag ownership based on session role.

### Core Database Tables

Key tables (see script.sql for full schema):
- **Product** - ProductID, Name, Description, Price, QuantityInStock, DepartmentID, ImageURL, OnSale, IsActive
- **Department** - Product categorization
- **Bag** - Shopping cart (CustomerID OR EmployeeID, ProductID, Quantity)
- **Orders** - Customer orders linked to Customer
- **SalesTransaction** - Completed transactions (CustomerID OR EmployeeID)
- **Transaction_Details** - Line items for transactions
- **ShoppingList** / **ShoppingListItem** - Customer wishlists
- **Inventory** - Stock levels with ReorderLevel
- **Reorder_Alerts** - Low stock notifications
- **Holiday_Sales** / **SeasonalSale** - Promotional periods

### Route Structure (Flask)

The monolithic app.py contains all routes:
- `/` - Home page with product catalog (filtered by department client-side)
- `/login`, `/register` - Authentication
- `/admin`, `/employee`, `/customer` - Role-specific dashboards
- `/api/*` - JSON endpoints for AJAX operations
- `/bag/*` - Shopping cart operations
- `/api/reports/*` - Various sales/inventory/customer reports
- `/checkout` - Order processing

The Node.js version in app.js shows a modularized structure with separate route files (routes/auth.js, routes/products.js, etc.) but this is not the active codebase.

### Template System

Templates use Jinja2 (Flask):
- `templates/` contains all HTML files
- `templates/partials/` for reusable components
- `static/css/` and `static/js/` for assets

Key templates:
- index.html - Product catalog
- login.html / register.html - Auth forms
- admin_dashboard.html, employee_dashboard.html, customer_dashboard.html - Role dashboards
- Various report templates (*_report.html)

### Context Processor

app.py:25-37 implements `inject_bag_count()` context processor:
- Makes `bag_count` available to all templates
- Queries Bag table sum based on current user's role and ID
- Used for displaying cart item count in navigation

## Development Notes

### Database Connection Requirements

All database credentials must be set as environment variables:
- `DB_HOST` - Azure SQL Server hostname (format: servername.database.windows.net)
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_NAME` - Database name (default: PosApp)
- `SECRET_KEY` - Flask session secret (defaults to 'dev_secret_123!@#' if not set)

Connection string uses ODBC Driver 18 with encryption enabled and TrustServerCertificate=yes.

### Deployment

The Procfile indicates Heroku/Azure deployment using Waitress:
```
web: waitress-serve --listen=0.0.0.0:5000 app:app
```

GitHub Actions workflow exists at `.github/workflows/deploy-to-azure.yml` for automated Azure deployment.

### Security Considerations

- Passwords are stored in plain text in the database (no hashing)
- SQL queries use parameterized queries to prevent SQL injection
- CORS is enabled globally via Flask-CORS
- Session cookies have 24-hour expiration (in Node.js version)

### Working with Both Codebases

When modifying functionality:
1. The Python/Flask version (app.py) is the authoritative implementation
2. The Node.js version (app.js) is outdated and not deployed
3. Focus changes on app.py unless explicitly migrating to Node.js
4. Template changes in templates/ (Jinja2) would need conversion to views/ (EJS) for Node.js

### Database Schema

The complete schema is in script.sql. To reinitialize the database, run this SQL file against your Azure SQL Server instance. The database name is "PosApp".
