# Testing Checklist for Vanilla Node.js Server

## Pre-Flight Checks

- [ ] Node.js version >= 16.0.0 installed (`node --version`)
- [ ] Dependencies installed (`npm install`)
- [ ] `.env` file configured with database credentials
- [ ] Database connection working (`node -e "require('./db').getConnection().then(() => console.log('OK'))"`)
- [ ] Syntax check passed (`node --check server.js`)

## Server Startup

- [ ] Server starts without errors
- [ ] Console shows startup banner
- [ ] Console lists all available routes
- [ ] Port 3000 is accessible (or custom PORT from .env)

## Basic Functionality

### Home Page (GET /)
- [ ] Page loads without errors
- [ ] Products display correctly
- [ ] Categories/departments display
- [ ] Navigation bar renders
- [ ] Static CSS loads (page is styled)
- [ ] Static JavaScript loads (no console errors)
- [ ] Product emojis or images display

### Static Files (GET /static/*)
- [ ] CSS file loads: `/static/css/style.css`
- [ ] JavaScript file loads: `/static/js/main.js`
- [ ] Correct MIME types (check Network tab)
- [ ] 404 for non-existent static files

## Authentication Flow

### Login Page (GET /login)
- [ ] Login form displays
- [ ] Username/email input field renders
- [ ] Password input field renders
- [ ] Submit button works
- [ ] "Back to Home" link works
- [ ] "Register" link works

### Login Submission (POST /login)
- [ ] Valid admin credentials work
- [ ] Valid employee credentials work
- [ ] Valid customer credentials work
- [ ] Returns JSON response: `{"success": true, "role": "...", "redirectUrl": "..."}`
- [ ] Session cookie is set (`sessionId` in cookies)
- [ ] Invalid credentials return error
- [ ] Missing credentials return 400 error
- [ ] Redirects to appropriate dashboard

### Registration Page (GET /register)
- [ ] Registration form displays
- [ ] All input fields render (username, name, email, phone, password)
- [ ] Submit button works
- [ ] "Sign in here" link works

### Registration Submission (POST /register)
- [ ] Valid registration creates customer
- [ ] Returns JSON: `{"success": true, "message": "..."}`
- [ ] Duplicate email returns 409 error
- [ ] Duplicate username returns 409 error
- [ ] Missing required fields return 400 error
- [ ] Customer appears in database

### Logout (GET /logout)
- [ ] Session cookie is cleared
- [ ] Redirects to `/login`
- [ ] Cannot access protected routes after logout
- [ ] Session data removed from memory

## Session Management

- [ ] Session persists across requests
- [ ] Session cookie is HttpOnly
- [ ] Session expires after 24 hours
- [ ] Invalid session ID returns null
- [ ] Multiple users have separate sessions
- [ ] Session data includes `user_id` and `role`

## Shopping Cart

### Cart Page (GET /bag)
- [ ] Requires login (redirects if not logged in)
- [ ] Page renders for logged-in users
- [ ] Shows user name in navigation
- [ ] Cart container displays
- [ ] Displays appropriate dashboard link based on role

### Get Cart Items (GET /api/bag)
- [ ] Returns 401 if not logged in
- [ ] Returns empty array for new users
- [ ] Returns cart items as JSON array
- [ ] Each item has: BagID, ProductID, Name, Price, Quantity, AddedAt
- [ ] Customer sees only their items
- [ ] Employee sees only their items

### Add to Cart (POST /api/bag)
- [ ] Returns 401 if not logged in
- [ ] Returns 400 for invalid product_id
- [ ] Returns 400 for invalid quantity
- [ ] Adds new item to cart
- [ ] Updates existing item quantity
- [ ] Returns JSON: `{"success": true, "message": "..."}`
- [ ] Database Bag table updated correctly

## Dashboard Access

