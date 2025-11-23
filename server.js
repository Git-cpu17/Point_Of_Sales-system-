// server.js - Vanilla Node.js HTTP Server for FreshMart POS System
// School project - Only built-in Node.js modules + mssql, dotenv, and ejs

// ============================================================================
// IMPORTS - Only allowed modules
// ============================================================================
const http = require('http');
const url = require('url');
const querystring = require('querystring');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const ejs = require('ejs');
const { getConnection, sql } = require('./db');
require('dotenv').config();

// ============================================================================
// CONFIGURATION
// ============================================================================
const PORT = process.env.PORT || 3000;
const VIEWS_DIR = path.join(__dirname, 'views');
const STATIC_DIR = path.join(__dirname, 'static');

// ============================================================================
// IN-MEMORY SESSION STORE
// ============================================================================
const sessions = {};

// Session configuration
const SESSION_COOKIE_NAME = 'sessionId';
const SESSION_MAX_AGE = 24 * 60 * 60 * 1000; // 24 hours

// ============================================================================
// HELPER FUNCTIONS - Cookie & Session Management
// ============================================================================

/**
 * Parse cookies from request header
 * @param {http.IncomingMessage} req - HTTP request object
 * @returns {Object} - Parsed cookies as key-value pairs
 */
function parseCookies(req) {
  const cookies = {};
  const cookieHeader = req.headers.cookie;

  if (cookieHeader) {
    cookieHeader.split(';').forEach(cookie => {
      const [name, ...rest] = cookie.split('=');
      const value = rest.join('=').trim();
      if (name && value) {
        cookies[name.trim()] = decodeURIComponent(value);
      }
    });
  }

  return cookies;
}

/**
 * Get session data by session ID
 * @param {string} sessionId - Session identifier
 * @returns {Object|null} - Session data or null if expired/invalid
 */
function getSession(sessionId) {
  if (!sessionId || !sessions[sessionId]) {
    return null;
  }

  const session = sessions[sessionId];

  // Check if session has expired
  if (session.expiresAt < Date.now()) {
    delete sessions[sessionId];
    return null;
  }

  return session.data;
}

/**
 * Create a new session with data
 * @param {Object} data - Session data to store
 * @returns {string} - Generated session ID
 */
function createSession(data) {
  const sessionId = crypto.randomBytes(32).toString('hex');

  sessions[sessionId] = {
    data: data,
    expiresAt: Date.now() + SESSION_MAX_AGE
  };

  return sessionId;
}

/**
 * Update existing session data
 * @param {string} sessionId - Session identifier
 * @param {Object} data - Updated session data
 */
function updateSession(sessionId, data) {
  if (sessions[sessionId]) {
    sessions[sessionId].data = { ...sessions[sessionId].data, ...data };
    sessions[sessionId].expiresAt = Date.now() + SESSION_MAX_AGE;
  }
}

/**
 * Destroy a session
 * @param {string} sessionId - Session identifier
 */
function destroySession(sessionId) {
  if (sessionId && sessions[sessionId]) {
    delete sessions[sessionId];
  }
}

/**
 * Set a session cookie in the response
 * @param {http.ServerResponse} res - HTTP response object
 * @param {string} sessionId - Session identifier
 */
function setSessionCookie(res, sessionId) {
  const cookie = `${SESSION_COOKIE_NAME}=${sessionId}; HttpOnly; Path=/; Max-Age=${SESSION_MAX_AGE / 1000}`;
  res.setHeader('Set-Cookie', cookie);
}

/**
 * Clear session cookie
 * @param {http.ServerResponse} res - HTTP response object
 */
function clearSessionCookie(res) {
  res.setHeader('Set-Cookie', `${SESSION_COOKIE_NAME}=; HttpOnly; Path=/; Max-Age=0`);
}

// ============================================================================
// HELPER FUNCTIONS - Request Parsing
// ============================================================================

