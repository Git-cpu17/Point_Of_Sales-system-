# Server Architecture - Vanilla Node.js

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT (Browser)                         │
│  - HTML/CSS/JavaScript                                          │
│  - Fetch API for AJAX requests                                 │
│  - Cookies (sessionId)                                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP Request
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NODE.JS HTTP SERVER                           │
│                      (server.js)                                 │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │           REQUEST HANDLER (Main Router)                │    │
│  │  - Parse URL (url.parse)                               │    │
│  │  - Parse Cookies (parseCookies)                        │    │
│  │  - Get Session (getSession)                            │    │
│  │  - Route Matching (if/else)                            │    │
│  └────────┬───────────────────────────────┬─────────────┬─┘    │
│           │                               │             │       │
│           ▼                               ▼             ▼       │
│  ┌────────────────┐         ┌──────────────────┐   ┌────────┐ │
│  │ Static Files   │         │  Route Handlers  │   │ Auth   │ │
│  │ - serveStatic  │         │  - handleHome    │   │ Check  │ │
│  │ - getMimeType  │         │  - handleLogin   │   │        │ │
│  │ - Cache headers│         │  - handleBag     │   │        │ │
│  └────────────────┘         │  - handleAdmin   │   └────────┘ │
│                             │  - handleCustomer│              │
│                             │  - handleEmployee│              │
│                             └──────────┬───────┘              │
│                                        │                       │
│                                        ▼                       │
│  ┌───────────────────────────────────────────────────────┐    │
│  │              HELPER FUNCTIONS                         │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │    │
│  │  │  Session    │  │   Request    │  │  Response   │  │    │
│  │  │  - create   │  │  - parseBody │  │  - sendJSON │  │    │
│  │  │  - get      │  │  - cookies   │  │  - sendHTML │  │    │
│  │  │  - destroy  │  │  - query     │  │  - redirect │  │    │
│  │  └─────────────┘  └──────────────┘  └─────────────┘  │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌───────────────────────────────────────────────────────┐    │
│  │              IN-MEMORY SESSION STORE                  │    │
│  │  sessions = {                                         │    │
│  │    'abc123...': {                                     │    │
│  │      data: { user_id: 1, role: 'customer' },         │    │
│  │      expiresAt: 1234567890000                        │    │
│  │    }                                                  │    │
│  │  }                                                    │    │
│  └───────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATABASE LAYER (db.js)                       │
│  - Connection Pool (mssql)                                      │
│  - Max 10 connections                                           │
│  - Parameterized queries                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 AZURE SQL DATABASE                               │
│  Tables:                                                         │
│  - Product, Department                                          │
│  - Customer, Employee, Administrator                            │
│  - Bag, SalesTransaction, Transaction_Details                   │
│  - Inventory                                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Request Flow Diagram

### Example: Customer Login Flow

```
1. Browser → Server
   POST /login
   Content-Type: application/json
   Body: {"user_id": "john", "password": "pass123"}

2. Server: Parse Request
   ↓
   parseBody(req) → { user_id: "john", password: "pass123" }

3. Server: Database Query
   ↓
   pool.request()
     .input('username', sql.VarChar, 'john')
     .input('password', sql.VarChar, 'pass123')
     .query('SELECT CustomerID FROM Customer WHERE username = @username ...')

4. Server: Create Session
   ↓
   createSession({ user_id: 42, role: 'customer' })
   → sessionId = "abc123def456..."

5. Server: Set Cookie & Respond
   ↓
   Set-Cookie: sessionId=abc123def456...; HttpOnly; Path=/
   Response: {"success": true, "role": "customer", "redirectUrl": "/customer"}

6. Browser: Redirect
   ↓
   window.location.href = '/customer'

7. Browser → Server
   GET /customer
   Cookie: sessionId=abc123def456...

8. Server: Validate Session
   ↓
   cookies = parseCookies(req) → { sessionId: "abc123..." }
   session = getSession("abc123...") → { user_id: 42, role: 'customer' }
   requireRole(session, 'customer') → true ✓

9. Server: Query Dashboard Data
   ↓
   Multiple database queries for customer info, orders, stats

10. Server: Render Template
    ↓
    renderTemplate(res, 'customer_dashboard', { customer, orders, ... })
    ↓
    EJS renders HTML with data

11. Server → Browser
    200 OK
    Content-Type: text/html
    HTML page with customer dashboard
```

