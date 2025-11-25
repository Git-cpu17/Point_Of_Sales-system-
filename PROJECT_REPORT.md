# FreshMart Point of Sale System - Project Report

## Project Overview
FreshMart is a  Point of Sale (POS) system designed for grocery store management.

---

## GitHub Usernames and names
 - Ben Bizman https://github.com/RealBenBizman
 - Lucas Pavlosky https://github.com/godvap
 - Yashwanth Muddam https://github.com/mrsaiduck
 - An Nguyen https://github.com/Git-cpu17

## 1. Data Management Capabilities

### 1.1 Product Management
**Operations:** Add, Modify, Delete, View

**Data Fields:**
- Product ID (Auto-generated)
- Name
- Description
- Price
- Quantity in Stock
- Department ID
- Barcode
- Sale Price
- On Sale Status (Boolean)
- Image URL
- Is Active (Boolean)

**User Roles with Access:** Administrator, Employee (view only)

**Key Features:**
- Mark products as on sale
- Set product availability status
- Upload product images
- Categorize by department
- Track inventory levels

---

### 1.2 Customer Data
**Operations:** Add, Modify, View

**Data Fields:**
- Customer ID (Auto-generated)
- Username (Cannot be changed after creation)
- Full Name
- Email Address
- Phone Number
- Password
- Member Since Date

**User Roles with Access:**
- Administrator (full CRUD)
- Customer (view and edit own data only)

**Key Features:**
- Self-registration
- Profile management
- Email uniqueness validation
- Password change with verification

---

### 1.3 Employee Management
**Operations:** Add, Modify, Deactivate, View

**Data Fields:**
- Employee ID (Auto-generated)
- Username
- Full Name
- Email
- Phone
- Password
- Department Assignment
- Is Active Status
- Hire Date

**User Roles with Access:** Administrator only

**Key Features:**
- Department assignment
- Active/inactive status management
- Role-based access control

---

### 1.4 Department Management
**Operations:** Add, Modify, View

**Data Fields:**
- Department ID (Auto-generated)
- Department Name
- Description

**User Roles with Access:** Administrator

**Key Features:**
- Product categorization
- Department-specific sales

---

### 1.5 Sales Transactions
**Operations:** Create, View

**Data Fields:**
- Transaction ID (Auto-generated)
- Transaction Date
- Total Amount
- Order Status (Processing, Shipped, Delivered)
- Customer ID or Employee ID
- Order Discount
- Payment Method
- Transaction Details (line items)

**User Roles with Access:**
- Administrator (full view)
- Employee (create and view)
- Customer (view own transactions)

**Key Features:**
- Multi-item transactions
- Discount application
- Order status tracking
- Transaction history

---

### 1.6 Shopping Bag/Cart
**Operations:** Add, Modify, Delete, View

**Data Fields:**
- Bag ID (Auto-generated)
- Product ID
- Quantity
- Customer ID or Employee ID

**User Roles with Access:** Customer, Employee

**Key Features:**
- Dual ownership (customer or employee)
- Real-time quantity updates
- Persistent cart storage

---

### 1.7 Shopping Lists
**Operations:** Add, Modify, Delete, View

**Data Fields:**
- List ID (Auto-generated)
- List Name
- Customer ID
- Shopping List Items (Product ID, Quantity)

**User Roles with Access:** Customer only

**Key Features:**
- Multiple lists per customer
- Reusable shopping lists
- Quick add-to-cart from lists

---

### 1.8 Holiday/Seasonal Sales
**Operations:** Add, Modify, Deactivate, View

**Data Fields:**
- Sale ID (Auto-generated)
- Sale Name (e.g., "Uma Month")
- Start Date
- End Date
- Discount Percentage
- Department ID (optional - for department-specific sales)
- Is Active Status

**User Roles with Access:** Administrator

**Key Features:**
- Time-based automatic activation
- Department-specific or store-wide sales
- Percentage-based discounts
- Sale name display on website

---

### 1.9 Inventory Management
**Operations:** View, Modify

