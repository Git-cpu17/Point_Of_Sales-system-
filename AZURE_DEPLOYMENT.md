# Azure Deployment Guide - FreshMart POS System

This guide walks you through deploying the FreshMart Point of Sale system to Azure App Service.

## Prerequisites

1. **Azure Account** - Active Azure subscription
2. **Azure SQL Database** - Already set up with your schema
3. **Git** - Installed locally for deployment
4. **Node.js** - v16 or higher (for local testing)

## Pre-Deployment Checklist

- [x] `web.config` file created (for Azure App Service/IIS)
- [x] `.deployment` file created
- [x] `deploy.sh` script created
- [x] `package.json` has proper start script
- [x] `db.js` configured for Azure SQL
- [x] `server.js` uses `process.env.PORT`
- [x] All EJS templates exist in `/views/`
- [x] Static assets exist in `/static/`

## Step-by-Step Deployment

### 1. Create Azure App Service

```bash
# Login to Azure
az login

# Create a resource group (if you don't have one)
az group create --name FreshMartRG --location eastus

# Create an App Service Plan (B1 Basic tier or higher)
az appservice plan create \
  --name FreshMartPlan \
  --resource-group FreshMartRG \
  --sku B1 \
  --is-linux

# Create the Web App
az webapp create \
  --name freshmart-pos \
  --resource-group FreshMartRG \
  --plan FreshMartPlan \
  --runtime "NODE|18-lts"
```

**OR** use the Azure Portal:
1. Go to https://portal.azure.com
2. Click "Create a resource" > "Web App"
3. Fill in:
   - **Name**: `freshmart-pos` (must be globally unique)
   - **Runtime**: Node 18 LTS
   - **Region**: Same as your database
   - **Pricing Plan**: B1 Basic or higher
4. Click "Review + Create"

### 2. Configure Environment Variables

In Azure Portal:
1. Go to your App Service
2. Navigate to **Configuration** > **Application settings**
3. Add the following settings:

| Name | Value | Example |
|------|-------|---------|
| `DB_USER` | Your Azure SQL username | `adminuser` |
| `DB_PASSWORD` | Your Azure SQL password | `YourPassword123!` |
| `DB_SERVER` | Your Azure SQL server | `yourserver.database.windows.net` |
| `DB_NAME` | Database name | `FreshMartDB` |
| `DB_ENCRYPT` | Must be `true` for Azure | `true` |
| `DB_TRUST_CERT` | Set to `false` for production | `false` |
| `SESSION_SECRET` | Random secret key | `your-random-32-char-secret-key` |
| `PORT` | (Auto-set by Azure) | `8080` |
| `NODE_ENV` | Environment | `production` |

**Important**: Click **Save** after adding all settings!

### 3. Configure Azure SQL Firewall

Your App Service needs access to Azure SQL:

**Option A: Allow Azure Services** (Easiest)
1. Go to your Azure SQL Server in the portal
2. Navigate to **Security** > **Networking**
3. Under "Firewall rules", enable "Allow Azure services and resources to access this server"
4. Click **Save**

**Option B: Specific Outbound IP** (More secure)
1. Get your App Service outbound IPs:
   ```bash
   az webapp show --name freshmart-pos --resource-group FreshMartRG --query outboundIpAddresses
   ```
2. Add each IP to your SQL Server firewall rules

### 4. Deploy via Git

#### Option A: Local Git Deployment

```bash
# 1. Get your deployment credentials
az webapp deployment user set --user-name <your-username> --password <your-password>

# 2. Get your Git URL
az webapp deployment source config-local-git \
  --name freshmart-pos \
  --resource-group FreshMartRG

# 3. Add Azure as a remote
git remote add azure <git-url-from-step-2>

# 4. Commit your changes
git add .
git commit -m "Initial Azure deployment"

# 5. Push to Azure
git push azure main:master
```

#### Option B: GitHub Actions (Recommended)

1. In Azure Portal, go to your App Service
2. Navigate to **Deployment Center**
3. Select **GitHub** as source
4. Authenticate and select your repository
5. Azure will auto-create a GitHub Actions workflow
6. Click **Save**

Every push to `main` will now auto-deploy!

#### Option C: Azure CLI Direct Deployment

```bash
# Deploy from local directory
az webapp up \
  --name freshmart-pos \
  --resource-group FreshMartRG \
  --runtime "NODE:18-lts"
```

### 5. Verify Deployment

1. **Check deployment logs**:
   ```bash
   az webapp log tail --name freshmart-pos --resource-group FreshMartRG
   ```

2. **Browse to your app**:
   ```
   https://freshmart-pos.azurewebsites.net
   ```

3. **Test login** with your database credentials

### 6. Enable Application Logging

```bash
# Enable detailed logging
az webapp log config \
  --name freshmart-pos \
  --resource-group FreshMartRG \
  --application-logging filesystem \
  --detailed-error-messages true \
  --failed-request-tracing true \
  --web-server-logging filesystem
```

## Post-Deployment Configuration

### Enable HTTPS Only

```bash
az webapp update \
  --name freshmart-pos \
  --resource-group FreshMartRG \
  --https-only true
```

