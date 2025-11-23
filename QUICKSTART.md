# Quick Start Guide - Vanilla Node.js Server

## Get Started in 3 Steps

### Step 1: Install Dependencies

```bash
npm install
```

This installs ONLY 3 packages:
- `mssql` - Database connectivity
- `dotenv` - Environment variables
- `ejs` - Template engine

### Step 2: Configure Database

Make sure your `.env` file has these values:

```env
DB_USER=your_username
DB_PASSWORD=your_password
DB_SERVER=your_server.database.windows.net
DB_NAME=your_database
DB_ENCRYPT=true
DB_TRUST_CERT=true
PORT=3000
```

### Step 3: Run the Server

```bash
npm start
```

Or:

```bash
node server.js
```

You should see:

```
============================================================
FreshMart POS System - Vanilla Node.js Server
============================================================
Server running at http://localhost:3000/
Environment: development
Database: your_server.database.windows.net
============================================================

Available routes:
  GET  /              - Home page
  GET  /login         - Login page
  POST /login         - Login submission
  GET  /register      - Registration page
  POST /register      - Registration submission
  GET  /logout        - Logout
  GET  /bag           - Shopping cart
  GET  /api/bag       - Get cart items (JSON)
  POST /api/bag       - Add to cart (JSON)
  GET  /admin         - Admin dashboard
  GET  /employee      - Employee dashboard
  GET  /customer      - Customer dashboard
  GET  /static/*      - Static files (CSS, JS, images)
============================================================
```

## Visit the Application

Open your browser to: **http://localhost:3000**

## Test the Routes

### 1. Home Page
```
http://localhost:3000/
```
Shows all products and categories

### 2. Login
```
http://localhost:3000/login
```
Login as admin, employee, or customer

### 3. Register
```
http://localhost:3000/register
```
Create a new customer account

### 4. Shopping Cart
```
http://localhost:3000/bag
```
View your cart (requires login)

### 5. Dashboards

- **Admin**: http://localhost:3000/admin
- **Employee**: http://localhost:3000/employee
- **Customer**: http://localhost:3000/customer

## API Testing with curl

### Login
```bash
curl -X POST http://localhost:3000/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"admin","password":"yourpass"}'
```

Response:
```json
{
  "success": true,
  "role": "admin",
  "redirectUrl": "/admin"
}
```

### Register New Customer
```bash
curl -X POST http://localhost:3000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "555-1234",
    "password": "password123"
  }'
```

### Add to Cart (with session)
```bash
curl -X POST http://localhost:3000/api/bag \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionId=YOUR_SESSION_ID" \
  -d '{"product_id": 1, "quantity": 2}'
```

### Get Cart Items
```bash
curl http://localhost:3000/api/bag \
  -H "Cookie: sessionId=YOUR_SESSION_ID"
```

## Key Features

✅ **No Express** - Pure Node.js `http` module
✅ **Session Management** - Built from scratch with `crypto`
✅ **Cookie Handling** - Custom parser and setter
✅ **Body Parsing** - Supports JSON and URL-encoded
✅ **Static Files** - Serves CSS, JS, images with proper MIME types
✅ **EJS Templates** - Server-side rendering
✅ **SQL Server** - Azure SQL Database via `mssql`
✅ **Security** - HttpOnly cookies, parameterized queries, path validation

## File Structure

```
/home/pavdog/projects/Point_Of_Sales-system-/
├── server.js              # Main server (1,146 lines)
├── db.js                  # Database connection
├── package.json           # Dependencies (only 3!)
├── .env                   # Environment variables
├── views/                 # EJS templates
│   ├── index.ejs
│   ├── login.ejs
│   ├── register.ejs
│   ├── bag.ejs
│   ├── admin_dashboard.ejs
│   ├── employee_dashboard.ejs
│   └── customer_dashboard.ejs
└── static/                # Static assets
    ├── css/style.css
    └── js/main.js
```

## Troubleshooting

### Port already in use
```bash
# Change port in .env
PORT=3001
```

### Database connection failed
- Check Azure SQL firewall allows your IP
- Verify credentials in `.env`
- Test connection with `db.js`

### Templates not rendering
- Check `views/` directory exists
- Ensure `.ejs` files are present
- Check file permissions

### Session not persisting
- Check cookies are enabled in browser
- Verify `sessionId` cookie is set
- Check session hasn't expired (24h)

## Development Tips

### Enable Debug Logging
```javascript
// In server.js, uncomment logging
console.log('Session:', session);
console.log('Cookies:', cookies);
```

### Watch for Changes
```bash
# Install nodemon globally
npm install -g nodemon

# Run with auto-restart
nodemon server.js
```

### Check Syntax
```bash
node --check server.js
```

## Production Deployment

1. Set `NODE_ENV=production` in `.env`
2. Use a process manager (PM2)
3. Set up HTTPS with a reverse proxy (nginx)
4. Enable database connection pooling
5. Add rate limiting for API routes

## Next Steps

- Add more routes (shopping lists, reports, etc.)
- Implement checkout functionality
- Add input validation
- Implement CSRF protection
- Add password hashing (bcrypt)
- Set up logging (Winston)

## Support

For issues or questions:
1. Check `SERVER_README.md` for detailed documentation
2. Review error logs in console
3. Verify database schema matches expectations

---

**Built with vanilla Node.js - No Express required!**
