# FreshMart POS System - Vanilla Node.js Server

## Overview

This is a complete vanilla Node.js HTTP server implementation for the FreshMart Point of Sale system, designed for a school project that only allows built-in Node.js modules plus `mssql`, `dotenv`, and `ejs`.

**File:** `server.js` (1,146 lines)

## Allowed Dependencies

This server ONLY uses:
- **Built-in Node.js modules:** `http`, `url`, `querystring`, `fs`, `path`, `crypto`
- **External packages (allowed):** `mssql`, `dotenv`, `ejs`
- **Database module:** `./db.js`

## Features Implemented

### 1. Core HTTP Server
- Built with Node.js `http` module (no Express)
- Request routing with if/else logic
- Query parameter parsing
- POST body parsing (JSON and URL-encoded)
- Static file serving with proper MIME types
- Error handling and 404 pages

### 2. Session Management (Built from Scratch)
- In-memory session store using JavaScript objects
- Cryptographically secure session IDs (`crypto.randomBytes`)
- HttpOnly session cookies
- Session expiration (24-hour timeout)
- Stores `user_id` and `role` in session

### 3. Authentication System
- Login for 3 user types: Admin, Employee, Customer
- Registration for new customers
- Password validation against database
- Session-based authentication
- Logout with session cleanup

### 4. Route Handlers

#### Public Routes
- `GET /` - Home page with products and categories
- `GET /login` - Login form
- `POST /login` - Handle login (returns JSON)
- `GET /register` - Registration form
- `POST /register` - Handle registration (returns JSON)
- `GET /logout` - Clear session and redirect

#### Protected Routes
- `GET /bag` - Shopping cart page
- `GET /api/bag` - Get cart items (JSON API)
- `POST /api/bag` - Add item to cart (JSON API)
- `GET /admin` - Admin dashboard (admin only)
- `GET /employee` - Employee dashboard (employee only)
- `GET /customer` - Customer dashboard (customer only)

#### Static Files
- `GET /static/*` - CSS, JavaScript, images, fonts

### 5. Database Integration
- Uses SQL Server via `mssql` package
- Connection pooling via `./db.js`
- Parameterized queries (SQL injection protection)
- Async/await pattern
- Error handling for all database operations

### 6. Template Rendering
- EJS templates for server-side rendering
- Dynamic data injection
- Reusable partials support

## Architecture

### Helper Functions

#### Cookie & Session Management
```javascript
parseCookies(req)           // Parse cookie header
getSession(sessionId)       // Retrieve session data
createSession(data)         // Create new session
updateSession(id, data)     // Update session
destroySession(sessionId)   // Delete session
setSessionCookie(res, id)   // Set cookie in response
clearSessionCookie(res)     // Clear cookie
```

#### Request Parsing
```javascript
parseBody(req)              // Parse POST body (JSON/URL-encoded)
```

#### Response Utilities
```javascript
sendJSON(res, data, code)   // Send JSON response
sendHTML(res, html, code)   // Send HTML response
redirect(res, location)     // Send redirect
send404(res)                // Send 404 page
sendError(res, error)       // Send error page
```

#### Template & Static Files
```javascript
renderTemplate(res, name, data)  // Render EJS template
serveStatic(res, filePath)       // Serve static file
getMimeType(filePath)            // Get MIME type
```

#### Business Logic
```javascript
getBagOwner(session)        // Get CustomerID or EmployeeID
requireRole(session, role)  // Check authorization
getBagCount(session)        // Get cart item count
rowsToDict(rows, columns)   // Convert DB rows to objects
```

## Usage

### Starting the Server

```bash
# Install dependencies (only 3 external packages)
npm install

# Create .env file with database credentials
cp .env.example .env
# Edit .env with your Azure SQL credentials

# Start the server
npm start
# Or: node server.js
```

### Environment Variables (.env)

```env
# Database Configuration
DB_USER=your_database_username
DB_PASSWORD=your_database_password
DB_SERVER=your_server.database.windows.net
DB_NAME=your_database_name
DB_ENCRYPT=true
DB_TRUST_CERT=true

# Server Configuration
PORT=3000
```

### Testing Routes

```bash
# Home page
curl http://localhost:3000/

# Login (POST JSON)
curl -X POST http://localhost:3000/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"admin","password":"password"}'

# Get cart items (with session cookie)
curl http://localhost:3000/api/bag \
  -H "Cookie: sessionId=YOUR_SESSION_ID"

# Add to cart (with session cookie)
curl -X POST http://localhost:3000/api/bag \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionId=YOUR_SESSION_ID" \
  -d '{"product_id":1,"quantity":2}'
```

## Security Features

1. **Session Security**
   - HttpOnly cookies (prevents XSS)
   - Cryptographically random session IDs (32 bytes hex)
   - Session expiration (24 hours)
   - Session validation on each request