/**
 * Parse POST request body
 * @param {http.IncomingMessage} req - HTTP request object
 * @returns {Promise<Object>} - Parsed body data
 */
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';

    req.on('data', chunk => {
      body += chunk.toString();

      // Prevent large payloads
      if (body.length > 1e6) {
        req.connection.destroy();
        reject(new Error('Request body too large'));
      }
    });

    req.on('end', () => {
      try {
        const contentType = req.headers['content-type'] || '';

        if (contentType.includes('application/json')) {
          // Parse JSON
          resolve(body ? JSON.parse(body) : {});
        } else if (contentType.includes('application/x-www-form-urlencoded')) {
          // Parse URL-encoded form data
          resolve(querystring.parse(body));
        } else {
          // Default to JSON parsing
          resolve(body ? JSON.parse(body) : {});
        }
      } catch (error) {
        reject(error);
      }
    });

    req.on('error', reject);
  });
}

// ============================================================================
// HELPER FUNCTIONS - Response Utilities
// ============================================================================

/**
 * Send JSON response
 * @param {http.ServerResponse} res - HTTP response object
 * @param {Object} data - Data to send as JSON
 * @param {number} statusCode - HTTP status code
 */
function sendJSON(res, data, statusCode = 200) {
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(data));
}

/**
 * Send HTML response
 * @param {http.ServerResponse} res - HTTP response object
 * @param {string} html - HTML content
 * @param {number} statusCode - HTTP status code
 */
function sendHTML(res, html, statusCode = 200) {
  res.statusCode = statusCode;
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(html);
}

/**
 * Send redirect response
 * @param {http.ServerResponse} res - HTTP response object
 * @param {string} location - Redirect URL
 */
function redirect(res, location) {
  res.statusCode = 302;
  res.setHeader('Location', location);
  res.end();
}

/**
 * Send 404 Not Found response
 * @param {http.ServerResponse} res - HTTP response object
 */
function send404(res) {
  res.statusCode = 404;
  res.setHeader('Content-Type', 'text/html');
  res.end('<h1>404 - Not Found</h1><p>The page you requested does not exist.</p>');
}

/**
 * Send error response
 * @param {http.ServerResponse} res - HTTP response object
 * @param {Error} error - Error object
 */
function sendError(res, error) {
  console.error('Server error:', error);
  res.statusCode = 500;
  res.setHeader('Content-Type', 'text/html');
  res.end('<h1>500 - Internal Server Error</h1><p>Something went wrong on the server.</p>');
}

// ============================================================================
// HELPER FUNCTIONS - Template Rendering
// ============================================================================

/**
 * Render EJS template
 * @param {http.ServerResponse} res - HTTP response object
 * @param {string} templateName - Template file name (without .ejs)
 * @param {Object} data - Data to pass to template
 */
async function renderTemplate(res, templateName, data = {}) {
  try {
    const templatePath = path.join(VIEWS_DIR, `${templateName}.ejs`);
    const html = await ejs.renderFile(templatePath, data);
    sendHTML(res, html);
  } catch (error) {
    console.error('Template rendering error:', error);
    sendError(res, error);
  }
}

// ============================================================================
// HELPER FUNCTIONS - Static File Serving
// ============================================================================

/**
 * Get MIME type from file extension
 * @param {string} filePath - File path
 * @returns {string} - MIME type
 */
function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.eot': 'application/vnd.ms-fontobject'
  };

  return mimeTypes[ext] || 'application/octet-stream';
}

/**
 * Serve static files
 * @param {http.ServerResponse} res - HTTP response object
 * @param {string} filePath - File path
 */
function serveStatic(res, filePath) {
  fs.readFile(filePath, (error, data) => {
    if (error) {
      if (error.code === 'ENOENT') {
        send404(res);
      } else {
        sendError(res, error);
      }
      return;
    }

    res.statusCode = 200;
    res.setHeader('Content-Type', getMimeType(filePath));
    res.setHeader('Cache-Control', 'public, max-age=86400'); // 1 day cache
    res.end(data);
  });
}

// ============================================================================
// HELPER FUNCTIONS - Database & Business Logic
// ============================================================================

/**
 * Convert database rows to array of objects
 * @param {Array} rows - Database rows
 * @param {Array} columns - Column descriptions
 * @returns {Array<Object>} - Array of objects
 */
