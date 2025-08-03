# 🚀 Clinic Queue - Deployment Guide

This guide walks you through deploying the Clinic Queue system to production.

## 📋 Prerequisites

- [ ] Python 3.8+ 
- [ ] Twilio account with WhatsApp Business API
- [ ] Redis instance (for production)
- [ ] PostgreSQL database (recommended for production)
- [ ] Domain name and SSL certificate

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   WhatsApp      │    │   FastAPI        │    │   PostgreSQL    │
│   Users         │───▶│   Main App       │───▶│   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          
                              ▼                          
                       ┌──────────────────┐              
                       │   Redis Queue    │              
                       │   & Cache        │              
                       └──────────────────┘              
                              │                          
                              ▼                          
                       ┌──────────────────┐              
                       │   WhatsApp       │              
                       │   Worker         │              
                       └──────────────────┘              
```

## 🌐 Production Deployment Options

### Option 1: Railway (Recommended)

Railway provides easy deployment with built-in PostgreSQL and Redis.

1. **Prepare your code:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **Create Railway project:**
   ```bash
   # Install Railway CLI
   npm install -g @railway/cli
   
   # Login and deploy
   railway login
   railway init
   railway up
   ```

3. **Add services:**
   ```bash
   # Add PostgreSQL
   railway add postgresql
   
   # Add Redis
   railway add redis
   ```

4. **Set environment variables:**
   ```bash
   railway variables set ADMIN_PASS=your_secure_password
   railway variables set TWILIO_ACCOUNT_SID=your_account_sid
   railway variables set TWILIO_AUTH_TOKEN=your_auth_token
   railway variables set TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   ```

### Option 2: Render

1. **Connect your GitHub repo** to Render
2. **Create a Web Service** with:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. **Add PostgreSQL** and **Redis** services
4. **Configure environment variables**

### Option 3: Heroku

1. **Create Heroku app:**
   ```bash
   heroku create your-clinic-queue
   ```

2. **Add add-ons:**
   ```bash
   heroku addons:create heroku-postgresql:hobby-dev
   heroku addons:create heroku-redis:hobby-dev
   ```

3. **Set environment variables:**
   ```bash
   heroku config:set ADMIN_PASS=your_secure_password
   heroku config:set TWILIO_ACCOUNT_SID=your_account_sid
   # ... etc
   ```

4. **Deploy:**
   ```bash
   git push heroku main
   ```

## 🔧 Environment Configuration

### Required Environment Variables

```bash
# Essential
ADMIN_PASS=secure_password_here
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://user:pass@host:port

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Optional
CLINIC_NAME="Your Clinic Name"
CLINIC_ADDRESS="123 Health St, City"
```

### Database Setup

**For PostgreSQL:**
```bash
# The app will automatically create tables on startup
# No manual migration needed
```

**For SQLite (development only):**
```bash
# Uses queue.db file by default
# Good for testing but not recommended for production
```

## 📱 Twilio WhatsApp Setup

### 1. WhatsApp Business API Setup

1. **Go to Twilio Console:**
   - Visit: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn

2. **Join WhatsApp Sandbox:**
   - Follow instructions to connect your WhatsApp number
   - Note your sandbox number (e.g., +14155238886)

3. **Configure Webhooks:**
   - Webhook URL: `https://your-domain.com/webhooks/whatsapp`
   - Method: POST

### 2. Production WhatsApp Business

For production use:

1. **Apply for WhatsApp Business API** through Twilio
2. **Business Verification** required
3. **Message Templates** must be pre-approved
4. **Higher rate limits** and better features

## 🔄 Worker Process Setup

The WhatsApp worker handles sending notifications. You need to run it separately:

### Development:
```bash
python whatsapp_worker.py
```

### Production (Railway):
```bash
# Add worker service to railway.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python whatsapp_worker.py"
```

### Production (Heroku):
```bash
# Add to Procfile
worker: python whatsapp_worker.py
```

Then scale the worker:
```bash
heroku ps:scale worker=1
```

## 🔒 Security Considerations

### 1. Environment Variables
- **Never commit** `.env` files to git
- Use **strong passwords** for admin access
- **Rotate credentials** regularly

### 2. Network Security
- Use **HTTPS only** in production
- Consider **rate limiting** at load balancer level
- Implement **firewall rules** if needed

### 3. Data Privacy
- **Hash sensitive data** where possible
- **Limit data retention** (auto-delete old tickets)
- **Comply with HIPAA** if handling medical data

## 📊 Monitoring & Logging

### Application Monitoring
```python
# Add to your production environment
LOG_LEVEL=info
ENABLE_METRICS=true
```

### Redis Monitoring
Monitor queue sizes:
```bash
redis-cli llen whatsapp_notifications
redis-cli llen whatsapp_logs
```

### Database Monitoring
Check active tickets:
```sql
SELECT status, COUNT(*) FROM tickets GROUP BY status;
```

## 🔄 Backup & Recovery

### Database Backups
```bash
# PostgreSQL backup
pg_dump $DATABASE_URL > backup.sql

# Restore
psql $DATABASE_URL < backup.sql
```

### Redis Backups
```bash
# Redis backup (if persistence enabled)
redis-cli BGSAVE
```

## 📈 Scaling Considerations

### Horizontal Scaling
- **Multiple app instances** behind load balancer
- **Shared Redis** for session/cache storage
- **Separate worker instances** for notifications

### Performance Optimization
- **Connection pooling** for database
- **Redis caching** for frequently accessed data
- **CDN** for static assets (admin dashboard)

## 🛠️ Maintenance

### Regular Tasks
- [ ] Monitor queue performance
- [ ] Check notification delivery rates  
- [ ] Review and archive old tickets
- [ ] Update dependencies
- [ ] Backup database

### Health Checks
Add these endpoints to monitor:
- `/health` - Basic health check
- `/admin/metrics` - Performance metrics
- Redis queue sizes
- Database connection status

## 🆘 Troubleshooting

### Common Issues

**WhatsApp not working:**
- Check Twilio webhook URLs
- Verify credentials in environment
- Check worker process is running

**Database errors:**
- Verify DATABASE_URL format
- Check connection limits
- Ensure database exists

**High queue sizes:**
- Scale worker processes
- Check Redis memory limits
- Monitor notification delivery

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=debug
export DEBUG=true
```

## 📞 Support

Need help with deployment?

- **Documentation:** Check README.md and code comments
- **Issues:** Create GitHub issue with deployment details
- **Community:** Share your deployment experience

---

**🎉 Congratulations!** Your clinic queue is now running in production!

Don't forget to:
- Test the full patient flow
- Train your staff on the admin dashboard  
- Share WhatsApp number with patients
- Monitor performance and user feedback