2. **SQL Injection Protection**
   - All queries use parameterized statements
   - Input validation for product IDs and quantities

3. **Path Traversal Protection**
   - Static file serving validates paths
   - Prevents access outside `/static/` directory

4. **Request Size Limits**
   - POST body limited to 1MB
   - Prevents denial-of-service attacks

## Code Structure

```
server.js (1,146 lines)
├── Imports (20 lines)
├── Configuration (10 lines)
├── Session Store (10 lines)
├── Helper Functions (400 lines)
│   ├── Cookie & Session (120 lines)
│   ├── Request Parsing (40 lines)
│   ├── Response Utilities (80 lines)
│   ├── Template Rendering (20 lines)
│   ├── Static Files (60 lines)
│   └── Business Logic (80 lines)
├── Route Handlers (600 lines)
│   ├── handleHome (60 lines)
│   ├── handleLoginGET/POST (80 lines)
│   ├── handleRegisterGET/POST (80 lines)
│   ├── handleLogout (10 lines)
│   ├── handleBag (50 lines)
│   ├── handleApiBagGET/POST (120 lines)
│   ├── handleAdminDashboard (80 lines)
│   ├── handleEmployeeDashboard (80 lines)
│   └── handleCustomerDashboard (80 lines)
├── Main Request Handler (100 lines)
└── Server Startup & Shutdown (50 lines)
```

## Comparison: Express vs Vanilla Node.js

| Feature | Express | This Server |
|---------|---------|-------------|
| Framework | Express.js | Vanilla Node.js |
| Dependencies | 50+ packages | 3 packages |
| Session | express-session | Custom implementation |
| Routing | app.get/post | if/else statements |
| Body parsing | express.json() | Custom parseBody() |
| Static files | express.static() | Custom serveStatic() |
| Cookies | cookie-parser | Custom parseCookies() |

## Database Schema Requirements

The server expects these tables:
- `Product` - Products with prices and stock
- `Department` - Product categories
- `Customer` - Customer accounts
- `Employee` - Employee accounts
- `Administrator` - Admin accounts
- `Bag` - Shopping cart items
- `SalesTransaction` - Completed orders
- `Transaction_Details` - Order line items
- `Inventory` - Inventory tracking

## Error Handling

1. **Database Errors**
   - Logged to console
   - Returns 500 error page
   - Graceful degradation

2. **Invalid Sessions**
   - Redirects to login page
   - Returns 401 for API routes

3. **File Not Found**
   - Returns 404 page for routes
   - Returns 404 for static files

4. **Malformed Requests**
   - Returns 400 Bad Request
   - Validates required fields

## Performance Considerations

1. **Database Connection Pooling**
   - Reuses connections via `global.connectionPool`
   - Max 10 connections, min 0
   - 30-second idle timeout

2. **Static File Caching**
   - Sets `Cache-Control: public, max-age=86400`
   - 1-day browser cache for static assets

3. **Session Cleanup**
   - Sessions expire after 24 hours
   - Automatic cleanup on access

## Extending the Server

### Adding a New Route

```javascript
// In main request handler
if (pathname === '/your-route' && method === 'GET') {
  return await handleYourRoute(req, res, session);
}

// Create handler function
async function handleYourRoute(req, res, session) {
  try {
    // Your logic here
    await renderTemplate(res, 'your_template', { data });
  } catch (error) {
    console.error('Error:', error);
    sendError(res, error);
  }
}
```

### Adding a New API Endpoint

```javascript
if (pathname === '/api/your-endpoint' && method === 'POST') {
  const data = await parseBody(req);
  // Process data
  sendJSON(res, { success: true, data: result });
}
```

## Testing Checklist

- [ ] Server starts without errors
- [ ] Home page loads with products
- [ ] Login works for admin/employee/customer
- [ ] Registration creates new customer
- [ ] Sessions persist across requests
- [ ] Logout clears session
- [ ] Shopping cart add/view works
- [ ] Admin dashboard shows stats
- [ ] Employee dashboard shows stats
- [ ] Customer dashboard shows orders
- [ ] Static files (CSS/JS) load
- [ ] 404 page shows for invalid routes

## Troubleshooting

### Server won't start
- Check `.env` file exists and has correct values
- Verify database connection with `db.js`
- Check port 3000 is not in use

### Login fails
- Verify database has users with matching credentials
- Check browser console for errors
- Verify session cookies are being set

### Static files 404
- Ensure `/static/` directory exists
- Check file paths in templates
- Verify MIME types are correct

### Database errors
- Check Azure SQL firewall rules
- Verify connection string in `.env`
- Check database tables exist

## License

This is a school project. Use for educational purposes only.

## Credits

Built with vanilla Node.js for FreshMart POS System.
No Express, no middleware libraries - just core Node.js!