function rowsToDict(rows, columns) {
  return rows.map(row => {
    const obj = {};
    columns.forEach((col, index) => {
      obj[col.name] = row[index];
    });
    return obj;
  });
}

/**
 * Get bag owner (CustomerID or EmployeeID) from session
 * @param {Object} session - Session data
 * @returns {Object|null} - Owner object with CustomerID/EmployeeID
 */
function getBagOwner(session) {
  if (!session || !session.user_id) {
    return null;
  }

  const role = session.role;
  const uid = session.user_id;

  if (role === 'customer') {
    return { CustomerID: uid, EmployeeID: null };
  }

  if (role === 'employee') {
    return { CustomerID: null, EmployeeID: uid };
  }

  return null;
}

/**
 * Check if session has required role
 * @param {Object} session - Session data
 * @param {string} requiredRole - Required role (admin, employee, customer)
 * @returns {boolean} - True if authorized
 */
function requireRole(session, requiredRole) {
  return session && session.role === requiredRole;
}

/**
 * Get bag count for current user
 * @param {Object} session - Session data
 * @returns {Promise<number>} - Total items in bag
 */
async function getBagCount(session) {
  try {
    const owner = getBagOwner(session);
    if (!owner) return 0;

    const pool = await getConnection();
    let result;

    if (owner.CustomerID !== null) {
      result = await pool.request()
        .input('customerId', sql.Int, owner.CustomerID)
        .query('SELECT COALESCE(SUM(Quantity), 0) as total FROM dbo.Bag WHERE CustomerID = @customerId AND EmployeeID IS NULL');
    } else {
      result = await pool.request()
        .input('employeeId', sql.Int, owner.EmployeeID)
        .query('SELECT COALESCE(SUM(Quantity), 0) as total FROM dbo.Bag WHERE EmployeeID = @employeeId AND CustomerID IS NULL');
    }

    return result.recordset[0].total || 0;
  } catch (error) {
    console.error('Error getting bag count:', error);
    return 0;
  }
}

// ============================================================================
// ROUTE HANDLERS
// ============================================================================

/**
 * Home page - Display products and categories
 */
async function handleHome(req, res, session) {
  try {
    const pool = await getConnection();

    // Fetch active products
    const productsResult = await pool.request().query(`
      SELECT ProductID, Name, Description, Price, QuantityInStock, DepartmentID, ImageURL, OnSale
      FROM Product
      WHERE IsActive = 1
    `);
    const products = productsResult.recordset;

    // Fetch departments
    const departmentsResult = await pool.request().query('SELECT DepartmentID, Name FROM Department');
    const departments = departmentsResult.recordset;

    // Get user info based on role
    let user = null;
    if (session && session.user_id) {
      const role = session.role;
      const userId = session.user_id;

      if (role === 'customer') {
        const result = await pool.request()
          .input('id', sql.Int, userId)
          .query('SELECT Name FROM Customer WHERE CustomerID = @id');
        if (result.recordset.length > 0) {
          user = { Name: result.recordset[0].Name, role: 'customer' };
        }
      } else if (role === 'admin') {
        const result = await pool.request()
          .input('id', sql.Int, userId)
          .query('SELECT Name FROM Administrator WHERE AdminID = @id');
        if (result.recordset.length > 0) {
          user = { Name: result.recordset[0].Name, role: 'admin' };
        }
      } else if (role === 'employee') {
        const result = await pool.request()
          .input('id', sql.Int, userId)
          .query('SELECT Name FROM Employee WHERE EmployeeID = @id AND IsActive = 1');
        if (result.recordset.length > 0) {
          user = { Name: result.recordset[0].Name, role: 'employee' };
        }
      }
    }

    // Get bag count
    const bag_count = await getBagCount(session);

    await renderTemplate(res, 'index', {
      products,
      departments,
      user,
      session,
      bag_count
    });
  } catch (error) {
    console.error('Error in home route:', error);
    sendError(res, error);
  }
}

/**
 * GET /login - Display login form
 */
async function handleLoginGET(req, res) {
  await renderTemplate(res, 'login');
}