**Data Fields:**
- Inventory ID (Auto-generated)
- Product ID
- Quantity Available
- Reorder Level
- Last Restock Date

**User Roles with Access:** Administrator, Employee

**Key Features:**
- Low stock alerts (Reorder Alerts)
- Inventory tracking
- Restock date logging

---

### 1.10 Reorder Alerts
**Operations:** View, Auto-generated

**Data Fields:**
- Alert ID (Auto-generated)
- Product ID
- Alert Date
- Current Stock Level
- Reorder Level
- Status (Pending, Resolved)

**User Roles with Access:** Administrator, Employee

**Key Features:**
- Automatic generation when stock ≤ reorder level
- Alert management

---

## 2. User Roles and Permissions

### 2.1 Administrator
**Access Level:** Full system access

**Capabilities:**
- **Product Management**
  - Add, edit, delete products
  - Set prices and sale status
  - Upload product images
  - Manage inventory levels

- **User Management**
  - Create, modify, deactivate employees
  - View customer accounts
  - Manage administrator accounts

- **Department Management**
  - Create and modify departments
  - Assign employees to departments

- **Sales & Promotions**
  - Create and manage holiday/seasonal sales
  - Set discount percentages
  - Configure sale dates and departments

- **Reporting & Analytics**
  - View all sales reports
  - Access customer analytics
  - Review employee performance
  - Generate inventory reports
  - Track revenue and product performance

- **Order Management**
  - View all customer orders
  - Track order statuses
  - Process transactions

**Dashboard Features:**
- Sales overview
- Inventory alerts
- Customer statistics
- Employee management
- Product catalog management

---

### 2.2 Employee
**Access Level:** Operational access

**Capabilities:**
- **Product Information**
  - View product catalog
  - Check inventory levels
  - View product prices and availability

- **Transaction Processing**
  - Create sales transactions
  - Process customer orders
  - Apply discounts

- **Shopping Bag**
  - Manage shopping cart for in-store purchases
  - Add/remove items
  - Calculate totals

- **Inventory Viewing**
  - View stock levels
  - Check reorder alerts
  - Monitor low inventory

- **Department Access**
  - View department information
  - Access department-specific data

**Dashboard Features:**
- Transaction processing interface
- Product search and lookup
- Inventory status
- Department information

**Restrictions:**
- Cannot modify product information
- Cannot create or manage users
- Cannot access financial reports
- Cannot configure sales/promotions

---

### 2.3 Customer
**Access Level:** Self-service shopping

**Capabilities:**
- **Account Management**
  - Register new account
  - Update personal information (name, email, phone)
  - Change password

- **Shopping**
  - Browse product catalog
  - Filter by department
  - Search products
  - View product details and pricing
  - See sale prices and discounts

- **Shopping Cart**
  - Add items to cart
  - Update quantities
  - Remove items
  - View cart total

- **Shopping Lists**
  - Create multiple shopping lists
  - Add/remove items from lists
  - Name and organize lists
  - Quick add-to-cart from lists

- **Order Management**
  - Place orders
  - View order history
  - Track order status
  - View transaction details

- **Account Dashboard**
  - View total savings
  - See order statistics
  - Access recent orders
  - View loyalty points (displayed)

**Dashboard Features:**
- Personal shopping overview
- Recent orders
- Savings tracker
- Shopping lists
- Account settings

**Restrictions:**
- Cannot view other customers' data
- Cannot access administrative functions
- Cannot modify product information
- Cannot view business reports
- Cannot create sales/promotions

---

## 3. Semantic Constraints as Triggers

### 3.1 Seasonal / Holiday Sales
 - The owner of the store would like holiday sales to be implemented automatically in their system. We have added a table for holiday and seasonal sales into the database, that can set a sale, its discount amount, and the date range it is in effect for. The system will check if there is a sale going on, and apply that sale automatically with a trigger.