### Admin Dashboard (GET /admin)
- [ ] Requires admin role (redirects others)
- [ ] Displays admin name
- [ ] Shows total products count
- [ ] Shows total customers count
- [ ] Shows today's revenue
- [ ] Shows orders today count
- [ ] Lists active employees
- [ ] All statistics are accurate

### Employee Dashboard (GET /employee)
- [ ] Requires employee role (redirects others)
- [ ] Displays employee info
- [ ] Shows current date
- [ ] Shows orders processed today
- [ ] Shows revenue generated today
- [ ] Shows low stock products count
- [ ] All statistics are accurate

### Customer Dashboard (GET /customer)
- [ ] Requires customer role (redirects others)
- [ ] Displays customer info
- [ ] Shows order history
- [ ] Shows total saved (discounts)
- [ ] Shows total orders count
- [ ] Orders display correctly with details
- [ ] All statistics are accurate

## Security Tests

### Session Security
- [ ] Session IDs are random (32 bytes hex)
- [ ] Session cookies are HttpOnly (check in browser)
- [ ] Cannot access another user's session
- [ ] Expired sessions are rejected

### SQL Injection Protection
- [ ] Login with `' OR '1'='1` fails
- [ ] Registration with SQL in fields fails
- [ ] All queries use parameterized statements

### Path Traversal Protection
- [ ] `/static/../server.js` returns 404
- [ ] `/static/../../etc/passwd` returns 404
- [ ] Static files only served from `/static/` directory

### Input Validation
- [ ] Product ID must be integer > 0
- [ ] Quantity must be integer > 0
- [ ] Email format validated on registration
- [ ] Required fields enforced

### Request Size Limits
- [ ] Large POST body (> 1MB) is rejected
- [ ] Connection destroyed on oversized request

## Error Handling

### 404 Not Found
- [ ] Invalid route returns 404 page
- [ ] 404 page has proper HTML
- [ ] Missing static file returns 404

### 500 Server Error
- [ ] Database errors show 500 page
- [ ] Template errors show 500 page
- [ ] Errors logged to console
- [ ] User sees friendly error message

### 400 Bad Request
- [ ] Missing login credentials return 400
- [ ] Missing registration fields return 400
- [ ] Invalid JSON returns 400

### 401 Unauthorized
- [ ] Invalid login credentials return 401
- [ ] API routes without session return 401

### 409 Conflict
- [ ] Duplicate email on registration returns 409
- [ ] Duplicate username on registration returns 409

## Database Integration

### Connection Pooling
- [ ] Database connection established on startup
- [ ] Connection pool reused across requests
- [ ] Max 10 connections enforced
- [ ] Idle connections timeout after 30s

### Query Execution
- [ ] All queries use async/await
- [ ] Parameterized queries work correctly
- [ ] Results returned as recordsets
- [ ] NULL values handled properly

### Transaction Safety
- [ ] Inserts commit successfully
- [ ] Updates commit successfully
- [ ] Errors don't corrupt database

## Template Rendering

### EJS Templates
- [ ] Templates render without errors
- [ ] Variables passed to templates correctly
- [ ] Conditionals work (if/else)
- [ ] Loops work (for/forEach)
- [ ] Partials included correctly (if used)
- [ ] HTML escaped properly (no XSS)

### Data Binding
- [ ] Product data displays correctly
- [ ] User data displays correctly
- [ ] Order data displays correctly
- [ ] Dates formatted properly
- [ ] Numbers formatted properly (currency, etc.)

## API Endpoints

### JSON Responses
- [ ] Content-Type is `application/json`
- [ ] Valid JSON returned
- [ ] Proper HTTP status codes
- [ ] Error messages included

### Request Parsing
- [ ] JSON body parsed correctly
- [ ] URL-encoded body parsed correctly
- [ ] Query parameters parsed correctly
- [ ] Content-Type header respected

## Performance

### Response Times
- [ ] Home page loads in < 1 second
- [ ] Login response in < 500ms
- [ ] API responses in < 300ms
- [ ] Static files cached (check Cache-Control header)