/**
 * POST /login - Handle login submission
 */
async function handleLoginPOST(req, res) {
  try {
    const data = await parseBody(req);
    const user_id = data.user_id || data.username || '';
    const password = data.password || '';

    if (!user_id || !password) {
      return sendJSON(res, { success: false, message: 'Missing credentials' }, 400);
    }

    const pool = await getConnection();

    // Check Administrator
    const adminResult = await pool.request()
      .input('username', sql.VarChar, user_id)
      .input('password', sql.VarChar, password)
      .query('SELECT AdminID, Username FROM Administrator WHERE Username = @username AND Password = @password');

    if (adminResult.recordset.length > 0) {
      const admin = adminResult.recordset[0];
      const sessionId = createSession({
        user_id: admin.AdminID,
        role: 'admin'
      });
      setSessionCookie(res, sessionId);
      return sendJSON(res, { success: true, role: 'admin', redirectUrl: '/admin' });
    }

    // Check Employee
    const empResult = await pool.request()
      .input('username', sql.VarChar, user_id)
      .input('password', sql.VarChar, password)
      .query('SELECT EmployeeID, Username FROM Employee WHERE Username = @username AND Password = @password');

    if (empResult.recordset.length > 0) {
      const emp = empResult.recordset[0];
      const sessionId = createSession({
        user_id: emp.EmployeeID,
        role: 'employee'
      });
      setSessionCookie(res, sessionId);
      return sendJSON(res, { success: true, role: 'employee', redirectUrl: '/employee' });
    }

    // Check Customer
    const custResult = await pool.request()
      .input('username', sql.VarChar, user_id)
      .input('password', sql.VarChar, password)
      .query('SELECT CustomerID, username FROM Customer WHERE username = @username AND password = @password');

    if (custResult.recordset.length > 0) {
      const cust = custResult.recordset[0];
      const sessionId = createSession({
        user_id: cust.CustomerID,
        role: 'customer'
      });
      setSessionCookie(res, sessionId);
      return sendJSON(res, { success: true, role: 'customer', redirectUrl: '/customer' });
    }

    // No match found
    return sendJSON(res, { success: false, message: 'Invalid ID or Password' }, 401);

  } catch (error) {
    console.error('Error in login POST:', error);
    sendJSON(res, { success: false, message: 'Server error' }, 500);
  }
}

/**
 * GET /register - Display registration form
 */
async function handleRegisterGET(req, res) {
  await renderTemplate(res, 'register');
}

/**
 * POST /register - Handle registration submission
 */
async function handleRegisterPOST(req, res) {
  try {
    const data = await parseBody(req);
    const { name, email, password, phone, username } = data;

    if (!name || !email || !password || !username) {
      return sendJSON(res, { success: false, message: 'Missing required fields' }, 400);
    }

    const pool = await getConnection();

    // Check if email exists
    const emailCheck = await pool.request()
      .input('email', sql.VarChar, email)
      .query('SELECT CustomerID FROM Customer WHERE Email = @email');

    if (emailCheck.recordset.length > 0) {
      return sendJSON(res, { success: false, message: 'Email already registered' }, 409);
    }

    // Check if username exists
    const usernameCheck = await pool.request()
      .input('username', sql.VarChar, username)
      .query('SELECT CustomerID FROM Customer WHERE username = @username');

    if (usernameCheck.recordset.length > 0) {
      return sendJSON(res, { success: false, message: 'Username already taken' }, 409);
    }

    // Insert new customer
    await pool.request()
      .input('username', sql.VarChar, username)
      .input('name', sql.VarChar, name)
      .input('phone', sql.VarChar, phone || null)
      .input('email', sql.VarChar, email)
      .input('password', sql.VarChar, password)
      .query(`
        INSERT INTO Customer (username, Name, Phone, Email, password)
        VALUES (@username, @name, @phone, @email, @password)
      `);

    return sendJSON(res, { success: true, message: 'Registration successful!' }, 201);

  } catch (error) {
    console.error('Error in register POST:', error);
    sendJSON(res, { success: false, message: 'Server error' }, 500);
  }
}

