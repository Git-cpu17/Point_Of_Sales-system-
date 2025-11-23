# Azure Deployment Checklist - Tonight

Use this checklist to deploy FreshMart POS to Azure App Service tonight.

## ✅ Pre-Deployment (Already Done)

- [x] Created `web.config` for Azure App Service
- [x] Created `.deployment` and `deploy.sh` files
- [x] Updated `package.json` with proper scripts
- [x] Verified `server.js` uses `process.env.PORT`
- [x] Verified `db.js` configured for Azure SQL
- [x] All EJS templates exist in `/views/`
- [x] Static assets exist in `/static/`
- [x] Created comprehensive deployment documentation

## 📋 What You Need Before Starting

1. **Azure SQL Database** credentials:
   - Server name (e.g., `yourserver.database.windows.net`)
   - Database name
   - Username
   - Password

2. **Azure Subscription** - Active and ready to use

3. **Git** - Repository ready to push

## 🚀 Deployment Steps (30 minutes)

### Step 1: Create Azure App Service (5 min)

**Option A: Azure Portal (Easier)**
1. Go to https://portal.azure.com
2. Click "Create a resource" → "Web App"
3. Fill in:
   - Name: `freshmart-pos` (or your preferred name)
   - Runtime: **Node 18 LTS**
   - Region: Same as your database
   - Plan: **B1 Basic** (cheapest non-free option)
4. Click "Review + Create" → "Create"

**Option B: Azure CLI**
```bash
az login
az webapp up --name freshmart-pos --runtime "NODE:18-lts" --sku B1
```

### Step 2: Configure Environment Variables (5 min)

In Azure Portal → Your App Service → Configuration → Application settings:

Add these settings (click "+ New application setting" for each):

```
DB_USER=<your-azure-sql-username>
DB_PASSWORD=<your-azure-sql-password>
DB_SERVER=<your-server>.database.windows.net
DB_NAME=<your-database-name>
DB_ENCRYPT=true
DB_TRUST_CERT=false
SESSION_SECRET=<generate-random-32-char-string>
NODE_ENV=production
```

**IMPORTANT**: Click **Save** at the top!

### Step 3: Configure Azure SQL Firewall (2 min)

Azure Portal → Your SQL Server → Networking:
- Enable "Allow Azure services and resources to access this server"
- Click **Save**

### Step 4: Deploy Application (10 min)

**Easiest Method - Azure CLI**:
```bash
# From your project directory
az webapp up \
  --name freshmart-pos \
  --resource-group <your-resource-group> \
  --runtime "NODE:18-lts"
```

**Alternative - Git Deployment**:
```bash
# Get deployment URL
az webapp deployment source config-local-git --name freshmart-pos

# Add remote and push
git remote add azure <deployment-url>
git add .
git commit -m "Initial Azure deployment"
git push azure main:master
```

### Step 5: Verify Deployment (5 min)

1. Check deployment logs:
   ```bash
   az webapp log tail --name freshmart-pos
   ```

2. Open your app:
   ```
   https://freshmart-pos.azurewebsites.net
   ```

3. Test login with a database user

4. Verify pages load correctly:
   - Home page (/)
   - Login (/login)
   - Register (/register)
   - Admin dashboard (/admin) - if you have admin creds

### Step 6: Enable Production Features (3 min)

```bash
# Enable HTTPS only
az webapp update --name freshmart-pos --https-only true

# Enable Always On (prevents sleeping)
az webapp config set --name freshmart-pos --always-on true

# Enable detailed logging
az webapp log config \
  --name freshmart-pos \
  --application-logging filesystem \
  --web-server-logging filesystem
```

## 🔍 Troubleshooting

### If app won't start:
1. Check logs: `az webapp log tail --name freshmart-pos`
2. Verify all environment variables are set correctly
3. Verify SQL firewall allows Azure services

### If database connection fails:
1. Verify `DB_ENCRYPT=true` is set
2. Check server name ends with `.database.windows.net`
3. Test connection from Azure SQL query editor
4. Check firewall rules

### If you get 404 errors:
1. Verify `web.config` exists in repository
2. Check deployment logs for errors
3. Verify `server.js` is in root directory

## 📞 Quick Commands Reference

```bash
# View logs
az webapp log tail --name freshmart-pos

# Restart app
az webapp restart --name freshmart-pos

# Get app URL
az webapp show --name freshmart-pos --query defaultHostName

# SSH into app (for debugging)
az webapp ssh --name freshmart-pos

# Re-deploy
git push azure main:master
```

## ✨ Success Criteria

Your deployment is successful when:
- [x] App opens at `https://your-app-name.azurewebsites.net`
- [x] Home page displays products from database
- [x] Login works with database credentials
- [x] No console errors in browser
- [x] Images and CSS load correctly

## 📝 Notes

- **Cost**: B1 App Service = ~$13/month
- **Always On** required for production (prevents cold starts)
- **HTTPS** automatically provided by Azure
- **Sessions** are in-memory (will reset on restart)
- **Backups** - Azure SQL has automatic backups

## 🚨 Known Issues to Address Later

1. **CRITICAL**: Passwords are stored in plaintext - need to add bcrypt hashing
2. Sessions are in-memory - consider Azure Redis Cache for production
3. No input validation - add express-validator
4. No rate limiting on login endpoint

---

## Ready? Let's Deploy! 🎯

1. Open Azure Portal
2. Have your database credentials ready
3. Follow steps 1-6 above
4. Should be live in 30 minutes!

For detailed instructions, see `AZURE_DEPLOYMENT.md`
