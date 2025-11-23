# Migration Guide: Flask/Express to Vanilla Node.js

## Overview

This guide shows how the FreshMart POS system was migrated from Flask (Python) to vanilla Node.js without using Express.

## Side-by-Side Comparison

### 1. Server Setup

| Flask (Python) | Vanilla Node.js |
|----------------|-----------------|
| `app = Flask(__name__)` | `const server = http.createServer(...)` |
| `app.secret_key = '...'` | Custom session store with `crypto` |
| `app.run(host='0.0.0.0', port=5000)` | `server.listen(PORT, ...)` |

**Before (Flask):**
```python
from flask import Flask, session
app = Flask(__name__)
app.secret_key = 'secret'

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(port=5000)
```

**After (Node.js):**
```javascript
const http = require('http');
const sessions = {};

const server = http.createServer(async (req, res) => {
  const parsedUrl = url.parse(req.url, true);

  if (parsedUrl.pathname === '/' && req.method === 'GET') {
    await handleHome(req, res, session);
  }
});

server.listen(3000);
```

### 2. Session Management

| Flask | Vanilla Node.js |
|-------|-----------------|
| `session['user_id'] = user.id` | `createSession({ user_id: user.id })` |
| `session.get('role')` | `session.role` |
| `session.clear()` | `destroySession(sessionId)` |
| Automatic cookie handling | `parseCookies()`, `setSessionCookie()` |

**Before (Flask):**
```python
from flask import session

# Set session
session['user_id'] = admin[0]
session['role'] = 'admin'

# Get session
user_id = session.get('user_id')

# Clear session
session.clear()
```

**After (Node.js):**
```javascript
// In-memory store
const sessions = {};

// Create session
const sessionId = createSession({
  user_id: admin.AdminID,
  role: 'admin'
});
setSessionCookie(res, sessionId);

// Get session
const cookies = parseCookies(req);
const session = getSession(cookies.sessionId);

// Clear session
destroySession(sessionId);
clearSessionCookie(res);
```

### 3. Routing

| Flask | Vanilla Node.js |
|-------|-----------------|
| `@app.route('/path', methods=['GET'])` | `if (pathname === '/path' && method === 'GET')` |
| `@app.route('/path', methods=['POST'])` | `if (pathname === '/path' && method === 'POST')` |
| Automatic route matching | Manual if/else routing |

**Before (Flask):**
```python
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Handle POST
        data = request.get_json()
        return jsonify({"success": True})
    return render_template('login.html')
```

**After (Node.js):**
```javascript
// In main request handler
if (pathname === '/login' && method === 'GET') {
  return await handleLoginGET(req, res);
}

if (pathname === '/login' && method === 'POST') {
  return await handleLoginPOST(req, res);
}

// Handler functions
async function handleLoginGET(req, res) {
  await renderTemplate(res, 'login');
}

async function handleLoginPOST(req, res) {
  const data = await parseBody(req);
  sendJSON(res, { success: true });
}
```

### 4. Request Body Parsing

| Flask | Vanilla Node.js |
|-------|-----------------|
| `request.get_json()` | `await parseBody(req)` (JSON) |
| `request.form` | `await parseBody(req)` (URL-encoded) |
| Automatic parsing | Custom `parseBody()` function |

**Before (Flask):**
```python
from flask import request

@app.route('/api/bag', methods=['POST'])
def add_to_bag():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity')
```

**After (Node.js):**
```javascript
async function handleApiBagPOST(req, res, session) {
  const data = await parseBody(req);
  const product_id = parseInt(data.product_id || 0);
  const quantity = parseInt(data.quantity || 1);
}

// Custom parseBody implementation
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      const contentType = req.headers['content-type'] || '';
      if (contentType.includes('application/json')) {
        resolve(JSON.parse(body));
      } else {
        resolve(querystring.parse(body));
      }
    });
  });
}
```

### 5. Response Handling

| Flask | Vanilla Node.js |
|-------|-----------------|
| `return render_template('page.html', data=data)` | `await renderTemplate(res, 'page', data)` |
| `return jsonify({"key": "value"})` | `sendJSON(res, { key: 'value' })` |
| `return redirect(url_for('login'))` | `redirect(res, '/login')` |

**Before (Flask):**
```python
from flask import render_template, jsonify, redirect, url_for

# Render template
return render_template('index.html', products=products)

# JSON response
return jsonify({"success": True, "data": data})

# Redirect
return redirect(url_for('login'))
```

**After (Node.js):**
```javascript
// Render template
await renderTemplate(res, 'index', { products });

// JSON response
sendJSON(res, { success: true, data });

// Redirect
redirect(res, '/login');

// Helper implementations
async function renderTemplate(res, name, data) {
  const html = await ejs.renderFile(`views/${name}.ejs`, data);
  sendHTML(res, html);
}

function sendJSON(res, data, statusCode = 200) {
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(data));
}

function redirect(res, location) {
  res.statusCode = 302;
  res.setHeader('Location', location);
  res.end();
}
```

### 6. Static Files

| Flask | Vanilla Node.js |
|-------|-----------------|
| `app.static_folder = 'static'` | Custom `serveStatic()` function |
| Automatic MIME types | Manual `getMimeType()` mapping |
| `/static/css/style.css` | `/static/css/style.css` |

**Before (Flask):**
```python
# Automatic - Flask serves /static/ folder
# No code needed
```