/**
 * GET /logout - Clear session and redirect to login
 */
function handleLogout(req, res, cookies) {
  const sessionId = cookies[SESSION_COOKIE_NAME];
  destroySession(sessionId);
  clearSessionCookie(res);
  redirect(res, '/login');
}

/**
 * GET /bag - Display shopping cart page
 */
async function handleBag(req, res, session) {
  try {
    let user = null;

    if (session && session.user_id) {
      const pool = await getConnection();
      const role = session.role;
      const userId = session.user_id;

      if (role === 'customer') {
        const result = await pool.request()
          .input('id', sql.Int, userId)
          .query('SELECT Name FROM Customer WHERE CustomerID = @id');
        if (result.recordset.length > 0) {
          user = { Name: result.recordset[0].Name, role: 'customer' };
        }
      } else if (role === 'admin') {
        const result = await pool.request()
          .input('id', sql.Int, userId)
          .query('SELECT Name FROM Administrator WHERE AdminID = @id');
        if (result.recordset.length > 0) {
          user = { Name: result.recordset[0].Name, role: 'admin' };
        }
      } else if (role === 'employee') {
        const result = await pool.request()
          .input('id', sql.Int, userId)
          .query('SELECT Name FROM Employee WHERE EmployeeID = @id AND IsActive = 1');
        if (result.recordset.length > 0) {
          user = { Name: result.recordset[0].Name, role: 'employee' };
        }
      }
    }

    const bag_count = await getBagCount(session);

    await renderTemplate(res, 'bag', { user, session, bag_count });
  } catch (error) {
    console.error('Error in bag route:', error);
    sendError(res, error);
  }
}

/**
 * GET /api/bag - Get bag items as JSON
 */
async function handleApiBagGET(req, res, session) {
  try {
    const owner = getBagOwner(session);

    if (!owner) {
      return sendJSON(res, { message: 'Login required' }, 401);
    }

    const pool = await getConnection();
    let result;

    if (owner.CustomerID !== null) {
      result = await pool.request()
        .input('customerId', sql.Int, owner.CustomerID)
        .query(`
          SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
          FROM dbo.Bag b
          JOIN dbo.Product p ON p.ProductID = b.ProductID
          WHERE b.CustomerID = @customerId AND b.EmployeeID IS NULL
          ORDER BY b.AddedAt DESC
        `);
    } else {
      result = await pool.request()
        .input('employeeId', sql.Int, owner.EmployeeID)
        .query(`
          SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
          FROM dbo.Bag b
          JOIN dbo.Product p ON p.ProductID = b.ProductID
          WHERE b.EmployeeID = @employeeId AND b.CustomerID IS NULL
          ORDER BY b.AddedAt DESC
        `);
    }

    sendJSON(res, result.recordset);
  } catch (error) {
    console.error('Error in GET /api/bag:', error);
    sendJSON(res, { message: 'Server error' }, 500);
  }
}

/**
 * POST /api/bag - Add item to bag
 */