## Module Dependencies

```
server.js
├── Built-in Modules (No installation needed)
│   ├── http          → HTTP server
│   ├── url           → URL parsing
│   ├── querystring   → Form data parsing
│   ├── fs            → File system
│   ├── path          → Path utilities
│   └── crypto        → Random ID generation
│
├── External Packages (npm install)
│   ├── mssql         → SQL Server driver
│   ├── dotenv        → Environment variables
│   └── ejs           → Template engine
│
└── Custom Modules
    └── ./db.js       → Database connection pool
```

## Data Flow: Shopping Cart

```
┌─────────────┐
│   Browser   │
│  (Customer) │
└──────┬──────┘
       │ Click "Add to Cart" button
       │ onclick="addToCart(productId)"
       ▼
┌─────────────────────────────────┐
│  JavaScript (main.js)           │
│  fetch('/api/bag', {            │
│    method: 'POST',              │
│    body: JSON.stringify({       │
│      product_id: 123,           │
│      quantity: 2                │
│    })                           │
│  })                             │
└────────┬────────────────────────┘
         │ HTTP POST /api/bag
         ▼
┌─────────────────────────────────┐
│  Server Router                  │
│  if (pathname === '/api/bag'    │
│      && method === 'POST')      │
│    handleApiBagPOST()           │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  handleApiBagPOST()             │
│  1. Parse body                  │
│  2. Validate inputs             │
│  3. Check session/auth          │
│  4. Get bag owner               │
│  5. Check if item exists        │
│  6. INSERT or UPDATE Bag table  │
│  7. Return JSON response        │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Database (Bag table)           │
│  INSERT INTO Bag                │
│  (CustomerID, ProductID,        │
│   Quantity, AddedAt)            │
│  VALUES (42, 123, 2, GETDATE()) │
└────────┬────────────────────────┘
         │ Success
         ▼
┌─────────────────────────────────┐
│  Server Response                │
│  200 OK                         │
│  Content-Type: application/json│
│  {"success": true,              │
│   "message": "Added to cart"}   │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Browser JavaScript             │
│  .then(res => res.json())       │
│  .then(data => {                │
│    alert('Added to cart!');     │
│    updateBagCount();            │
│  })                             │
└─────────────────────────────────┘
```

## Session Lifecycle

```
1. User Login
   ┌────────────────────────────────┐
   │ POST /login                    │
   │ Credentials valid ✓            │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ createSession()                │
   │ - Generate random ID (32 bytes)│
   │ - Store user_id, role          │
   │ - Set expiration (24h)         │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ sessions['abc123...'] = {      │
   │   data: {                      │
   │     user_id: 42,               │
   │     role: 'customer'           │
   │   },                           │
   │   expiresAt: Date.now() + 24h │
   │ }                              │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ Set-Cookie:                    │
   │ sessionId=abc123...;           │
   │ HttpOnly; Path=/;              │
   │ Max-Age=86400                  │
   └────────────────────────────────┘

2. Subsequent Requests
   ┌────────────────────────────────┐
   │ GET /customer                  │
   │ Cookie: sessionId=abc123...    │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ parseCookies(req)              │
   │ → { sessionId: 'abc123...' }   │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ getSession('abc123...')        │
   │ - Check if exists              │
   │ - Check if expired             │
   │ - Return session data          │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ session = {                    │
   │   user_id: 42,                 │
   │   role: 'customer'             │
   │ }                              │
   └────────────────────────────────┘

3. Logout
   ┌────────────────────────────────┐
   │ GET /logout                    │
   │ Cookie: sessionId=abc123...    │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ destroySession('abc123...')    │
   │ delete sessions['abc123...']   │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ clearSessionCookie(res)        │
   │ Set-Cookie: sessionId=;        │
   │ Max-Age=0                      │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ redirect(res, '/login')        │
   └────────────────────────────────┘

4. Expiration (Automatic)
   ┌────────────────────────────────┐
   │ Request with old session ID    │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ getSession('old123...')        │
   │ if (expiresAt < Date.now())    │
   │   delete sessions['old123...'] │
   │   return null                  │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │ session = null                 │
   │ Redirect to /login             │
   └────────────────────────────────┘
```

## File Structure

