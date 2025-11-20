// app.js
require('dotenv').config();
const express = require('express');
const session = require('express-session');
const path = require('path');
const flash = require('connect-flash');
const bodyParser = require('body-parser');

const app = express();
const sql = require('mssql');

// views
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'ejs');

// middleware
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use('/static', express.static(path.join(__dirname, 'public')));

app.use(session({
  secret: process.env.SESSION_SECRET || 'dev_secret_123!@#',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 24*60*60*1000 }
}));
app.use(flash());

// routers
app.use('/', require('./routes/auth'));
app.use('/', require('./routes/products')); // keeps same url structure (/api/products/:id etc)
app.use('/', require('./routes/bag'));
app.use('/', require('./routes/lists'));
app.use('/', require('./routes/employees'));
app.use('/', require('./routes/admin'));
app.use('/', require('./routes/reports'));
app.use('/', require('./routes/customer'));
app.use('/', require('./routes/employee'));
app.use('/', require('./routes/reorderAlerts'));

// default 404
app.use((req, res) => {
  res.status(404).send('Not found');
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, ()=> console.log(`Server listening on :${PORT}`));

// middleware/withDB.js
const { getConnection } = require('../db');

module.exports = async function withDB(req, res, next) {
  try {
    req.db = await getConnection();
    next();
  } catch (err) {
    console.error('DB connection error', err);
    res.status(500).send('Database connection error');
  }
};

// middleware/authGuard.js
module.exports = function(requiredRoles = []) {
  return function(req, res, next) {
    const role = req.session.role;
    if (!role) {
      return res.redirect('/login'); // or 401 for API calls
    }
    if (requiredRoles.length && !requiredRoles.includes(role)) {
      return res.status(403).json({ error: 'Unauthorized' });
    }
    return next();
  };
};

// middleware/bagOwner.js
module.exports = function getBagOwner(req) {
  const role = req.session.role;
  const uid = req.session.user_id;
  if (role === 'customer' && uid) return { CustomerID: uid, EmployeeID: null };
  if (role === 'employee' && uid) return { CustomerID: null, EmployeeID: uid };
  return null;
};

// routes/auth.js
const express = require('express');
const router = express.Router();
const withDB = require('../middleware/withDB');

router.get('/', withDB, async (req, res) => {
  const pool = req.db;
  try {
    const productsRes = await pool.request()
      .query(`SELECT ProductID, Name, Description, Price, QuantityInStock, DepartmentID, ImageURL, OnSale FROM Product WHERE IsActive = 1`);
    const departmentsRes = await pool.request().query(`SELECT DepartmentID, Name FROM Department`);
    const products = productsRes.recordset || [];
    const departments = departmentsRes.recordset || [];

    let user = null;
    const role = req.session.role;
    if (role === 'customer') {
      const r = await pool.request().input('id', req.session.user_id)
        .query('SELECT Name FROM Customer WHERE CustomerID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role: 'customer' };
    } else if (role === 'admin') {
      const r = await pool.request().input('id', req.session.user_id)
        .query('SELECT Name FROM Administrator WHERE AdminID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role: 'admin' };
    } else if (role === 'employee') {
      const r = await pool.request().input('id', req.session.user_id)
        .query('SELECT Name FROM Employee WHERE EmployeeID = @id AND IsActive = 1');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role: 'employee' };
    }

    res.render('index', { products, departments, user });
  } catch (err) {
    console.error(err);
    res.render('error', { message: 'Failed to load home' });
  }
});

// status endpoint
router.get('/api/status', (req, res) => {
  res.json({ message: 'Express API is running and connected to Azure SQL!' });
});

// login
router.get('/login', (req, res) => res.render('login'));
router.post('/login', withDB, async (req, res) => {
  const data = req.body || {};
  const user_id = data.user_id || data.username || '';
  const password = data.password || '';
  if (!user_id || !password) return res.status(400).json({ success:false, message:'Missing credentials' });

  try {
    const pool = req.db;
    // check admin
    let r = await pool.request().input('username', user_id).input('password', password)
      .query('SELECT AdminID, Name FROM Administrator WHERE Username = @username AND Password = @password');
    if (r.recordset[0]) {
      req.session.user_id = r.recordset[0].AdminID;
      req.session.role = 'admin';
      return res.json({ success: true, role: 'admin', redirectUrl: '/admin' });
    }
    r = await pool.request().input('username', user_id).input('password', password)
      .query('SELECT EmployeeID, Name FROM Employee WHERE Username = @username AND Password = @password');
    if (r.recordset[0]) {
      req.session.user_id = r.recordset[0].EmployeeID;
      req.session.role = 'employee';
      return res.json({ success: true, role: 'employee', redirectUrl: '/employee' });
    }
    r = await pool.request().input('username', user_id).input('password', password)
      .query('SELECT CustomerID, Name FROM Customer WHERE username = @username AND password = @password');
    if (r.recordset[0]) {
      req.session.user_id = r.recordset[0].CustomerID;
      req.session.role = 'customer';
      return res.json({ success: true, role: 'customer', redirectUrl: '/customer' });
    }
    return res.status(401).json({ success:false, message:'Invalid ID or Password' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success:false, message:'Server error' });
  }
});

// register
router.get('/register', (req, res) => res.render('register'));
router.post('/register', withDB, async (req, res) => {
  const data = req.body || {};
  const { name, email, password, phone, username } = data;
  if (!name || !email || !password || !username) return res.status(400).json({ success:false, message:'Missing required fields' });
  try {
    const pool = req.db;
    let r = await pool.request().input('email', email).query('SELECT 1 FROM Customer WHERE Email = @email');
    if (r.recordset[0]) return res.status(409).json({ success:false, message: 'Email already registered' });
    r = await pool.request().input('username', username).query('SELECT 1 FROM Customer WHERE username = @username');
    if (r.recordset[0]) return res.status(409).json({ success:false, message: 'Username already taken' });
    await pool.request()
      .input('username', username).input('name', name).input('phone', phone).input('email', email).input('password', password)
      .query(`INSERT INTO Customer (username, Name, Phone, Email, password) VALUES (@username, @name, @phone, @email, @password)`);
    return res.status(201).json({ success:true, message:'Registration successful!' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success:false, message:'Server error' });
  }
});

module.exports = router;

// routes/products.js

const withDB = require('../middleware/withDB');
const authGuard = require('../middleware/authGuard')(); // use per-route

// manage products page (admin)
router.get('/admin/products', withDB, async (req, res) => {
  if (!req.session.role || !['admin','employee'].includes(req.session.role)) return res.redirect('/login');

  const search = req.query.search || '';
  const department = req.query.department || '';

  let query = `
    SELECT p.ProductID, p.Name, p.Description, p.Price, p.SalePrice, p.OnSale, p.QuantityInStock,
           p.Barcode, d.Name as DepartmentName, p.DepartmentID, p.ImageURL
    FROM Product p
    LEFT JOIN Department d ON p.DepartmentID = d.DepartmentID
    WHERE p.IsActive = 1
  `;
  const inputs = {};
  if (search) {
    query += ` AND (p.Name LIKE @search OR p.Description LIKE @search OR p.Barcode LIKE @search)`;
    inputs.search = `%${search}%`;
  }
  if (department) {
    query += ` AND p.DepartmentID = @dept`;
    inputs.dept = department;
  }
  query += ' ORDER BY p.Name';

  try {
    const pool = req.db;
    const reqQ = pool.request();
    if (inputs.search) reqQ.input('search', inputs.search);
    if (inputs.dept) reqQ.input('dept', inputs.dept);
    const productsRes = await reqQ.query(query);
    const departmentsRes = await pool.request().query('SELECT DepartmentID, Name FROM Department ORDER BY Name');
    res.render('manage_products', { products: productsRes.recordset, departments: departmentsRes.recordset, search, selected_dept: department });
  } catch (err) {
    console.error(err);
    res.render('error', { message: 'Failed to load products' });
  }
});

// GET product edit page
router.get('/admin/edit-product/:product_id', withDB, async (req, res) => {
  if (!req.session.role || !['admin','employee'].includes(req.session.role)) return res.redirect('/login');
  const id = parseInt(req.params.product_id, 10);
  try {
    const pool = req.db;
    const prodRes = await pool.request().input('id', id).query('SELECT * FROM Product WHERE ProductID = @id');
    if (!prodRes.recordset[0]) {
      req.flash('danger','Product not found.');
      return res.redirect('/admin/products');
    }
    const product = prodRes.recordset[0];
    const depts = await pool.request().query('SELECT DepartmentID, Name FROM Department ORDER BY Name');
    res.render('edit_product', { product, departments: depts.recordset });
  } catch (err) {
    console.error(err);
    res.render('error', { message: 'Failed to load product' });
  }
});

// POST edit product (form submit)
router.post('/admin/edit-product/:product_id', withDB, async (req, res) => {
  if (!req.session.role || !['admin','employee'].includes(req.session.role)) return res.redirect('/login');

  const pid = parseInt(req.params.product_id, 10);
  const data = req.body || {};
  try {
    const name = (data.Name || '').trim();
    if (!name) { req.flash('danger','Product name is required.'); return res.redirect(`/admin/edit-product/${pid}`); }
    const price = parseFloat(data.Price);
    const department_id = parseInt(data.DepartmentID,10);
    const quantity_in_stock = parseInt(data.QuantityInStock || 0, 10);
    const image_url = data.ImageURL || '';

    // if no image_url you'd call generate image here (omitted, see notes)
    const pool = req.db;
    await pool.request()
      .input('Name', name).input('Description', data.Description || '')
      .input('Price', price).input('DepartmentID', department_id)
      .input('QuantityInStock', quantity_in_stock).input('ImageURL', image_url)
      .input('ProductID', pid)
      .query(`
        UPDATE Product
        SET Name = @Name, Description = @Description, Price = @Price, DepartmentID = @DepartmentID,
            QuantityInStock = @QuantityInStock, ImageURL = @ImageURL
        WHERE ProductID = @ProductID
      `);
    req.flash('success', `Product '${name}' updated successfully!`);
    return res.redirect('/admin/products');
  } catch (err) {
    console.error(err);
    req.flash('danger', 'Failed to update product.');
    return res.redirect(`/admin/edit-product/${req.params.product_id}`);
  }
});

// API: delete product (soft delete)
router.delete('/api/products/:product_id', withDB, async (req, res) => {
  if (!req.session.role || req.session.role !== 'admin') return res.status(403).json({message:'Unauthorized'});
  const product_id = parseInt(req.params.product_id,10);
  try {
    const pool = req.db;
    const r = await pool.request().input('id', product_id).query('SELECT Name FROM Product WHERE ProductID = @id');
    if (!r.recordset[0]) return res.status(404).json({message:'Product not found'});
    const product_name = r.recordset[0].Name;
    await pool.request().input('id', product_id).query('UPDATE Product SET IsActive = 0 WHERE ProductID = @id');
    return res.json({message: `Product '${product_name}' has been deactivated`});
  } catch (err) {
    console.error(err);
    return res.status(500).json({message:'Error deactivating product'});
  }
});

// API low stock
router.get('/api/low_stock', withDB, async (req, res) => {
  if (!req.session.user_id || !['admin','employee'].includes(req.session.role)) return res.status(403).json({error:'Unauthorized'});
  try {
    const pool = req.db;
    const r = await pool.request().query(`
      SELECT ProductID, Name, QuantityInStock, DepartmentID
      FROM Product
      WHERE QuantityInStock < 10
      ORDER BY QuantityInStock ASC
    `);
    res.json(r.recordset);
  } catch (err) {
    console.error(err);
    res.status(500).json({error:'Server error'});
  }
});

// API update stock
router.post('/api/update_stock', withDB, async (req, res) => {
  if (!req.session.user_id || !['admin','employee'].includes(req.session.role)) return res.status(403).json({error:'Unauthorized'});
  const { product_id, new_stock } = req.body || {};
  if (product_id == null || new_stock == null) return res.status(400).json({ error: 'Missing fields' });
  const pid = parseInt(product_id,10);
  const ns = parseInt(new_stock,10);
  if (isNaN(ns) || ns < 0) return res.status(400).json({ error:'Stock cannot be negative' });
  try {
    await req.db.request().input('ns', ns).input('pid', pid).query('UPDATE Product SET QuantityInStock = @ns WHERE ProductID = @pid');
    res.json({message:'Stock updated successfully'});
  } catch (err) {
    console.error(err);
    res.status(500).json({error:'Server error'});
  }
});

module.exports = router;

// routes/bag.js

const withDB = require('../middleware/withDB');
const getBagOwner = require('../middleware/bagOwner');

router.get('/bag', withDB, async (req, res) => {
  // render bag page (like Flask)
  let user = null;
  if (req.session.user_id) {
    const role = req.session.role;
    const pool = req.db;
    if (role === 'customer') {
      const r = await pool.request().input('id', req.session.user_id).query('SELECT Name FROM Customer WHERE CustomerID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role: 'customer' };
    } else if (role === 'admin') {
      const r = await pool.request().input('id', req.session.user_id).query('SELECT Name FROM Administrator WHERE AdminID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role:'admin' };
    } else if (role === 'employee') {
      const r = await pool.request().input('id', req.session.user_id).query('SELECT Name FROM Employee WHERE EmployeeID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role:'employee' };
    }
  }
  res.render('bag', { user });
});

router.get('/api/bag', withDB, async (req, res) => {
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({ message:'Login required' });
  try {
    const pool = req.db;
    let query, inputName, inputVal;
    if (owner.CustomerID != null) {
      query = `SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
               FROM dbo.Bag b JOIN dbo.Product p ON p.ProductID = b.ProductID
               WHERE b.CustomerID = @id AND b.EmployeeID IS NULL
               ORDER BY b.AddedAt DESC`;
      inputName = 'id'; inputVal = owner.CustomerID;
    } else {
      query = `SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
               FROM dbo.Bag b JOIN dbo.Product p ON p.ProductID = b.ProductID
               WHERE b.EmployeeID = @id AND b.CustomerID IS NULL
               ORDER BY b.AddedAt DESC`;
      inputName = 'id'; inputVal = owner.EmployeeID;
    }
    const r = await pool.request().input(inputName, inputVal).query(query);
    res.json(r.recordset);
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: 'Server error' });
  }
});

router.post('/api/bag', withDB, async (req, res) => {
  const payload = req.body || {};
  let pid = parseInt(payload.product_id || 0,10);
  let qty = parseInt(payload.quantity || 1,10);
  if (!pid || pid <= 0 || !qty || qty <= 0) return res.status(400).json({ message:'Bad item' });

  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({ message:'Login required' });

  try {
    const pool = req.db;
    if (owner.CustomerID != null) {
      await pool.request()
        .input('cid', owner.CustomerID).input('pid', pid).input('qty', qty)
        .query(`
          MERGE dbo.Bag AS target
          USING (SELECT @cid AS CustomerID, @pid AS ProductID) AS src
          ON target.CustomerID = src.CustomerID AND target.ProductID = src.ProductID AND target.EmployeeID IS NULL
          WHEN MATCHED THEN UPDATE SET Quantity = target.Quantity + @qty
          WHEN NOT MATCHED THEN INSERT (CustomerID, EmployeeID, ProductID, Quantity) VALUES (src.CustomerID, NULL, src.ProductID, @qty);
        `);
    } else {
      await pool.request()
        .input('eid', owner.EmployeeID).input('pid', pid).input('qty', qty)
        .query(`
          MERGE dbo.Bag AS target
          USING (SELECT @eid AS EmployeeID, @pid AS ProductID) AS src
          ON target.EmployeeID = src.EmployeeID AND target.ProductID = src.ProductID AND target.CustomerID IS NULL
          WHEN MATCHED THEN UPDATE SET Quantity = target.Quantity + @qty
          WHEN NOT MATCHED THEN INSERT (CustomerID, EmployeeID, ProductID, Quantity) VALUES (NULL, src.EmployeeID, src.ProductID, @qty);
        `);
    }
    await pool.request().query('COMMIT');
    res.status(201).json({ message:'Added' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: 'Server error' });
  }
});

// patch quantity
router.patch('/api/bag/:bag_id', withDB, async (req, res) => {
  const bag_id = parseInt(req.params.bag_id,10);
  const payload = req.body || {};
  const qty = parseInt(payload.quantity || 0,10);
  if (isNaN(qty) || qty < 0) return res.status(400).json({message:'Bad quantity'});
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({message:'Login required'});
  try {
    const pool = req.db;
    if (owner.CustomerID != null) {
      const r = await pool.request().input('qty', qty).input('bid', bag_id).input('cid', owner.CustomerID)
        .query('UPDATE dbo.Bag SET Quantity = @qty WHERE BagID = @bid AND CustomerID = @cid AND EmployeeID IS NULL');
      if (r.rowsAffected[0] === 0) return res.status(404).json({message:'Not found'});
    } else {
      const r = await pool.request().input('qty', qty).input('bid', bag_id).input('eid', owner.EmployeeID)
        .query('UPDATE dbo.Bag SET Quantity = @qty WHERE BagID = @bid AND EmployeeID = @eid AND CustomerID IS NULL');
      if (r.rowsAffected[0] === 0) return res.status(404).json({message:'Not found'});
    }
    res.json({message:'Updated'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

// delete item
router.delete('/api/bag/:bag_id', withDB, async (req, res) => {
  const bag_id = parseInt(req.params.bag_id,10);
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({message:'Login required'});
  try {
    const pool = req.db;
    let result;
    if (owner.CustomerID != null) {
      result = await pool.request().input('bid', bag_id).input('cid', owner.CustomerID)
        .query('DELETE FROM dbo.Bag WHERE BagID = @bid AND CustomerID = @cid AND EmployeeID IS NULL');
    } else {
      result = await pool.request().input('bid', bag_id).input('eid', owner.EmployeeID)
        .query('DELETE FROM dbo.Bag WHERE BagID = @bid AND EmployeeID = @eid AND CustomerID IS NULL');
    }
    if (result.rowsAffected[0] === 0) return res.status(404).json({message:'Not found'});
    res.json({message:'Deleted'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

// clear bag
router.delete('/api/bag', withDB, async (req, res) => {
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({message:'Login required'});
  try {
    const pool = req.db;
    if (owner.CustomerID != null) {
      await pool.request().input('cid', owner.CustomerID).query('DELETE FROM dbo.Bag WHERE CustomerID = @cid AND EmployeeID IS NULL');
    } else {
      await pool.request().input('eid', owner.EmployeeID).query('DELETE FROM dbo.Bag WHERE EmployeeID = @eid AND CustomerID IS NULL');
    }
    res.json({message:'Cleared'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

module.exports = router;

// routes/bag.js
const withDB = require('../middleware/withDB');
const getBagOwner = require('../middleware/bagOwner');

router.get('/bag', withDB, async (req, res) => {
  // render bag page (like Flask)
  let user = null;
  if (req.session.user_id) {
    const role = req.session.role;
    const pool = req.db;
    if (role === 'customer') {
      const r = await pool.request().input('id', req.session.user_id).query('SELECT Name FROM Customer WHERE CustomerID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role: 'customer' };
    } else if (role === 'admin') {
      const r = await pool.request().input('id', req.session.user_id).query('SELECT Name FROM Administrator WHERE AdminID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role:'admin' };
    } else if (role === 'employee') {
      const r = await pool.request().input('id', req.session.user_id).query('SELECT Name FROM Employee WHERE EmployeeID = @id');
      if (r.recordset[0]) user = { Name: r.recordset[0].Name, role:'employee' };
    }
  }
  res.render('bag', { user });
});

router.get('/api/bag', withDB, async (req, res) => {
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({ message:'Login required' });
  try {
    const pool = req.db;
    let query, inputName, inputVal;
    if (owner.CustomerID != null) {
      query = `SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
               FROM dbo.Bag b JOIN dbo.Product p ON p.ProductID = b.ProductID
               WHERE b.CustomerID = @id AND b.EmployeeID IS NULL
               ORDER BY b.AddedAt DESC`;
      inputName = 'id'; inputVal = owner.CustomerID;
    } else {
      query = `SELECT b.BagID, b.ProductID, p.Name, p.Price, b.Quantity, b.AddedAt
               FROM dbo.Bag b JOIN dbo.Product p ON p.ProductID = b.ProductID
               WHERE b.EmployeeID = @id AND b.CustomerID IS NULL
               ORDER BY b.AddedAt DESC`;
      inputName = 'id'; inputVal = owner.EmployeeID;
    }
    const r = await pool.request().input(inputName, inputVal).query(query);
    res.json(r.recordset);
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: 'Server error' });
  }
});

router.post('/api/bag', withDB, async (req, res) => {
  const payload = req.body || {};
  let pid = parseInt(payload.product_id || 0,10);
  let qty = parseInt(payload.quantity || 1,10);
  if (!pid || pid <= 0 || !qty || qty <= 0) return res.status(400).json({ message:'Bad item' });

  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({ message:'Login required' });

  try {
    const pool = req.db;
    if (owner.CustomerID != null) {
      await pool.request()
        .input('cid', owner.CustomerID).input('pid', pid).input('qty', qty)
        .query(`
          MERGE dbo.Bag AS target
          USING (SELECT @cid AS CustomerID, @pid AS ProductID) AS src
          ON target.CustomerID = src.CustomerID AND target.ProductID = src.ProductID AND target.EmployeeID IS NULL
          WHEN MATCHED THEN UPDATE SET Quantity = target.Quantity + @qty
          WHEN NOT MATCHED THEN INSERT (CustomerID, EmployeeID, ProductID, Quantity) VALUES (src.CustomerID, NULL, src.ProductID, @qty);
        `);
    } else {
      await pool.request()
        .input('eid', owner.EmployeeID).input('pid', pid).input('qty', qty)
        .query(`
          MERGE dbo.Bag AS target
          USING (SELECT @eid AS EmployeeID, @pid AS ProductID) AS src
          ON target.EmployeeID = src.EmployeeID AND target.ProductID = src.ProductID AND target.CustomerID IS NULL
          WHEN MATCHED THEN UPDATE SET Quantity = target.Quantity + @qty
          WHEN NOT MATCHED THEN INSERT (CustomerID, EmployeeID, ProductID, Quantity) VALUES (NULL, src.EmployeeID, src.ProductID, @qty);
        `);
    }
    await pool.request().query('COMMIT');
    res.status(201).json({ message:'Added' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: 'Server error' });
  }
});

// patch quantity
router.patch('/api/bag/:bag_id', withDB, async (req, res) => {
  const bag_id = parseInt(req.params.bag_id,10);
  const payload = req.body || {};
  const qty = parseInt(payload.quantity || 0,10);
  if (isNaN(qty) || qty < 0) return res.status(400).json({message:'Bad quantity'});
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({message:'Login required'});
  try {
    const pool = req.db;
    if (owner.CustomerID != null) {
      const r = await pool.request().input('qty', qty).input('bid', bag_id).input('cid', owner.CustomerID)
        .query('UPDATE dbo.Bag SET Quantity = @qty WHERE BagID = @bid AND CustomerID = @cid AND EmployeeID IS NULL');
      if (r.rowsAffected[0] === 0) return res.status(404).json({message:'Not found'});
    } else {
      const r = await pool.request().input('qty', qty).input('bid', bag_id).input('eid', owner.EmployeeID)
        .query('UPDATE dbo.Bag SET Quantity = @qty WHERE BagID = @bid AND EmployeeID = @eid AND CustomerID IS NULL');
      if (r.rowsAffected[0] === 0) return res.status(404).json({message:'Not found'});
    }
    res.json({message:'Updated'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

// delete item
router.delete('/api/bag/:bag_id', withDB, async (req, res) => {
  const bag_id = parseInt(req.params.bag_id,10);
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({message:'Login required'});
  try {
    const pool = req.db;
    let result;
    if (owner.CustomerID != null) {
      result = await pool.request().input('bid', bag_id).input('cid', owner.CustomerID)
        .query('DELETE FROM dbo.Bag WHERE BagID = @bid AND CustomerID = @cid AND EmployeeID IS NULL');
    } else {
      result = await pool.request().input('bid', bag_id).input('eid', owner.EmployeeID)
        .query('DELETE FROM dbo.Bag WHERE BagID = @bid AND EmployeeID = @eid AND CustomerID IS NULL');
    }
    if (result.rowsAffected[0] === 0) return res.status(404).json({message:'Not found'});
    res.json({message:'Deleted'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

// clear bag
router.delete('/api/bag', withDB, async (req, res) => {
  const owner = getBagOwner(req);
  if (!owner) return res.status(401).json({message:'Login required'});
  try {
    const pool = req.db;
    if (owner.CustomerID != null) {
      await pool.request().input('cid', owner.CustomerID).query('DELETE FROM dbo.Bag WHERE CustomerID = @cid AND EmployeeID IS NULL');
    } else {
      await pool.request().input('eid', owner.EmployeeID).query('DELETE FROM dbo.Bag WHERE EmployeeID = @eid AND CustomerID IS NULL');
    }
    res.json({message:'Cleared'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

module.exports = router;

// routes/lists.js
const withDB = require('../middleware/withDB');

function requireCustomer(req, res, next) {
  if (req.session.role !== 'customer') return res.status(401).json({message:'Login required'});
  req.customer_id = req.session.user_id;
  return next();
}

async function ensureDefaultList(pool, customer_id) {
  const r = await pool.request().input('cid', customer_id).query('SELECT ListID FROM dbo.ShoppingList WHERE CustomerID=@cid AND IsDefault=1');
  if (r.recordset[0]) return r.recordset[0].ListID;
  // Insert and get Inserted ID (SQL Server OUTPUT style)
  const insertRes = await pool.request().input('cid', customer_id).query(`
    INSERT INTO dbo.ShoppingList (CustomerID, Name, IsDefault, CreatedAt)
    OUTPUT Inserted.ListID
    VALUES (@cid, N'Default', 1, GETDATE());
  `);
  return insertRes.recordset[0].ListID;
}

router.get('/shopping-lists', withDB, async (req, res) => {
  let user = null;
  if (req.session.user_id) {
    // similar user name logic as bag
  }
  res.render('shopping_lists', { user });
});

// API: lists
router.get('/api/lists', withDB, requireCustomer, async (req, res) => {
  try {
    const pool = req.db;
    await ensureDefaultList(pool, req.customer_id);
    const r = await pool.request().input('cid', req.customer_id).query(`
      SELECT l.ListID, l.Name, l.IsDefault,
             ISNULL(SUM(i.Quantity), 0) AS ItemCount,
             MIN(l.CreatedAt) AS CreatedAt
      FROM dbo.ShoppingList l
      LEFT JOIN dbo.ShoppingListItem i ON i.ListID = l.ListID
      WHERE l.CustomerID = @cid
      GROUP BY l.ListID, l.Name, l.IsDefault
      ORDER BY l.IsDefault DESC, CreatedAt ASC
    `);
    res.json(r.recordset);
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

router.post('/api/lists', withDB, requireCustomer, async (req, res) => {
  const name = (req.body.name || '').trim();
  if (!name) return res.status(400).json({message:'Name required'});
  try {
    const pool = req.db;
    await ensureDefaultList(pool, req.customer_id);
    await pool.request().input('cid', req.customer_id).input('name', name)
      .query('INSERT INTO dbo.ShoppingList(CustomerID, Name, IsDefault, CreatedAt) VALUES(@cid, @name, 0, GETDATE())');
    res.json({message:'Created'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

// delete list
router.delete('/api/lists/:list_id', withDB, requireCustomer, async (req, res) => {
  const list_id = parseInt(req.params.list_id,10);
  try {
    const pool = req.db;
    const r = await pool.request().input('lid', list_id).input('cid', req.customer_id).query('SELECT IsDefault FROM dbo.ShoppingList WHERE ListID=@lid AND CustomerID=@cid');
    if (!r.recordset[0]) return res.status(404).json({message:'Not found'});
    if (r.recordset[0].IsDefault) return res.status(400).json({message:'Default list cannot be deleted'});
    await pool.request().input('lid', list_id).query('DELETE FROM dbo.ShoppingListItem WHERE ListID=@lid');
    await pool.request().input('lid', list_id).input('cid', req.customer_id).query('DELETE FROM dbo.ShoppingList WHERE ListID=@lid AND CustomerID=@cid');
    res.json({message:'Deleted'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

// items endpoints (list items, add, update, delete, clear) - implement similarly
router.get('/api/lists/:list_id/items', withDB, requireCustomer, async (req, res) => {
  const list_id = parseInt(req.params.list_id,10);
  try {
    const pool = req.db;
    const exists = await pool.request().input('lid', list_id).input('cid', req.customer_id).query('SELECT 1 FROM dbo.ShoppingList WHERE ListID=@lid AND CustomerID=@cid');
    if (!exists.recordset[0]) return res.status(404).json({message:'Not found'});
    const r = await pool.request().input('lid', list_id).query(`
      SELECT i.ProductID, i.Quantity, p.Name, p.Price,
             CONVERT(VARCHAR(19), i.AddedAt, 120) AS AddedAt
      FROM dbo.ShoppingListItem i
      JOIN dbo.Product p ON p.ProductID = i.ProductID
      WHERE i.ListID = @lid
      ORDER BY i.AddedAt DESC
    `);
    res.json(r.recordset);
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

router.post('/api/lists/:list_id/items', withDB, requireCustomer, async (req, res) => {
  const list_id = parseInt(req.params.list_id,10);
  try {
    const pool = req.db;
    const exists = await pool.request().input('lid', list_id).input('cid', req.customer_id).query('SELECT 1 FROM dbo.ShoppingList WHERE ListID=@lid AND CustomerID=@cid');
    if (!exists.recordset[0]) return res.status(404).json({message:'Not found'});
    const pid = parseInt(req.body.product_id || 0,10);
    const qty = parseInt(req.body.quantity || 1,10);
    if (pid <= 0 || qty <= 0) return res.status(400).json({message:'Bad payload'});
    await pool.request().input('lid', list_id).input('pid', pid).input('qty', qty).query(`
      MERGE dbo.ShoppingListItem AS t
      USING (VALUES (@lid, @pid, @qty)) AS s(ListID, ProductID, Quantity)
      ON (t.ListID = s.ListID AND t.ProductID = s.ProductID)
      WHEN MATCHED THEN UPDATE SET Quantity = t.Quantity + s.Quantity, AddedAt = GETDATE()
      WHEN NOT MATCHED THEN INSERT (ListID, ProductID, Quantity, AddedAt) VALUES (s.ListID, s.ProductID, s.Quantity, GETDATE());
    `);
    res.json({message:'Added'});
  } catch (err) {
    console.error(err);
    res.status(500).json({message:'Server error'});
  }
});

// other list item endpoints (patch, delete, clear) implemented similarly...
module.exports = router;

// utils/image.js
const fetch = require('node-fetch');
async function generateProductImage(productName) {
  const key = process.env.UNSPLASH_KEY;
  if (!key) return 'https://via.placeholder.com/400?text=Product+Image';
  try {
    const res = await fetch(`https://api.unsplash.com/photos/random?query=${encodeURIComponent(productName)}&orientation=squarish&client_id=${key}`);
    const data = await res.json();
    return data?.urls?.regular || 'https://via.placeholder.com/400?text=Product+Image';
  } catch (e) {
    console.error('unsplash error', e);
    return 'https://via.placeholder.com/400?text=Product+Image';
  }
}
module.exports = { generateProductImage };

// routes/employees.js
const withDB = require("../middleware/withDB");
const authGuard = require("../middleware/authGuard");

// ------------------------------
// Helpers
// ------------------------------
function requireAdmin(req, res, next) {
    if (req.session.role !== "admin") {
        return res.status(403).json({ error: "Unauthorized" });
    }
    next();
}

// ------------------------------
// GET: Render employee management page
// URL: /employees
// ------------------------------
router.get("/employees", withDB, requireAdmin, async (req, res) => {
    try {
        const pool = req.db;

        const employeesRes = await pool
            .request()
            .query(`
                SELECT EmployeeID, Name, Username, Phone, Email, Position, Salary, IsActive
                FROM Employee
                ORDER BY Name
            `);

        res.render("manage_employees", {
            employees: employeesRes.recordset,
            user: { role: "admin" }
        });

    } catch (err) {
        console.error(err);
        res.render("error", { message: "Failed to load employees." });
    }
});

// ------------------------------
// GET: Single employee details
// URL: /api/employees/:emp_id
// ------------------------------
router.get("/api/employees/:emp_id", withDB, requireAdmin, async (req, res) => {
    const emp_id = parseInt(req.params.emp_id, 10);

    if (isNaN(emp_id)) {
        return res.status(400).json({ error: "Invalid employee ID" });
    }

    try {
        const pool = req.db;

        const result = await pool
            .request()
            .input("emp_id", emp_id)
            .query(`
                SELECT EmployeeID, Name, Username, Phone, Email, Position, Salary, IsActive
                FROM Employee
                WHERE EmployeeID = @emp_id
            `);

        if (!result.recordset[0]) {
            return res.status(404).json({ error: "Employee not found" });
        }

        res.json(result.recordset[0]);

    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Server error" });
    }
});

// ------------------------------
// POST: Add new employee
// URL: /api/employees/add
// ------------------------------
router.post("/api/employees/add", withDB, requireAdmin, async (req, res) => {
    const { name, username, password, phone, email, position, salary } = req.body;

    if (!name || !username || !password) {
        return res.status(400).json({ error: "Missing required fields" });
    }

    try {
        const pool = req.db;

        // Check username unique
        const exists = await pool
            .request()
            .input("username", username)
            .query("SELECT 1 FROM Employee WHERE Username = @username");

        if (exists.recordset.length > 0) {
            return res.status(409).json({ error: "Username already taken" });
        }

        await pool
            .request()
            .input("name", name)
            .input("username", username)
            .input("password", password)
            .input("phone", phone || "")
            .input("email", email || "")
            .input("position", position || "")
            .input("salary", salary || 0)
            .query(`
                INSERT INTO Employee (Name, Username, Password, Phone, Email, Position, Salary, IsActive)
                VALUES (@name, @username, @password, @phone, @email, @position, @salary, 1)
            `);

        res.json({ message: "Employee added successfully" });

    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Server error" });
    }
});

// ------------------------------
// POST: Edit employee
// URL: /api/employees/edit/:emp_id
// ------------------------------
router.post("/api/employees/edit/:emp_id", withDB, requireAdmin, async (req, res) => {
    const emp_id = parseInt(req.params.emp_id, 10);
    const { name, username, password, phone, email, position, salary } = req.body;

    if (isNaN(emp_id)) {
        return res.status(400).json({ error: "Invalid employee ID" });
    }

    if (!name || !username) {
        return res.status(400).json({ error: "Missing required fields" });
    }

    try {
        const pool = req.db;

        // Check if username conflicts with another employee
        const exists = await pool
            .request()
            .input("username", username)
            .input("emp_id", emp_id)
            .query(`
                SELECT 1 FROM Employee
                WHERE Username = @username AND EmployeeID != @emp_id
            `);

        if (exists.recordset.length > 0) {
            return res.status(409).json({ error: "Username already in use by another employee" });
        }

        // Update
        const request = pool
            .request()
            .input("emp_id", emp_id)
            .input("name", name)
            .input("username", username)
            .input("phone", phone || "")
            .input("email", email || "")
            .input("position", position || "")
            .input("salary", salary || 0);

        let updateSQL = `
            UPDATE Employee
            SET Name = @name,
                Username = @username,
                Phone = @phone,
                Email = @email,
                Position = @position,
                Salary = @salary
        `;

        if (password && password.trim() !== "") {
            request.input("password", password);
            updateSQL += ", Password = @password ";
        }

        updateSQL += "WHERE EmployeeID = @emp_id";

        await request.query(updateSQL);

        res.json({ message: "Employee updated successfully" });

    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Server error" });
    }
});

// ------------------------------
// DELETE: Remove employee (soft delete)
// URL: /api/employees/delete/:emp_id
// ------------------------------
router.delete("/api/employees/delete/:emp_id", withDB, requireAdmin, async (req, res) => {
    const emp_id = parseInt(req.params.emp_id, 10);

    if (isNaN(emp_id)) {
        return res.status(400).json({ error: "Invalid employee ID" });
    }

    try {
        const pool = req.db;

        // Make sure employee exists
        const check = await pool
            .request()
            .input("emp_id", emp_id)
            .query("SELECT Name FROM Employee WHERE EmployeeID = @emp_id");

        if (!check.recordset[0]) {
            return res.status(404).json({ error: "Employee not found" });
        }

        await pool
            .request()
            .input("emp_id", emp_id)
            .query(`
                UPDATE Employee
                SET IsActive = 0
                WHERE EmployeeID = @emp_id
            `);

        res.json({ message: "Employee deleted successfully" });

    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Server error" });
    }
});

module.exports = router;

// routes/admin.js

const withDB = require("../middleware/withDB");
const sql = require("mssql");

// ------------------------------
// HELPERS
// ------------------------------
function requireAdmin(req, res, next) {
    if (req.session.role !== "admin") {
        return res.status(403).send("Unauthorized");
    }
    next();
}

// ------------------------------
// GET: Admin Dashboard
// URL: /admin
// ------------------------------
router.get("/", withDB, requireAdmin, async (req, res) => {
    try {
        const db = req.db;

        // Total products
        const totalProducts = await db.request().query(`
            SELECT COUNT(*) AS count FROM Product
        `);

        // Total employees
        const totalEmployees = await db.request().query(`
            SELECT COUNT(*) AS count FROM Employee WHERE IsActive = 1
        `);

        // Low stock products
        const lowStock = await db.request().query(`
            SELECT COUNT(*) AS count 
            FROM Product 
            WHERE QuantityInStock <= ReorderLevel
        `);

        // Total orders
        const totalOrders = await db.request().query(`
            SELECT COUNT(*) AS count FROM Orders
        `);

        // Category summary
        const categoryStats = await db.request().query(`
            SELECT d.DepartmentName, COUNT(p.ProductID) AS ProductCount
            FROM Department d
            LEFT JOIN Product p ON d.DepartmentID = p.DepartmentID
            GROUP BY d.DepartmentName
        `);

        // Daily Sales
        const dailySales = await db.request().query(`
            SELECT 
                CAST(OrderDate AS DATE) AS Date,
                SUM(TotalAmount) AS TotalSales
            FROM Orders
            GROUP BY CAST(OrderDate AS DATE)
            ORDER BY Date DESC
        `);

        // Featured products (same as Flask: highest stock OR new arrivals)
        const featured = await db.request().query(`
            SELECT TOP 6 ProductID, Name, Price, QuantityInStock, ImageURL
            FROM Product
            ORDER BY NEWID()
        `);

        res.render("admin_dashboard", {
            totals: {
                products: totalProducts.recordset[0].count,
                employees: totalEmployees.recordset[0].count,
                lowStock: lowStock.recordset[0].count,
                orders: totalOrders.recordset[0].count
            },
            categoryStats: categoryStats.recordset,
            dailySales: dailySales.recordset,
            featured: featured.recordset,
            user: { role: "admin" }
        });

    } catch (err) {
        console.error("Admin dashboard error:", err);
        res.status(500).render("error", { message: "Failed to load admin dashboard." });
    }
});

// ------------------------------
// POST: Apply Seasonal Sale (20% discount)
// URL: /apply_sales
// ------------------------------
router.post("/apply_sales", withDB, requireAdmin, async (req, res) => {
    try {
        const db = req.db;

        // Apply direct 20% discount
        await db.request().query(`
            UPDATE Product
            SET Price = Price * 0.80
        `);

        return res.json({ message: "Seasonal sale prices applied!" });

    } catch (err) {
        console.error("Apply Sales Error:", err);
        res.status(500).json({ error: "Failed to apply sale." });
    }
});

// ------------------------------
// GET: All Orders (Admin)
// URL: /admin/orders
// ------------------------------
router.get("/orders", withDB, requireAdmin, async (req, res) => {
    try {
        const db = req.db;

        const orders = await db.request().query(`
            SELECT o.OrderID, o.UserID, u.Name AS CustomerName, 
                   o.TotalAmount, o.OrderDate, o.Status
            FROM Orders o
            LEFT JOIN Users u ON o.UserID = u.UserID
            ORDER BY o.OrderDate DESC
        `);

        res.render("admin_orders", {
            orders: orders.recordset,
            user: { role: "admin" }
        });

    } catch (err) {
        console.error("Admin orders error:", err);
        res.status(500).render("error", { message: "Failed to load orders." });
    }
});

// ------------------------------
// GET: Single Order Details (Admin)
// URL: /admin/orders/:id
// ------------------------------
router.get("/orders/:id", withDB, requireAdmin, async (req, res) => {
    const orderId = parseInt(req.params.id);

    if (isNaN(orderId)) {
        return res.status(400).send("Invalid order ID");
    }

    try {
        const db = req.db;

        // Order header
        const orderInfo = await db.request()
            .input("orderId", sql.Int, orderId)
            .query(`
                SELECT o.OrderID, o.UserID, u.Name AS CustomerName, 
                       o.TotalAmount, o.OrderDate, o.Status
                FROM Orders o
                LEFT JOIN Users u ON o.UserID = u.UserID
                WHERE o.OrderID = @orderId
            `);

        // Order items
        const orderItems = await db.request()
            .input("orderId", sql.Int, orderId)
            .query(`
                SELECT od.ProductID, p.Name, od.Quantity, od.Price
                FROM OrderDetails od
                JOIN Product p ON od.ProductID = p.ProductID
                WHERE od.OrderID = @orderId
            `);

        if (orderInfo.recordset.length === 0) {
            return res.status(404).render("error", { message: "Order not found." });
        }

        res.render("admin_order_detail", {
            order: orderInfo.recordset[0],
            items: orderItems.recordset,
            user: { role: "admin" }
        });

    } catch (err) {
        console.error("Admin order detail error:", err);
        res.status(500).render("error", { message: "Failed to load order details." });
    }
});

module.exports = router;


const sql = require('mssql'); // Assuming you're using mssql package

// Middleware to check admin role
function checkAdmin(req, res, next) {
    if (!req.session || req.session.role !== 'admin') {
        return res.status(403).json({ error: 'Unauthorized' });
    }
    next();
}

// GET /api/reports/sales - Get sales report
router.get('/sales', checkAdmin, async (req, res) => {
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request().query('EXEC GetSalesReport');
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// GET /api/reports/inventory - Get inventory report
router.get('/inventory', checkAdmin, async (req, res) => {
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request().query('EXEC GetInventoryReport');
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// GET /api/reports/customers - Get top customer report
router.get('/customers', checkAdmin, async (req, res) => {
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request().query('EXEC GetTopCustomersReport');
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/reports/custom - Run a custom report stored procedure
router.post('/custom', checkAdmin, async (req, res) => {
    const { reportName, params } = req.body;
    try {
        const pool = await sql.connect(req.dbConfig);
        const request = pool.request();
        if (params) {
            for (const key in params) {
                request.input(key, params[key]);
            }
        }
        const result = await request.execute(reportName);
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});


// Middleware to check admin role
function checkAdmin(req, res, next) {
    if (!req.session || req.session.role !== 'admin') {
        return res.status(403).json({ error: 'Unauthorized' });
    }
    next();
}

// GET /api/reorderAlerts - Get all products that need reorder
router.get('/', checkAdmin, async (req, res) => {
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request().query('EXEC GetReorderAlerts');
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/reorderAlerts/mark - Mark a product as reordered
router.post('/mark', checkAdmin, async (req, res) => {
    const { productId } = req.body;
    if (!productId) {
        return res.status(400).json({ error: 'Product ID is required' });
    }

    try {
        const pool = await sql.connect(req.dbConfig);
        await pool.request()
            .input('ProductID', sql.Int, productId)
            .query('EXEC MarkProductReordered @ProductID');
        res.json({ message: 'Product marked as reordered.' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/reorderAlerts/custom - Run custom reorder alert procedure
router.post('/custom', checkAdmin, async (req, res) => {
    const { procedureName, params } = req.body;
    try {
        const pool = await sql.connect(req.dbConfig);
        const request = pool.request();
        if (params) {
            for (const key in params) {
                request.input(key, params[key]);
            }
        }
        const result = await request.execute(procedureName);
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Middleware to check admin role
function checkAdmin(req, res, next) {
    if (!req.session || req.session.role !== 'admin') {
        return res.status(403).json({ error: 'Unauthorized' });
    }
    next();
}

// GET /api/customers - Get all customers
router.get('/', checkAdmin, async (req, res) => {
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request().query('EXEC GetAllCustomers');
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// GET /api/customers/:customerId - Get customer by ID
router.get('/:customerId', checkAdmin, async (req, res) => {
    const { customerId } = req.params;
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request()
            .input('CustomerID', sql.Int, customerId)
            .query('EXEC GetCustomerByID @CustomerID');
        res.json(result.recordset[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/customers/add - Add new customer
router.post('/add', checkAdmin, async (req, res) => {
    const { Name, Email, Phone } = req.body;
    try {
        const pool = await sql.connect(req.dbConfig);
        await pool.request()
            .input('Name', sql.NVarChar, Name)
            .input('Email', sql.NVarChar, Email)
            .input('Phone', sql.NVarChar, Phone)
            .query('EXEC AddCustomer @Name, @Email, @Phone');
        res.json({ message: 'Customer added successfully' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/customers/edit/:customerId - Edit customer
router.post('/edit/:customerId', checkAdmin, async (req, res) => {
    const { customerId } = req.params;
    const { Name, Email, Phone } = req.body;
    try {
        const pool = await sql.connect(req.dbConfig);
        await pool.request()
            .input('CustomerID', sql.Int, customerId)
            .input('Name', sql.NVarChar, Name)
            .input('Email', sql.NVarChar, Email)
            .input('Phone', sql.NVarChar, Phone)
            .query('EXEC UpdateCustomer @CustomerID, @Name, @Email, @Phone');
        res.json({ message: 'Customer updated successfully' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// DELETE /api/customers/delete/:customerId - Delete customer
router.delete('/delete/:customerId', checkAdmin, async (req, res) => {
    const { customerId } = req.params;
    try {
        const pool = await sql.connect(req.dbConfig);
        await pool.request()
            .input('CustomerID', sql.Int, customerId)
            .query('EXEC DeleteCustomer @CustomerID');
        res.json({ message: 'Customer deleted successfully' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});


// Middleware to check admin role
function checkAdmin(req, res, next) {
    if (!req.session || req.session.role !== 'admin') {
        return res.status(403).json({ error: 'Unauthorized' });
    }
    next();
}

// GET /api/employees - Get all employees
router.get('/', checkAdmin, async (req, res) => {
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request().query('EXEC GetAllEmployees');
        res.json(result.recordset);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// GET /api/employees/:empId - Get employee by ID
router.get('/:empId', checkAdmin, async (req, res) => {
    const { empId } = req.params;
    try {
        const pool = await sql.connect(req.dbConfig);
        const result = await pool.request()
            .input('EmployeeID', sql.Int, empId)
            .query('EXEC GetEmployeeByID @EmployeeID');
        res.json(result.recordset[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/employees/add - Add new employee
router.post('/add', checkAdmin, async (req, res) => {
    const { Name, Email, Role } = req.body;
    try {
        const pool = await sql.connect(req.dbConfig);
        await pool.request()
            .input('Name', sql.NVarChar, Name)
            .input('Email', sql.NVarChar, Email)
            .input('Role', sql.NVarChar, Role)
            .query('EXEC AddEmployee @Name, @Email, @Role');
        res.json({ message: 'Employee added successfully' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/employees/edit/:empId - Edit employee
router.post('/edit/:empId', checkAdmin, async (req, res) => {
    const { empId } = req.params;
    const { Name, Email, Role } = req.body;
    try {
        const pool = await sql.connect(req.dbConfig);
        await pool.request()
            .input('EmployeeID', sql.Int, empId)
            .input('Name', sql.NVarChar, Name)
            .input('Email', sql.NVarChar, Email)
            .input('Role', sql.NVarChar, Role)
            .query('EXEC UpdateEmployee @EmployeeID, @Name, @Email, @Role');
        res.json({ message: 'Employee updated successfully' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// DELETE /api/employees/delete/:empId - Delete employee
router.delete('/delete/:empId', checkAdmin, async (req, res) => {
    const { empId } = req.params;
    try {
        const pool = await sql.connect(req.dbConfig);
        await pool.request()
            .input('EmployeeID', sql.Int, empId)
            .query('EXEC DeleteEmployee @EmployeeID');
        res.json({ message: 'Employee deleted successfully' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

module.exports = router;