async function handleApiBagPOST(req, res, session) {
  try {
    const data = await parseBody(req);
    const product_id = parseInt(data.product_id || 0);
    const quantity = parseInt(data.quantity || 1);

    if (product_id <= 0 || quantity <= 0) {
      return sendJSON(res, { message: 'Invalid product or quantity' }, 400);
    }

    const owner = getBagOwner(session);

    if (!owner) {
      return sendJSON(res, { message: 'Login required' }, 401);
    }

    const pool = await getConnection();

    // Check if item already in bag
    let checkResult;
    if (owner.CustomerID !== null) {
      checkResult = await pool.request()
        .input('customerId', sql.Int, owner.CustomerID)
        .input('productId', sql.Int, product_id)
        .query('SELECT BagID, Quantity FROM dbo.Bag WHERE CustomerID = @customerId AND ProductID = @productId AND EmployeeID IS NULL');
    } else {
      checkResult = await pool.request()
        .input('employeeId', sql.Int, owner.EmployeeID)
        .input('productId', sql.Int, product_id)
        .query('SELECT BagID, Quantity FROM dbo.Bag WHERE EmployeeID = @employeeId AND ProductID = @productId AND CustomerID IS NULL');
    }

    if (checkResult.recordset.length > 0) {
      // Update existing bag item
      const bagId = checkResult.recordset[0].BagID;
      const newQuantity = checkResult.recordset[0].Quantity + quantity;

      await pool.request()
        .input('bagId', sql.Int, bagId)
        .input('quantity', sql.Int, newQuantity)
        .query('UPDATE dbo.Bag SET Quantity = @quantity WHERE BagID = @bagId');

      return sendJSON(res, { success: true, message: 'Cart updated' });
    } else {
      // Insert new bag item
      if (owner.CustomerID !== null) {
        await pool.request()
          .input('customerId', sql.Int, owner.CustomerID)
          .input('productId', sql.Int, product_id)
          .input('quantity', sql.Int, quantity)
          .query('INSERT INTO dbo.Bag (CustomerID, ProductID, Quantity, AddedAt) VALUES (@customerId, @productId, @quantity, GETDATE())');
      } else {
        await pool.request()
          .input('employeeId', sql.Int, owner.EmployeeID)
          .input('productId', sql.Int, product_id)
          .input('quantity', sql.Int, quantity)
          .query('INSERT INTO dbo.Bag (EmployeeID, ProductID, Quantity, AddedAt) VALUES (@employeeId, @productId, @quantity, GETDATE())');
      }

      return sendJSON(res, { success: true, message: 'Added to cart' });
    }

  } catch (error) {
    console.error('Error in POST /api/bag:', error);
    sendJSON(res, { message: 'Server error' }, 500);
  }
}

/**
 * GET /admin - Admin dashboard
 */
async function handleAdminDashboard(req, res, session) {
  try {
    if (!requireRole(session, 'admin')) {
      return redirect(res, '/login');
    }

    const pool = await getConnection();

    // Get statistics
    const totalProductsResult = await pool.request()
      .query('SELECT COUNT(*) as count FROM Product');
    const total_products = totalProductsResult.recordset[0].count;

    const totalCustomersResult = await pool.request()
      .query('SELECT COUNT(*) as count FROM Customer');
    const total_customers = totalCustomersResult.recordset[0].count;

    const todaysRevenueResult = await pool.request()
      .query('SELECT SUM(TotalAmount) as total FROM SalesTransaction WHERE CAST(TransactionDate AS DATE) = CAST(GETDATE() AS DATE)');
    const todays_revenue = todaysRevenueResult.recordset[0].total || 0;

    const ordersTodayResult = await pool.request()
      .query('SELECT COUNT(*) as count FROM SalesTransaction WHERE CAST(TransactionDate AS DATE) = CAST(GETDATE() AS DATE)');
    const orders_today = ordersTodayResult.recordset[0].count || 0;

    // Get employee list
    const employeesResult = await pool.request()
      .query('SELECT EmployeeID, Name, Email, DepartmentID FROM Employee WHERE IsActive = 1');
    const employees = employeesResult.recordset;

    // Get admin name
    let admin_name = 'Admin';
    const adminResult = await pool.request()
      .input('adminId', sql.Int, session.user_id)
      .query('SELECT Name FROM Administrator WHERE AdminID = @adminId');

    if (adminResult.recordset.length > 0) {
      admin_name = adminResult.recordset[0].Name;
    }

    await renderTemplate(res, 'admin_dashboard', {
      total_products,
      total_customers,
      todays_revenue,
      orders_today,
      employees,
      admin_name,
      session
    });

  } catch (error) {
    console.error('Error in admin dashboard:', error);
    sendError(res, error);
  }
}

/**
 * GET /employee - Employee dashboard
 */
