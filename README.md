# Clinic Queue by SMS/WhatsApp

This project implements a simple, privacy‑friendly virtual queue for free or pop‑up clinics.  Patients join the queue by texting `JOIN` to a dedicated number.  The system responds with a short ticket code (e.g., `Q7`), their position in line, and an estimated wait time.  Staff interact with a lightweight admin board to move tickets forward and send automated “you’re next” alerts.  An optional kiosk page allows people without phones to join the queue.

## Features

### 📱 **Enhanced WhatsApp Experience**
* **Rich messaging** with emojis, formatting, and visual progress indicators
* **Smart command recognition** - accepts natural language (join/register/book, status/position/eta, etc.)
* **Media support** - patients can send images, documents, and voice notes
* **Proactive notifications** - automatic alerts when you're next or position changes
* **Interactive onboarding** - friendly welcome messages and comprehensive help

### 🏥 **Queue Management** 
* **Multi-channel registration** – patients join via SMS, WhatsApp, or in-person kiosk
* **Real-time status tracking** – `waiting`, `next`, `in_room`, `done`, `no_show`, `urgent` states
* **Smart ETA calculation** – uses rolling average of service times with live updates
* **Priority handling** – urgent cases can be fast-tracked

### 👨‍⚕️ **Advanced Admin Dashboard**
* **Real-time analytics** – completion rates, wait times, no-show statistics
* **Interactive charts** – hourly distribution, status breakdown, channel analytics
* **Patient flow timeline** – live activity feed with privacy protection
* **Performance metrics** – queue length, throughput, patients per hour
* **Broadcast messaging** – send announcements to all active WhatsApp users

### 🔒 **Privacy & Security**
* **Anonymous tickets** – minimal data storage with privacy-first design
* **Secure admin access** – password-protected dashboard with session management
* **Rate limiting** – prevents abuse with intelligent throttling
* **Data retention** – configurable cleanup of old tickets

### ⚡ **Production Ready**
* **Scalable architecture** – Redis caching, database optimization, real-time updates
* **Background workers** – dedicated WhatsApp notification processing
* **Cloud deployment** – ready for Railway, Render, Heroku with full setup guides
* **Monitoring & health checks** – comprehensive logging and performance tracking

## 🚀 Quick Start

### 1. **Setup & Installation**
```bash
# Clone and setup
git clone <repository-url>
cd Clinic_Que
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. **WhatsApp Integration (Recommended)**
Run the interactive setup script:
```bash
python setup_twilio.py
```

Or manually create `.env` file:
```bash
cp .env.example .env
# Edit .env with your Twilio credentials
```

### 3. **Start the System**
```bash
# Terminal 1: Main application
python -m uvicorn main:app --reload --port 8000

# Terminal 2: WhatsApp notifications (optional)
python whatsapp_worker.py
```

### 4. **Access the Dashboard**
- **Admin Dashboard:** http://localhost:8000/admin/dashboard
- **Login with:** `demo` (or your custom admin password)
- **Old Simple Board:** http://localhost:8000/admin/board?passcode=demo

### 5. **Test WhatsApp Integration**
1. **Setup ngrok** for local testing:
   ```bash
   ngrok http 8000
   ```
2. **Configure Twilio webhook:** `https://your-ngrok-url.ngrok.io/webhooks/whatsapp`
3. **Test commands:** Send `JOIN`, `STATUS`, `HELP` to your WhatsApp sandbox number

### 6. **Patient Commands (WhatsApp/SMS)**
- `JOIN` or `JOIN [reason]` - Enter the queue
- `STATUS` - Check position and wait time  
- `LEAVE` - Cancel your ticket
- `LOCATION` - Get clinic address and directions
- `HELP` - See all available commands

### 7. **Admin Features**
- **Real-time queue management** - Move patients through workflow
- **Analytics dashboard** - Track performance and usage
- **Broadcast messaging** - Send announcements to all users
- **Patient timeline** - Monitor all activity

## Project structure

```
clinic_queue_app/
├── main.py          # FastAPI application entry point
├── models.py        # SQLModel definitions for tickets and settings
├── schemas.py       # Pydantic schemas for API responses
├── services.py      # Business logic for tickets, ETAs, and events
├── static/
│   └── admin.js     # Minimal React component for the admin board
├── requirements.txt # Python dependencies
└── README.md        # You are here
```

## 🚀 Production Deployment

Ready to deploy? We've got you covered:

### **Hosting Platforms**
- **Railway** (recommended): `railway up` + automatic PostgreSQL/Redis
- **Render**: Connect GitHub repo + add PostgreSQL/Redis services  
- **Heroku**: `git push heroku main` + addons for database/cache

### **Database Options**
- **Development:** SQLite (automatic, no setup required)
- **Production:** PostgreSQL via [Neon](https://neon.tech), [Supabase](https://supabase.com), or platform add-ons

### **Monitoring & Caching**
- **Redis:** [Upstash](https://upstash.com), [Redis Cloud](https://redis.com), or platform add-ons
- **Analytics:** Built-in dashboard with comprehensive metrics

📖 **Full deployment guide:** See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step instructions.

## 🛠️ Development & Customization

### **Project Structure**
```
Clinic_Que/
├── main.py              # FastAPI app with all endpoints
├── services.py          # Database & business logic  
├── models.py           # Data models (SQLModel)
├── schemas.py          # API request/response schemas
├── whatsapp_worker.py  # Background notification processor
├── setup_twilio.py     # Interactive WhatsApp setup
├── static/
│   ├── admin-dashboard.js  # Enhanced React admin interface
│   └── admin.js           # Simple admin board (legacy)
└── requirements.txt    # Python dependencies
```

### **Key APIs**
- `POST /webhooks/whatsapp` - WhatsApp message handling
- `GET /admin/dashboard` - Enhanced admin interface
- `GET /admin/analytics` - Comprehensive analytics
- `GET /admin/metrics` - Real-time performance data
- `POST /admin/send-broadcast` - WhatsApp broadcast messaging

### **Customization Options**
- **Clinic branding** - Update clinic name, address, hours in `.env`
- **Message templates** - Modify WhatsApp responses in `main.py`
- **Service times** - Adjust default wait time estimates
- **Analytics** - Add custom metrics in `services.py`

## 🤝 Contributing

We welcome contributions! Areas for enhancement:

- **Multi-language support** - Internationalization for diverse communities
- **Advanced scheduling** - Appointment booking integration
- **Payment integration** - Stripe/PayPal for consultation fees  
- **Video consultations** - Zoom/Teams integration for telehealth
- **Electronic health records** - FHIR compatibility
- **SMS provider options** - Beyond Twilio (AWS SNS, etc.)

## 🆘 Support & Troubleshooting

**Common Issues:**
- **WhatsApp not working?** Check webhook URLs and Twilio credentials
- **Database errors?** Verify DATABASE_URL format and permissions
- **Notifications not sending?** Ensure whatsapp_worker.py is running

**Get Help:**
- 📖 Check the comprehensive documentation in code comments
- 🐛 Create GitHub issues for bugs or deployment questions
- 💡 Share feature requests and improvements

---

**🏥 Happy healing!** Your clinic queue system is ready to improve patient experience and reduce waiting room congestion.