### 3.2 Low stock reorder
- The owner of the store would like to order new stock based on current stock with custom limits set by the admins. The admins can set a low stock reorder point for each product, and when the product's stock is reduced below that amount, either manually or by a customer buying it, it will ping the admins and employees that it is time to reorder that product.

---

## 4. Queries and Reports Available

The FreshMart POS system provides comprehensive reporting and analytics capabilities through multiple specialized reports. These reports support business intelligence, inventory management, and customer relationship management.

### 4.1 Product Report

**Access:** Administrator, Employee

**Route:** `/product_report`

**Purpose:** Comprehensive product performance analysis and inventory tracking

**Data Provided:**
- Product ID and Name
- Department categorization
- Pricing information (Regular Price, Sale Price)
- Inventory levels (Quantity Available)
- Stock status (In Stock, Low Stock, Out of Stock)
- Reorder levels and last restock dates
- Sale status indicator (OnSale: Yes/No)
- Total revenue per product
- Number of sales transactions

**Filter Capabilities:**
- Department selection (single or multiple)
- Product name search (partial matching)
- Stock status filtering (In Stock, Low Stock, Out of Stock, All)
- Sale status (On Sale, Not On Sale, All)
- Price range (minimum and maximum)
- Quantity range filtering
- Restock date range
- Sortable by any column (ascending/descending)

**Key Queries:**
```sql
-- Product performance with inventory and sales data
SELECT p.ProductID, p.Name, d.Name AS Department, p.Price, p.SalePrice,
       i.QuantityAvailable, i.ReorderLevel, i.LastRestockDate,
       CASE WHEN p.OnSale = 1 THEN 'Yes' ELSE 'No' END AS OnSale,
       ISNULL(SUM(td.Quantity * td.Price), 0) AS TotalRevenue,
       COUNT(td.TransactionID) AS NumberOfSales
FROM Product p
LEFT JOIN Department d ON p.DepartmentID = d.DepartmentID
LEFT JOIN Inventory i ON p.ProductID = i.ProductID
LEFT JOIN Transaction_Details td ON td.ProductID = p.ProductID
GROUP BY p.ProductID, p.Name, d.Name, p.Price, p.SalePrice,
         i.QuantityAvailable, i.ReorderLevel, i.LastRestockDate, p.OnSale
```

**Business Use Cases:**
- Identify best-selling products
- Monitor inventory levels
- Track products requiring reorder
- Analyze pricing and sale effectiveness
- Evaluate product performance by department

---

### 4.2 Employee Report

**Access:** Administrator only

**Route:** `/employee_report`

**Purpose:** Employee performance tracking and productivity analysis

**Data Provided:**
- Employee ID and Name
- Department assignment
- Job Title
- Hire Date and tenure calculation
- Total revenue generated
- Number of sales transactions
- Average sale value per employee
- Days since hire (tenure)

**Filter Capabilities:**
- Department filtering (single or multiple)
- Job title selection
- Employee name search
- Hire date range
- Revenue range (minimum and maximum)
- Number of sales range
- Average sale value filtering
- Sortable by any metric

**Key Queries:**
```sql
-- Employee performance with revenue metrics
SELECT e.EmployeeID, e.Name, d.Name AS DepartmentName, e.JobTitle, e.HireDate,
       COALESCE(SUM(td.Quantity * p.Price), 0) AS TotalRevenue,
       COUNT(td.TransactionID) AS NumberOfSales,
       COALESCE(SUM(td.Quantity * p.Price)/NULLIF(COUNT(td.TransactionID),0), 0) AS AverageSaleValue
FROM Employee e
LEFT JOIN Department d ON e.DepartmentID = d.DepartmentID
LEFT JOIN Transaction_Details td ON td.EmployeeID = e.EmployeeID
LEFT JOIN Product p ON p.ProductID = td.ProductID
WHERE e.IsActive = 1
GROUP BY e.EmployeeID, e.Name, d.Name, e.JobTitle, e.HireDate
```

**Calculated Metrics:**
- Average employee tenure across all employees
- Individual employee tenure (days since hire)
- Employee productivity (sales per employee)