async function handleEmployeeDashboard(req, res, session) {
  try {
    if (!requireRole(session, 'employee')) {
      return redirect(res, '/login');
    }

    const pool = await getConnection();
    const user_id = session.user_id;

    // Get employee info
    const userResult = await pool.request()
      .input('employeeId', sql.Int, user_id)
      .query('SELECT * FROM Employee WHERE EmployeeID = @employeeId');

    if (userResult.recordset.length === 0) {
      return redirect(res, '/login');
    }

    const user = userResult.recordset[0];

    // Orders processed today
    const ordersTodayResult = await pool.request()
      .input('employeeId', sql.Int, user_id)
      .query(`
        SELECT COUNT(*) as count
        FROM Transaction_Details
        WHERE EmployeeID = @employeeId AND CAST(datetime AS DATE) = CAST(GETDATE() AS DATE)
      `);
    const orders_today = ordersTodayResult.recordset[0].count || 0;

    // Revenue generated today
    const revenueTodayResult = await pool.request()
      .input('employeeId', sql.Int, user_id)
      .query(`
        SELECT SUM(Subtotal) as total
        FROM Transaction_Details
        WHERE EmployeeID = @employeeId AND CAST(datetime AS DATE) = CAST(GETDATE() AS DATE)
      `);
    const revenue_today = revenueTodayResult.recordset[0].total || 0;

    // Low stock products in employee's department
    const lowStockResult = await pool.request()
      .input('employeeId', sql.Int, user_id)
      .query(`
        SELECT COUNT(*) as count
        FROM Inventory i
        JOIN Employee e ON e.DepartmentID = i.DepartmentID
        WHERE e.EmployeeID = @employeeId AND i.QuantityAvailable <= i.ReorderLevel
      `);
    const low_stock_products = lowStockResult.recordset[0].count || 0;

    // Current date
    const current_date = new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });

    await renderTemplate(res, 'employee_dashboard', {
      user,
      current_date,
      orders_today,
      revenue_today,
      low_stock_products,
      session
    });

  } catch (error) {
    console.error('Error in employee dashboard:', error);
    sendError(res, error);
  }
}

/**
 * GET /customer - Customer dashboard
 */
async function handleCustomerDashboard(req, res, session) {
  try {
    if (!requireRole(session, 'customer')) {
      return redirect(res, '/login');
    }

    const pool = await getConnection();
    const customer_id = session.user_id;

    // Get customer info
    const customerResult = await pool.request()
      .input('customerId', sql.Int, customer_id)
      .query('SELECT * FROM Customer WHERE CustomerID = @customerId');

    if (customerResult.recordset.length === 0) {
      return redirect(res, '/login');
    }

    const customer = customerResult.recordset[0];

    // Get customer orders
    const ordersResult = await pool.request()
      .input('customerId', sql.Int, customer_id)
      .query(`
        SELECT
          t.TransactionID,
          t.TransactionDate,
          t.TotalAmount,
          t.OrderStatus,
          SUM(td.Quantity) AS ItemCount
        FROM SalesTransaction t
        JOIN Transaction_Details td ON t.TransactionID = td.TransactionID
        WHERE t.CustomerID = @customerId
        GROUP BY t.TransactionID, t.TransactionDate, t.TotalAmount, t.OrderStatus
        ORDER BY t.TransactionDate DESC
      `);
    const orders = ordersResult.recordset;

    // Total saved (discounts)
    const totalSavedResult = await pool.request()
      .input('customerId', sql.Int, customer_id)
      .query('SELECT SUM(OrderDiscount) as total FROM SalesTransaction WHERE CustomerID = @customerId');
    const total_saved = totalSavedResult.recordset[0].total || 0;

    // Total orders
    const totalOrdersResult = await pool.request()
      .input('customerId', sql.Int, customer_id)
      .query('SELECT COUNT(*) as count FROM SalesTransaction WHERE CustomerID = @customerId');
    const total_orders = totalOrdersResult.recordset[0].count || 0;

    await renderTemplate(res, 'customer_dashboard', {
      customer,
      orders,
      total_saved,
      total_orders,
      session
    });

  } catch (error) {
    console.error('Error in customer dashboard:', error);
    sendError(res, error);
  }
}

// ============================================================================
// MAIN REQUEST HANDLER & ROUTER
// ============================================================================