### Set Up Custom Domain (Optional)

1. Go to **Custom domains** in your App Service
2. Click **Add custom domain**
3. Follow the verification steps
4. Add SSL certificate via **TLS/SSL settings**

### Configure CORS (If needed for APIs)

In **API** > **CORS**, add allowed origins or use `*` for testing.

## Troubleshooting

### Application Won't Start

1. Check Application Settings are correct
2. Verify DB connection string
3. Check logs:
   ```bash
   az webapp log tail --name freshmart-pos --resource-group FreshMartRG
   ```

### Database Connection Errors

1. Verify firewall rules allow App Service IPs
2. Check `DB_ENCRYPT=true` is set
3. Verify server name includes `.database.windows.net`
4. Test connection from Azure Portal's SQL query editor

### 404 Errors

1. Verify `web.config` exists in repository root
2. Check that `server.js` is the entry point
3. Verify static files are in `/static/` directory

### Session Issues

1. Verify `SESSION_SECRET` is set in Application Settings
2. Note: In-memory sessions will reset when the app restarts
3. For production, consider using Azure Redis Cache for sessions

## Performance Optimization

### Enable Always On

```bash
az webapp config set \
  --name freshmart-pos \
  --resource-group FreshMartRG \
  --always-on true
```

This prevents the app from sleeping after 20 minutes of inactivity.

### Scale Up/Out

**Scale Up** (Bigger server):
```bash
az appservice plan update \
  --name FreshMartPlan \
  --resource-group FreshMartRG \
  --sku P1V2
```

**Scale Out** (More instances):
```bash
az appservice plan update \
  --name FreshMartPlan \
  --resource-group FreshMartRG \
  --number-of-workers 2
```

## Monitoring

### Application Insights (Recommended)

1. Go to your App Service
2. Navigate to **Application Insights**
3. Click **Turn on Application Insights**
4. Create new resource or use existing
5. Click **Apply**

This provides:
- Performance monitoring
- Error tracking
- Usage analytics
- Live metrics

### View Metrics

In Azure Portal > App Service > **Metrics**:
- CPU Percentage
- Memory Percentage
- Response Time
- HTTP Server Errors

## Security Best Practices

1. **Never commit `.env` file** - Already in `.gitignore`
2. **Use Azure Key Vault** for production secrets (advanced)
3. **Enable HTTPS only** (see command above)
4. **Implement password hashing** (currently plaintext - CRITICAL security issue!)
5. **Restrict SQL firewall** to only App Service IPs
6. **Enable Azure AD authentication** for admin access (optional)

## Cost Management

Estimated monthly costs (as of 2024):
- **B1 App Service Plan**: ~$13/month
- **Azure SQL Basic (2GB)**: ~$5/month
- **Total**: ~$18/month

To reduce costs:
- Use **F1 Free tier** for testing (limited to 60 min/day CPU)
- Stop the app when not in use
- Use shared SQL pool

## Continuous Deployment Workflow

For ongoing development:

```bash
# 1. Make changes locally
# 2. Test locally
npm start

# 3. Commit and push
git add .
git commit -m "Your change description"
git push azure main:master

# 4. Monitor deployment
az webapp log tail --name freshmart-pos --resource-group FreshMartRG
```

## Backup Strategy

### Database Backups

Azure SQL automatically creates backups. To create manual backup:

```bash
az sql db export \
  --name FreshMartDB \
  --server yourserver \
  --resource-group FreshMartRG \
  --admin-user adminuser \
  --admin-password YourPassword123! \
  --storage-key-type StorageAccessKey \
  --storage-key <your-storage-key> \
  --storage-uri https://yourstorage.blob.core.windows.net/backups/freshmart.bacpac
```

### Application Backups

In Azure Portal > App Service > **Backups**, configure:
- Backup schedule
- Storage account
- Retention period

## Support Resources

- **Azure Documentation**: https://docs.microsoft.com/azure/app-service/
- **Node.js on Azure**: https://docs.microsoft.com/azure/app-service/quickstart-nodejs
- **Azure SQL**: https://docs.microsoft.com/azure/azure-sql/
- **Pricing Calculator**: https://azure.microsoft.com/pricing/calculator/

## Quick Reference Commands

```bash
# Restart app
az webapp restart --name freshmart-pos --resource-group FreshMartRG

# View logs
az webapp log tail --name freshmart-pos --resource-group FreshMartRG

# SSH into container (Linux App Service)
az webapp ssh --name freshmart-pos --resource-group FreshMartRG

# Get app URL
az webapp show --name freshmart-pos --resource-group FreshMartRG --query defaultHostName

# Delete everything (careful!)
az group delete --name FreshMartRG --yes
```

---

## Ready to Deploy?

Your application is now Azure-ready! Follow the steps above and you should have your FreshMart POS system running in Azure within 30 minutes.

**Recommended deployment path for tonight:**
1. Create App Service via Azure Portal (5 min)
2. Configure environment variables (5 min)
3. Enable Azure SQL firewall (2 min)
4. Deploy via `az webapp up` command (10 min)
5. Test and verify (5 min)

Good luck with your deployment! 🚀