**Business Use Cases:**
- Evaluate employee performance
- Identify top-performing staff
- Track departmental productivity
- Support HR decisions
- Calculate average tenure

---

### 4.3 Customer Report

**Access:** Administrator only

**Route:** `/customer_report`

**Purpose:** Customer behavior analysis and loyalty tracking

**Data Provided:**
- Customer ID, Name, and Email
- Total number of purchases
- Total amount spent
- Favorite product (most purchased item)
- Most purchased category/department
- Recent purchase date
- Largest single order value

**Filter Capabilities:**
- Customer name search
- Email search
- Purchase date range
- Total spent range (minimum and maximum)
- Total purchases range
- Sortable by any column

**Key Queries:**
```sql
-- Customer purchasing behavior and preferences
SELECT c.CustomerID, c.Name, c.Email,
       COUNT(DISTINCT st.TransactionID) AS TotalPurchases,
       COALESCE(SUM(st.TotalAmount), 0) AS TotalSpent,

       -- Favorite product (correlated subquery)
       COALESCE((
           SELECT TOP 1 p.Name
           FROM Transaction_Details td2
           JOIN Product p ON td2.ProductID = p.ProductID
           JOIN SalesTransaction st2 ON td2.TransactionID = st2.TransactionID
           WHERE st2.CustomerID = c.CustomerID
           GROUP BY p.ProductID, p.Name
           ORDER BY SUM(td2.Quantity) DESC
       ), 'N/A') AS FavoriteProduct,

       -- Most purchased category
       COALESCE((
           SELECT TOP 1 d.Name
           FROM Transaction_Details td2
           JOIN Product p ON td2.ProductID = p.ProductID
           JOIN Department d ON p.DepartmentID = d.DepartmentID
           JOIN SalesTransaction st2 ON td2.TransactionID = st2.TransactionID
           WHERE st2.CustomerID = c.CustomerID
           GROUP BY d.Name
           ORDER BY SUM(td2.Quantity) DESC
       ), 'N/A') AS MostPurchasedCategory
FROM Customer c
LEFT JOIN SalesTransaction st ON c.CustomerID = st.CustomerID
GROUP BY c.CustomerID, c.Name, c.Email
```

**Aggregate Metrics:**
- Overall largest single order across all customers
- Customer lifetime value
- Purchase frequency patterns

**Business Use Cases:**
- Identify high-value customers
- Understand customer preferences
- Target marketing campaigns
- Personalized product recommendations
- Customer retention strategies

---

### 4.4 Revenue Report

**Access:** Administrator only

**Route:** `/revenue_report`

**Purpose:** Financial analysis and transaction tracking

**Data Provided:**
- Transaction ID
- Transaction Date
- Customer Name
- Payment Method
- Order Status
- Total Amount
- Visual chart representation

**Filter Capabilities:**
- Date range (start and end date)
- Payment method filtering
- Order status filtering
- Department-based filtering
- Sortable by date or amount

**Key Queries:**
```sql
-- Revenue transactions with customer information
SELECT st.TransactionID, st.TransactionDate, c.Name AS CustomerName,
       st.PaymentMethod, st.OrderStatus, st.TotalAmount
FROM SalesTransaction st
LEFT JOIN Customer c ON st.CustomerID = c.CustomerID
ORDER BY st.TransactionDate DESC
```

**Additional Features:**
- Chart visualization endpoint (`/api/revenue_report_chart`)
- Revenue trends over time
- Payment method distribution
- Order status breakdown

**Business Use Cases:**
- Track daily/weekly/monthly revenue
- Analyze payment preferences
- Monitor order fulfillment
- Financial forecasting
- Revenue trend analysis

---

### 4.5 Receipts Report

**Access:** Administrator only

**Route:** `/receipts_report`

**Purpose:** Comprehensive transaction receipt analysis with line item summaries

