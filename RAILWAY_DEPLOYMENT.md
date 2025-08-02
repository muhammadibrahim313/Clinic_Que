# 🚂 Railway Deployment Guide for Clinic Queue

Deploy your clinic queue system to Railway in minutes with PostgreSQL and Redis!

## 🚀 Quick Deploy (One-Click)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template)

## 📋 Manual Deployment Steps

### Step 1: Prepare Repository

1. **Push to GitHub** (if not already):
   ```bash
   git add .
   git commit -m "Prepare for Railway deployment"
   git push origin main
   ```

### Step 2: Create Railway Project

1. **Go to [railway.app](https://railway.app)**
2. **Sign in** with GitHub
3. **New Project** → **Deploy from GitHub repo**
4. **Select** your `Clinic_Que` repository
5. **Deploy** - Railway will automatically detect Python and start building

### Step 3: Add Database Services

1. **In Railway Dashboard** → **Add Service**
2. **Add PostgreSQL**:
   - Click **+ New**
   - Select **Database** → **PostgreSQL**
   - Railway auto-generates `DATABASE_URL`
3. **Add Redis** (optional but recommended):
   - Click **+ New** 
   - Select **Database** → **Redis**
   - Railway auto-generates `REDIS_URL`

### Step 4: Configure Environment Variables

**In Railway Dashboard** → **Your App** → **Variables**, add:

```
ADMIN_PASS=your_secure_password_here
```

**Note**: `DATABASE_URL`, `REDIS_URL`, and `PORT` are automatically set by Railway.

### Step 5: Deploy and Test

1. **Railway auto-deploys** when you push to GitHub
2. **Your app URL**: `https://your-app-name.railway.app`
3. **Test endpoints**:
   - Health: `https://your-app.railway.app/health`
   - Admin: `https://your-app.railway.app/static/admin.html`
   - Kiosk: `https://your-app.railway.app/kiosk`

## 🧪 Testing Your Deployment

### Health Check
```bash
curl https://your-app.railway.app/health
```
Should return:
```json
{
  "status": "healthy",
  "database": "connected", 
  "redis": "connected",
  "clinic_name": "Clinic Queue"
}
```

### Admin Dashboard
1. **Open**: `https://your-app.railway.app/static/admin.html`
2. **Login** with your `ADMIN_PASS`
3. **Create test ticket** via kiosk
4. **Verify real-time updates** working

### WhatsApp Integration
1. **Update Twilio Webhook**: `https://your-app.railway.app/webhooks/whatsapp`
2. **Test WhatsApp commands**: `JOIN`, `STATUS`, `LEAVE`

## 📊 Railway Features You Get

### ✅ **Automatic Scaling**
- Scales based on traffic
- Zero downtime deployments
- Global CDN

### ✅ **Monitoring & Logs**
- Real-time application logs
- Performance metrics
- Error tracking

### ✅ **Database Management**
- Automatic PostgreSQL backups
- Redis persistence
- Database analytics

### ✅ **Custom Domain**
- Add your own domain
- Automatic SSL certificates
- Professional URLs

## 🔧 Development Workflow

### Local Development
```bash
# Use SQLite for local development
python -m uvicorn main:app --reload

# Test Railway version locally
DATABASE_URL=postgresql://localhost/test python -m uvicorn main_railway:app --reload
```

### Deploy Updates
```bash
git add .
git commit -m "Update clinic queue features"
git push origin main
# Railway automatically deploys!
```

## 🛠️ Environment Variables Reference

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection | ✅ | Auto-set by Railway |
| `REDIS_URL` | Redis connection | ⚠️ | Optional (enables caching) |
| `ADMIN_PASS` | Admin dashboard password | ✅ | Must set in Railway |
| `PORT` | Application port | ✅ | Auto-set by Railway |
| `TWILIO_ACCOUNT_SID` | Twilio credentials | ⚠️ | For SMS/WhatsApp |
| `TWILIO_AUTH_TOKEN` | Twilio credentials | ⚠️ | For SMS/WhatsApp |

## 🎯 Production Checklist

### ✅ **Security**
- [ ] Set strong `ADMIN_PASS`
- [ ] Configure CORS for your domain
- [ ] Set up proper Twilio webhook validation

### ✅ **Performance**
- [ ] Redis service added and connected
- [ ] Database connection pooling enabled
- [ ] Monitoring and alerts configured

### ✅ **Features**
- [ ] Admin dashboard accessible
- [ ] Kiosk functionality working
- [ ] WhatsApp integration tested
- [ ] Real-time updates functioning

## 🚨 Troubleshooting

### App Not Starting
```bash
# Check Railway logs
railway logs

# Common issues:
# 1. Missing DATABASE_URL - add PostgreSQL service
# 2. Missing ADMIN_PASS - add in Variables
# 3. Import errors - check requirements.txt
```

### Database Connection Issues
```bash
# Check if PostgreSQL is connected
railway shell
# Inside shell:
echo $DATABASE_URL
```

### Redis Not Working
- **Symptoms**: No real-time updates, slower performance
- **Solution**: Add Redis service in Railway dashboard
- **Note**: App works without Redis (falls back gracefully)

## 💰 Cost Estimate

### **Railway Hobby Plan** (Great for clinics):
- **App hosting**: $5/month
- **PostgreSQL**: $5/month  
- **Redis**: $3/month
- **Total**: ~$13/month for unlimited patients!

### **Railway Pro Plan** (Large hospitals):
- **Unlimited apps**: $20/month
- **Better performance & support**
- **Priority scaling**

## 🎉 Success!

Your clinic queue is now **globally deployed** with:
- ✅ **PostgreSQL database** - unlimited patients
- ✅ **Redis caching** - lightning-fast responses
- ✅ **Auto-scaling** - handles traffic spikes
- ✅ **SSL certificates** - secure connections
- ✅ **Global CDN** - fast worldwide access
- ✅ **Automatic backups** - never lose data

**Your patients can now join the queue from anywhere in the world!** 🌍

## 📞 Support

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Railway Discord**: [discord.gg/railway](https://discord.gg/railway)
- **PostgreSQL Issues**: Check Railway dashboard logs
- **Application Issues**: Monitor Railway app logs