const server = http.createServer(async (req, res) => {
  try {
    // Parse URL
    const parsedUrl = url.parse(req.url, true);
    const pathname = parsedUrl.pathname;
    const method = req.method;
    const query = parsedUrl.query;

    // Parse cookies and get session
    const cookies = parseCookies(req);
    const sessionId = cookies[SESSION_COOKIE_NAME];
    const session = sessionId ? getSession(sessionId) : null;

    // Log request
    console.log(`${method} ${pathname}`);

    // ========================================================================
    // STATIC FILE SERVING
    // ========================================================================
    if (pathname.startsWith('/static/')) {
      const filePath = path.join(STATIC_DIR, pathname.replace('/static/', ''));

      // Security: Prevent directory traversal
      if (!filePath.startsWith(STATIC_DIR)) {
        return send404(res);
      }

      return serveStatic(res, filePath);
    }

    // ========================================================================
    // ROUTE HANDLING
    // ========================================================================

    // Home page
    if (pathname === '/' && method === 'GET') {
      return await handleHome(req, res, session);
    }

    // Login
    if (pathname === '/login' && method === 'GET') {
      return await handleLoginGET(req, res);
    }

    if (pathname === '/login' && method === 'POST') {
      return await handleLoginPOST(req, res);
    }

    // Register
    if (pathname === '/register' && method === 'GET') {
      return await handleRegisterGET(req, res);
    }

    if (pathname === '/register' && method === 'POST') {
      return await handleRegisterPOST(req, res);
    }

    // Logout
    if (pathname === '/logout' && method === 'GET') {
      return handleLogout(req, res, cookies);
    }

    // Shopping bag/cart
    if (pathname === '/bag' && method === 'GET') {
      return await handleBag(req, res, session);
    }

    // API: Get bag items
    if (pathname === '/api/bag' && method === 'GET') {
      return await handleApiBagGET(req, res, session);
    }

    // API: Add to bag
    if (pathname === '/api/bag' && method === 'POST') {
      return await handleApiBagPOST(req, res, session);
    }

    // Admin dashboard
    if (pathname === '/admin' && method === 'GET') {
      return await handleAdminDashboard(req, res, session);
    }

    // Employee dashboard
    if (pathname === '/employee' && method === 'GET') {
      return await handleEmployeeDashboard(req, res, session);
    }

    // Customer dashboard
    if (pathname === '/customer' && method === 'GET') {
      return await handleCustomerDashboard(req, res, session);
    }

    // 404 - Not Found
    send404(res);

  } catch (error) {
    console.error('Unhandled error:', error);
    sendError(res, error);
  }
});

// ============================================================================
// START SERVER
// ============================================================================

server.listen(PORT, () => {
  console.log('='.repeat(60));
  console.log('FreshMart POS System - Vanilla Node.js Server');
  console.log('='.repeat(60));
  console.log(`Server running at http://localhost:${PORT}/`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`Database: ${process.env.DB_SERVER || 'Not configured'}`);
  console.log('='.repeat(60));
  console.log('\nAvailable routes:');
  console.log('  GET  /              - Home page');
  console.log('  GET  /login         - Login page');
  console.log('  POST /login         - Login submission');
  console.log('  GET  /register      - Registration page');
  console.log('  POST /register      - Registration submission');
  console.log('  GET  /logout        - Logout');
  console.log('  GET  /bag           - Shopping cart');
  console.log('  GET  /api/bag       - Get cart items (JSON)');
  console.log('  POST /api/bag       - Add to cart (JSON)');
  console.log('  GET  /admin         - Admin dashboard');
  console.log('  GET  /employee      - Employee dashboard');
  console.log('  GET  /customer      - Customer dashboard');
  console.log('  GET  /static/*      - Static files (CSS, JS, images)');
  console.log('='.repeat(60));
});

// ============================================================================
// GRACEFUL SHUTDOWN
// ============================================================================

process.on('SIGTERM', () => {
  console.log('SIGTERM received. Shutting down gracefully...');
  server.close(() => {
    console.log('Server closed.');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('\nSIGINT received. Shutting down gracefully...');
  server.close(() => {
    console.log('Server closed.');
    process.exit(0);
  });
});

// ============================================================================
// ERROR HANDLERS
// ============================================================================

process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});