**Data Provided:**
- Transaction ID
- Transaction Date
- Customer Name (or "Guest / In-store" for walk-in customers)
- Employee Name (who processed the transaction)
- Payment Method
- Order Status
- Order Discount applied
- Total Amount
- Number of distinct items purchased
- Total units sold

**Filter Capabilities:**
- Date range (start date and end date)
- Payment method filtering
- Order status filtering
- Employee filtering (specific employee who processed)

**Aggregate Metrics:**
- Total Revenue (sum of all transactions)
- Total Receipts count
- Average Receipt value

**Key Queries:**
```sql
-- Transaction receipts with customer, employee, and line item details
SELECT
    st.TransactionID,
    st.TransactionDate,
    COALESCE(c.Name, 'Guest / In-store') AS CustomerName,
    COALESCE(e.Name, 'N/A') AS EmployeeName,
    COALESCE(st.PaymentMethod, '') AS PaymentMethod,
    COALESCE(st.OrderStatus, '') AS OrderStatus,
    COALESCE(st.OrderDiscount, 0) AS OrderDiscount,
    COALESCE(st.TotalAmount, 0) AS TotalAmount,
    COUNT(DISTINCT td.ProductID) AS DistinctItems,
    COALESCE(SUM(td.Quantity), 0) AS TotalUnits
FROM SalesTransaction st
LEFT JOIN Customer c ON c.CustomerID = st.CustomerID
LEFT JOIN Employee e ON e.EmployeeID = (
    SELECT TOP 1 EmployeeID
    FROM Transaction_Details
    WHERE TransactionID = st.TransactionID
)
LEFT JOIN Transaction_Details td ON td.TransactionID = st.TransactionID
WHERE 1 = 1
[Dynamic filters applied]
GROUP BY st.TransactionID, st.TransactionDate, c.Name, e.Name,
         st.PaymentMethod, st.OrderStatus, st.OrderDiscount, st.TotalAmount
ORDER BY st.TransactionDate DESC
```

**Business Use Cases:**
- Detailed transaction audit trail
- Receipt verification and reconciliation
- Employee transaction tracking
- Payment method analysis
- Discount effectiveness monitoring
- Average transaction value tracking
- Daily sales reconciliation

**Unique Features:**
- Handles both customer and in-store (guest) transactions
- Links transactions to processing employees
- Summarizes line items per transaction
- Calculates total revenue and averages in real-time
- Supports both registered customers and walk-in sales

---

### 4.6 Inventory Report

**Access:** Administrator

**Route:** `/admin/inventory-report`

**Purpose:** Stock level monitoring and inventory management

**Data Provided:**
- Product inventory levels
- Department categorization
- Stock status indicators
- Reorder alerts

**Filter Capabilities:**
- Department filtering
- Price range filtering
- Stock status filtering

**Business Use Cases:**
- Monitor stock levels
- Identify reorder needs
- Prevent stockouts
- Optimize inventory costs

---

### 4.7 Dynamic Query Report

**Access:** Administrator, Employee

**Route:** `/reports/query`

**Purpose:** Flexible ad-hoc reporting with custom parameters

**Supported Query Types:**
1. **Product-based queries** - Sales by product
2. **Department-based queries** - Sales by department
3. **Employee-based queries** - Sales by employee
4. **Customer-based queries** - Sales by customer

**Filter Capabilities:**
- Date range selection
- Group by dimension (product, department, employee, customer)
- Department filtering
- Employee filtering
- Minimum units threshold
- Dynamic aggregation

**Key Query Structure:**
```sql
-- Flexible reporting based on grouping dimension
SELECT [GroupByColumn], SUM(td.Quantity) AS Units, SUM(td.Quantity * p.Price) AS Revenue
FROM Transaction_Details td
JOIN Product p ON td.ProductID = p.ProductID
[Additional joins based on grouping]
WHERE [Dynamic filters]
GROUP BY [GroupByColumn]
ORDER BY Units DESC
```

**Business Use Cases:**
- Custom analysis by multiple dimensions
- Flexible reporting for different stakeholders
- Ad-hoc business questions
- Comparative analysis

