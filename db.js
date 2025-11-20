// db.js
const sql = require('mssql');
require('dotenv').config();

const config = {
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  server: process.env.DB_SERVER,
  database: process.env.DB_NAME,
  options: {
    encrypt: process.env.DB_ENCRYPT === 'true',
    trustServerCertificate: process.env.DB_TRUST_CERT === 'true' // optional
  },
  pool: { max: 10, min: 0, idleTimeoutMillis: 30000 }
};

async function getConnection() {
  // global connection pool reused by mssql
  if (!global.connectionPool) {
    global.connectionPool = await sql.connect(config);
  }
  return global.connectionPool;
}

module.exports = { sql, getConnection };