```
Point_Of_Sales-system-/
│
├── server.js (1,146 lines)          ← Main server
│   ├── Imports & Config
│   ├── Session Store
│   ├── Helper Functions
│   ├── Route Handlers
│   └── Server Startup
│
├── db.js                             ← Database connection
│   ├── Connection config
│   ├── Connection pool
│   └── getConnection() export
│
├── package.json                      ← Dependencies (3 only)
│   ├── mssql
│   ├── dotenv
│   └── ejs
│
├── .env                              ← Environment config
│   ├── DB_USER
│   ├── DB_PASSWORD
│   ├── DB_SERVER
│   ├── DB_NAME
│   └── PORT
│
├── views/                            ← EJS Templates
│   ├── index.ejs
│   ├── login.ejs
│   ├── register.ejs
│   ├── bag.ejs
│   ├── admin_dashboard.ejs
│   ├── employee_dashboard.ejs
│   └── customer_dashboard.ejs
│
├── static/                           ← Static assets
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
└── Documentation/
    ├── SERVER_README.md
    ├── QUICKSTART.md
    ├── MIGRATION_GUIDE.md
    ├── TESTING_CHECKLIST.md
    ├── SUMMARY.md
    └── ARCHITECTURE.md (this file)
```

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                      │
│                                                         │
│  ┌────────────────────────────────────────────────┐   │
│  │  1. Input Validation                           │   │
│  │  - Type checking (parseInt)                    │   │
│  │  - Required field checks                       │   │
│  │  - Request size limits (1MB)                   │   │
│  └────────────────────────────────────────────────┘   │
│                         ▼                              │
│  ┌────────────────────────────────────────────────┐   │
│  │  2. Session Security                           │   │
│  │  - HttpOnly cookies (no JS access)             │   │
│  │  - Random session IDs (crypto.randomBytes)     │   │
│  │  - Session expiration (24h)                    │   │
│  └────────────────────────────────────────────────┘   │
│                         ▼                              │
│  ┌────────────────────────────────────────────────┐   │
│  │  3. Authentication                             │   │
│  │  - Password verification                       │   │
│  │  - Role-based access control                   │   │
│  │  - Session validation                          │   │
│  └────────────────────────────────────────────────┘   │
│                         ▼                              │
│  ┌────────────────────────────────────────────────┐   │
│  │  4. SQL Injection Protection                   │   │
│  │  - Parameterized queries only                  │   │
│  │  - No string concatenation in SQL              │   │
│  │  - Type-safe parameters                        │   │
│  └────────────────────────────────────────────────┘   │
│                         ▼                              │
│  ┌────────────────────────────────────────────────┐   │
│  │  5. Path Traversal Protection                  │   │
│  │  - Static file path validation                 │   │
│  │  - No "../" allowed                            │   │
│  │  - Whitelist static directory                  │   │
│  └────────────────────────────────────────────────┘   │
│                         ▼                              │
│  ┌────────────────────────────────────────────────┐   │
│  │  6. Error Handling                             │   │
│  │  - Try/catch blocks                            │   │
│  │  - No sensitive data in errors                 │   │
│  │  - Generic error messages to client            │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Technology Stack

```
┌──────────────────────────────────────────────┐
│           Frontend (Client-Side)             │
│  - HTML5                                     │
│  - CSS3 (custom styles)                      │
│  - Vanilla JavaScript (ES6+)                 │
│  - Fetch API (AJAX)                          │
└──────────────────┬───────────────────────────┘
                   │ HTTP
                   ▼
┌──────────────────────────────────────────────┐
│           Backend (Server-Side)              │
│  - Node.js (v16+)                            │
│  - Vanilla HTTP (no Express)                 │
│  - EJS (template engine)                     │
│  - Custom session management                 │
│  - Custom routing                            │
└──────────────────┬───────────────────────────┘
                   │ TCP/IP
                   ▼
┌──────────────────────────────────────────────┐
│              Database Layer                  │
│  - mssql driver                              │
│  - Connection pooling                        │
│  - Parameterized queries                     │
└──────────────────┬───────────────────────────┘
                   │ TDS Protocol
                   ▼
┌──────────────────────────────────────────────┐
│          Azure SQL Database                  │
│  - Relational database                       │
│  - Tables: 10+ tables                        │
│  - Stored procedures (optional)              │
└──────────────────────────────────────────────┘
```

This architecture demonstrates a complete web application built with minimal dependencies, following best practices while maintaining educational clarity.