**After (Node.js):**
```javascript
// In router
if (pathname.startsWith('/static/')) {
  const filePath = path.join(STATIC_DIR, pathname.replace('/static/', ''));
  return serveStatic(res, filePath);
}

function serveStatic(res, filePath) {
  fs.readFile(filePath, (error, data) => {
    if (error) return send404(res);
    res.setHeader('Content-Type', getMimeType(filePath));
    res.end(data);
  });
}

function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes = {
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.png': 'image/png',
    // ... more types
  };
  return mimeTypes[ext] || 'application/octet-stream';
}
```

### 7. Database Queries

| Flask (pyodbc) | Node.js (mssql) |
|----------------|-----------------|
| `cursor.execute(sql, params)` | `pool.request().input().query()` |
| `cursor.fetchall()` | `result.recordset` |
| `cursor.fetchone()` | `result.recordset[0]` |

**Before (Flask/Python):**
```python
from db import with_db

@app.route('/admin')
@with_db
def admin_dashboard(cursor, conn):
    cursor.execute("SELECT COUNT(*) FROM Product")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM Employee WHERE IsActive = ?", (1,))
    employees = rows_to_dict_list(cursor)

    return render_template('admin_dashboard.html',
                         total_products=total_products,
                         employees=employees)
```

**After (Node.js):**
```javascript
async function handleAdminDashboard(req, res, session) {
  const pool = await getConnection();

  // Simple query
  const result1 = await pool.request()
    .query('SELECT COUNT(*) as count FROM Product');
  const total_products = result1.recordset[0].count;

  // Parameterized query
  const result2 = await pool.request()
    .input('isActive', sql.Bit, 1)
    .query('SELECT * FROM Employee WHERE IsActive = @isActive');
  const employees = result2.recordset;

  await renderTemplate(res, 'admin_dashboard', {
    total_products,
    employees
  });
}
```

### 8. Authentication & Authorization

| Flask | Vanilla Node.js |
|-------|-----------------|
| `if 'user_id' not in session:` | `if (!session || !session.user_id)` |
| `session.get('role') == 'admin'` | `requireRole(session, 'admin')` |

**Before (Flask):**
```python
@app.route('/admin')
@with_db
def admin_dashboard(cursor, conn):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Admin logic here
    return render_template('admin_dashboard.html')
```

**After (Node.js):**
```javascript
async function handleAdminDashboard(req, res, session) {
  if (!requireRole(session, 'admin')) {
    return redirect(res, '/login');
  }

  // Admin logic here
  await renderTemplate(res, 'admin_dashboard');
}

function requireRole(session, requiredRole) {
  return session && session.role === requiredRole;
}
```

## Dependencies Comparison

### Flask Application
```
Flask
flask-cors
python-dotenv
pyodbc (or pymssql)
```

### Vanilla Node.js Application
```
mssql
dotenv
ejs
```

**No framework dependencies!** Only libraries for specific features.

## What Was Built From Scratch

The vanilla Node.js server implements these features without libraries:

1. **Session Management** ✅
   - In-memory session store
   - Session ID generation (`crypto.randomBytes`)
   - Session expiration
   - Cookie parsing and setting

2. **Routing System** ✅
   - URL parsing
   - Method matching (GET/POST)
   - Query parameter extraction
   - Route handlers

3. **Body Parsing** ✅
   - JSON body parsing
   - URL-encoded form parsing
   - Request size limits
   - Error handling

4. **Static File Serving** ✅
   - MIME type detection
   - File reading and streaming
   - Cache headers
   - 404 handling

5. **Cookie Management** ✅
   - Cookie parsing from headers
   - Cookie setting in responses
   - HttpOnly flag
   - Max-Age handling

6. **Response Helpers** ✅
   - JSON responses
   - HTML responses
   - Redirects
   - Error pages

## Code Size Comparison

| Metric | Flask (Python) | Vanilla Node.js |
|--------|----------------|-----------------|
| Main file size | ~2,800 lines | 1,146 lines |
| Dependencies | 4 packages + Flask | 3 packages |
| Custom code | Routes only | Routes + framework |
| Framework code | Hidden in Flask | Visible in server.js |

## Performance Considerations

### Flask
- ✅ Mature framework
- ✅ Built-in features
- ❌ Hidden overhead
- ❌ More dependencies

### Vanilla Node.js
- ✅ Full control
- ✅ Minimal dependencies
- ✅ Transparent behavior
- ❌ More code to maintain

## Migration Checklist

If you're migrating from Flask to this vanilla Node.js server:

- [ ] Install Node.js dependencies: `npm install`
- [ ] Convert `app.py` routes to handlers in `server.js`
- [ ] Replace `session['key']` with custom session management
- [ ] Replace `request.get_json()` with `parseBody(req)`
- [ ] Replace `render_template()` with `renderTemplate()`
- [ ] Replace `jsonify()` with `sendJSON()`
- [ ] Replace `redirect()` with custom `redirect()`
- [ ] Convert pyodbc queries to mssql queries
- [ ] Test all routes and functionality
- [ ] Update documentation

## Benefits of Vanilla Node.js

1. **Educational** - Understand how web servers work
2. **Lightweight** - Only 3 dependencies
3. **Transparent** - All code is visible and understandable
4. **Portable** - Works anywhere Node.js runs
5. **School-Friendly** - Meets "no Express" requirement

## When to Use Express

Use Express (or another framework) when:
- Building production applications
- Need middleware ecosystem
- Want rapid development
- Team is familiar with Express
- Not restricted by school requirements

## Conclusion

This vanilla Node.js server proves that you can build a full-featured web application without Express. While frameworks provide convenience, understanding the fundamentals makes you a better developer.

**School Project Approved:** ✅ Only uses allowed modules!
