# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FreshMart is a Point of Sale (POS) system for an online grocery store built with **Node.js/Express**. The application connects to **Azure SQL Database** (MS SQL Server).

**Note:** Legacy Python/Flask files (app.py, db.py, requirements.txt) exist in the repository but are no longer used.

## Running the Application

### Setup
```bash
# 1. Install dependencies
npm install

# 2. Create .env file from .env.example
cp .env.example .env

# 3. Edit .env with your database credentials:
# DB_USER, DB_PASSWORD, DB_SERVER, DB_NAME, SESSION_SECRET

# 4. Run the application
npm start

# Or run in development mode with auto-reload
npm run dev
```

### Environment Variables Required
- `DB_USER` - Azure SQL database username
- `DB_PASSWORD` - Azure SQL database password
- `DB_SERVER` - Azure SQL server (e.g., yourserver.database.windows.net)
- `DB_NAME` - Database name
- `DB_ENCRYPT` - Set to 'true' for Azure SQL
- `DB_TRUST_CERT` - Set to 'no' for production, 'yes' for local dev
- `SESSION_SECRET` - Random secret key for session encryption
- `PORT` - Server port (default: 3000)

## Database Architecture

### Connection Handling
- Uses `mssql` package with connection pooling via `getConnection()` in `db.js`
- Global connection pool is reused across requests for efficiency
- `withDB` middleware attaches database connection to `req.db` for each request

### Core Database Tables
- **Product** - Inventory items (ProductID, Name, Price, QuantityInStock, DepartmentID, IsActive, OnSale, ImageURL)
- **Department** - Product categories/departments
- **Customer** - Customer accounts with shopping capabilities
- **Employee** - Staff accounts with inventory management access
- **Administrator** - Admin accounts with full system access
- **Bag** - Shopping cart (CustomerID or EmployeeID, ProductID, Quantity)
- **ShoppingList** - Customer wish lists (ListID, CustomerID, Name, IsDefault)
- **ShoppingListItem** - Items in shopping lists
- **Orders** - Completed purchases

### Key Database Patterns
- Soft deletes using `IsActive` flag on Product and Employee tables
- Session-based bag ownership: either CustomerID or EmployeeID (one must be NULL)
- Shopping lists have a default list per customer that cannot be deleted

## Application Architecture

### Multi-Role System
Three distinct user roles with separate dashboards and permissions:

1. **Customer** (`role='customer'`)
   - Browse products, filter by department
   - Shopping bag/cart functionality
   - Create and manage shopping lists
   - View order history

2. **Employee** (`role='employee'`)
   - Manage products (add, edit, soft delete)
   - View low stock alerts
   - Update inventory
   - Access shopping bag for in-store checkouts

3. **Administrator** (`role='admin'`)
   - Full product and employee management
   - Apply seasonal sales (20% discount)
   - View reports (sales, inventory, customers, revenue)
   - Manage employee accounts

### Session Management
- Session stores `user_id` and `role`
- Bag ownership determined by `get_bag_owner_from_session()` helper
- Access control via role checking in route handlers

### Template System
- **Flask**: Jinja2 templates in `/templates/`
- **Node.js**: Should use EJS templates in `/views/` (converted from Jinja2)
- Shared partials for notifications and report tables

### API Endpoints Structure

Both implementations follow RESTful patterns:

**Authentication**
- `GET /login` - Login page
- `POST /login` - Authenticate (checks Admin → Employee → Customer)
- `GET /register` - Registration page
- `POST /register` - Create customer account

**Products**
- `GET /admin/products` - Product management page with search/filter
- `GET /admin/edit-product/:id` - Edit product form
- `POST /admin/edit-product/:id` - Update product
- `DELETE /api/products/:id` - Soft delete product
- `GET /api/low_stock` - Products with quantity < 10
- `POST /api/update_stock` - Update product stock level

**Shopping Bag/Cart**
- `GET /bag` - Bag page
- `GET /api/bag` - Get user's bag items
- `POST /api/bag` - Add/merge item to bag
- `PATCH /api/bag/:id` - Update item quantity
- `DELETE /api/bag/:id` - Remove item
- `DELETE /api/bag` - Clear entire bag

**Shopping Lists** (Customer only)
- `GET /shopping-lists` - Lists page
- `GET /api/lists` - Get customer's lists
- `POST /api/lists` - Create new list
- `DELETE /api/lists/:id` - Delete list (except default)
- `GET /api/lists/:id/items` - Get list items
- `POST /api/lists/:id/items` - Add item to list

### Code Organization

**Single-file Architecture** (`app.js`)
- All routes, middleware, and helpers in one monolithic file
- Database connection via `withDB(req, res, next)` middleware
- Helper functions:
  - `getBagOwner(req)` - Determines bag ownership from session
  - `requireAdmin(req, res, next)` - Admin role guard
  - `requireCustomer(req, res, next)` - Customer role guard
  - `ensureDefaultList(pool, customer_id)` - Shopping list helper
- Template engine: **EJS** (views in `/views/` directory)
- Static files: Served from `/static/` directory

## Important Implementation Details

### Bag/Cart System
- Customers and Employees have separate bags
- Uses MERGE statements for upsert operations (add to existing or insert new)
- Ownership filter: `WHERE CustomerID = ? AND EmployeeID IS NULL` (or vice versa)

### Product Management
- Products are soft-deleted (IsActive = 0) not removed from database
- Low stock threshold is hardcoded at quantity < 10
- Image URLs can be generated from Unsplash API (see utils/image.js in Node version)

### Authentication
- **NO PASSWORD HASHING** - Passwords stored in plaintext (security concern for production)
- Login checks roles in order: Administrator → Employee → Customer
- Each role has distinct table: Administrator, Employee, Customer

### Sales/Discounts
- OnSale flag on Product table
- SalePrice field for discounted price
- Admin can apply 20% sale to all products via `/apply_sales` endpoint

## Testing and Development

When modifying the database:
- Test changes against Azure SQL Database
- Connection timeout is 30 seconds
- Use parameterized queries to prevent SQL injection

When adding new features:
- Follow existing role-based access control patterns
- Use `withDB` middleware for database access
- Add new routes in `app.js` following existing patterns
- Create corresponding EJS templates in `/views/`

## Known Issues / Technical Debt

- **CRITICAL**: Passwords stored in plaintext (should use bcrypt/hashing)
- Monolithic app.js file - could be split into route modules for better organization
- No input validation library (consider using express-validator)
- No rate limiting on authentication endpoints
- Node.js v18 is used, but some Azure packages prefer v20+