---

### 4.8 Product KPIs (Key Performance Indicators)

**Access:** Administrator

**Route:** `/api/product_kpis`

**Purpose:** Quick snapshot of critical product metrics

**Data Provided:**
- **Top 3 Most Sold Products** (by number of sales)
- **Bottom 3 Slow-Moving Products** (fewest sales with at least 1 sale)
- **Top 3 Low Stock Products** (quantity ≤ reorder level)

**Key Queries:**
```sql
-- Top selling products
SELECT TOP 3 p.Name, COUNT(td.TransactionID) AS NumberOfSales
FROM Product p
LEFT JOIN Transaction_Details td ON td.ProductID = p.ProductID
GROUP BY p.Name
ORDER BY NumberOfSales DESC

-- Low stock alerts
SELECT TOP 3 p.Name, i.QuantityAvailable, i.ReorderLevel
FROM Product p
JOIN Inventory i ON i.ProductID = p.ProductID
WHERE i.QuantityAvailable <= i.ReorderLevel
ORDER BY i.QuantityAvailable ASC
```

**Business Use Cases:**
- Dashboard widgets
- Quick inventory health check
- Immediate action alerts
- Executive summaries

---

### 4.9 Customer Dashboard Queries

**Access:** Customer (own data only)

**Purpose:** Personalized customer insights

**Data Provided:**
- Total savings this month
- Total orders this year
- Recent order history
- Order status tracking
- Shopping list management

**Key Queries:**
```sql
-- Customer savings calculation
SELECT SUM(OrderDiscount) FROM SalesTransaction WHERE CustomerID = ?

-- Customer order count
SELECT COUNT(*) FROM SalesTransaction WHERE CustomerID = ?

-- Recent orders with details
SELECT t.TransactionID, t.TransactionDate, t.TotalAmount, t.OrderStatus,
       SUM(td.Quantity) AS ItemCount
FROM SalesTransaction t
JOIN Transaction_Details td ON t.TransactionID = td.TransactionID
WHERE t.CustomerID = ?
GROUP BY t.TransactionID, t.TransactionDate, t.TotalAmount, t.OrderStatus
ORDER BY t.TransactionDate DESC
```

**Business Use Cases:**
- Customer self-service
- Order tracking
- Loyalty program insights
- Personal savings tracking

---

### 4.10 Real-Time Queries

**Purpose:** Live data updates for operational needs

**Available Real-Time Queries:**

1. **Shopping Bag Count**
   - Real-time cart item count per user
   - Updates on every cart modification

2. **Active Sales Check**
   - Current holiday/seasonal sales
   - Automatic discount application
   - Date range validation

3. **Inventory Availability**
   - Real-time stock checks during checkout
   - Prevent overselling

4. **Session User Info**
   - Current user role and permissions
   - Personalized navigation and features

---

### 4.11 Report Export and Visualization

**Current Capabilities:**
- HTML table rendering for all reports
- Chart visualization for revenue trends
- JSON API endpoints for data integration
- Sortable and filterable result sets

**Supported Aggregations:**
- SUM (revenue, quantities)
- COUNT (transactions, sales)
- AVG (average sale values)
- MAX/MIN (largest orders, price ranges)
- COALESCE (handle null values)
- GROUP BY (multiple dimensions)

**Recommended Future Enhancements:**
- PDF export functionality
- Excel/CSV downloads
- Advanced chart types (pie charts, bar graphs)
- Scheduled report generation
- Email report delivery

---

### 4.12 Query Performance Considerations

**Optimizations Implemented:**
- Indexed foreign keys (ProductID, CustomerID, EmployeeID, DepartmentID)
- LEFT JOIN for optional relationships
- COALESCE for null handling
- TOP N for limited result sets
- Parameterized queries to prevent SQL injection

**Complex Query Features:**
- Correlated subqueries for customer favorites
- Window functions for ranking (TOP 1)
- Aggregate functions with GROUP BY
- CASE statements for conditional logic
- Date formatting and conversion