### Concurrent Requests
- [ ] Multiple users can login simultaneously
- [ ] Sessions don't interfere with each other
- [ ] Database pool handles concurrent queries

## Browser Compatibility

### Desktop Browsers
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (if available)

### Mobile Browsers
- [ ] Mobile Chrome
- [ ] Mobile Safari
- [ ] Responsive layout works

### Developer Tools
- [ ] No JavaScript errors in console
- [ ] No 404s in Network tab
- [ ] Cookies set correctly
- [ ] LocalStorage/SessionStorage used correctly (if applicable)

## Edge Cases

### Empty States
- [ ] New user with no cart items
- [ ] Customer with no orders
- [ ] Product with no description
- [ ] NULL phone number in customer

### Boundary Values
- [ ] Product ID = 0 rejected
- [ ] Quantity = 0 rejected
- [ ] Very long product names
- [ ] Very large quantities (999+)

### Special Characters
- [ ] Passwords with special characters
- [ ] Names with apostrophes (O'Brien)
- [ ] Emails with + or . characters
- [ ] Product names with quotes

## Deployment Readiness

### Configuration
- [ ] Environment variables work correctly
- [ ] PORT configurable via .env
- [ ] Database credentials from .env
- [ ] No hardcoded secrets in code

### Logging
- [ ] Requests logged to console
- [ ] Errors logged with stack traces
- [ ] Database queries logged (optional)

### Process Management
- [ ] Server restarts on crash
- [ ] Graceful shutdown on SIGTERM
- [ ] Graceful shutdown on SIGINT (Ctrl+C)
- [ ] Uncaught exceptions handled

## Code Quality

### Style & Formatting
- [ ] Consistent indentation (2 spaces)
- [ ] JSDoc comments for functions
- [ ] Meaningful variable names
- [ ] No commented-out code

### Best Practices
- [ ] No `eval()` usage
- [ ] No global variables (except sessions)
- [ ] Proper async/await usage
- [ ] Error handling in all async functions

### Dependencies
- [ ] Only 3 packages in package.json
- [ ] All dependencies have valid versions
- [ ] `npm audit` shows no vulnerabilities
- [ ] No unused dependencies

## Documentation

- [ ] SERVER_README.md exists and is complete
- [ ] QUICKSTART.md exists and is accurate
- [ ] MIGRATION_GUIDE.md exists and is helpful
- [ ] Code comments explain complex logic
- [ ] All routes documented

## Final Checks

- [ ] No Express or Express-related packages used
- [ ] Only built-in modules + mssql, dotenv, ejs
- [ ] School project requirements met
- [ ] Server runs for extended period without crashes
- [ ] Memory usage stable (no leaks)
- [ ] All features from original Flask app implemented

## Test Results Summary

| Category | Pass | Fail | Notes |
|----------|------|------|-------|
| Server Startup | ☐ | ☐ | |
| Authentication | ☐ | ☐ | |
| Session Management | ☐ | ☐ | |
| Shopping Cart | ☐ | ☐ | |
| Dashboards | ☐ | ☐ | |
| Security | ☐ | ☐ | |
| Error Handling | ☐ | ☐ | |
| Database | ☐ | ☐ | |
| Templates | ☐ | ☐ | |
| APIs | ☐ | ☐ | |
| **TOTAL** | ☐ | ☐ | |

## Acceptance Criteria

✅ **PASSED** if:
- All critical tests pass
- No security vulnerabilities
- Server runs stably for 1+ hour
- All user flows work end-to-end
- Only allowed dependencies used

❌ **FAILED** if:
- Any critical test fails
- Security issues found
- Server crashes or hangs
- User flows broken
- Forbidden dependencies used

---

**Tester Name:** _______________
**Date:** _______________
**Result:** ☐ PASSED | ☐ FAILED
