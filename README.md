# Clinic Queue by SMS/WhatsApp

This project implements a simple, privacy‑friendly virtual queue for free or pop‑up clinics.  Patients join the queue by texting `JOIN` to a dedicated number.  The system responds with a short ticket code (e.g., `Q7`), their position in line, and an estimated wait time.  Staff interact with a lightweight admin board to move tickets forward and send automated “you’re next” alerts.  An optional kiosk page allows people without phones to join the queue.

## Features

* **SMS/WhatsApp registration** – patients text `JOIN` to get a ticket.  Commands `STATUS` and `LEAVE` let them check their position or exit the queue.
* **Admin board** – a simple web interface lists tickets in `waiting`, `next`, `in_room`, `done`, and `no_show` states.  Staff click buttons to advance tickets or mark no‑shows.
* **Privacy‑first** – tickets are anonymous; only a short code and phone number are stored, plus an optional note.
* **ETA calculation** – uses a rolling average of service times to estimate wait in minutes.  ETAs update whenever the queue changes.
* **Extensible architecture** – the core logic stores truth in a relational database (SQLite by default, PostgreSQL in production).  Events are published to a Redis queue so that SMS/WhatsApp workers and a websocket pusher can run in the background without blocking the API.
* **Configurable** – all credentials and settings are read from environment variables.  You can toggle features such as Redis or switch the database via a single `.env` file.

## Quick start

1. **Clone this repository** and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Set up your environment variables**.  Copy the provided `.env.example` to `.env` and fill in your database URL, Twilio or Vonage credentials, and Redis URL.  You can obtain a free PostgreSQL instance from [Neon](https://neon.tech) and a free 30 MB Redis instance from services like [Upstash](https://upstash.com) or [Redis Cloud](https://redis.com).  In this repository, the database driver falls back to SQLite (a file named `queue.db` in the project directory) if no external driver is available.  To use Neon or another PostgreSQL provider, you will need to install a suitable driver (e.g., `psycopg2-binary`) and adjust `services.py` accordingly.

3. **Run the API server**:

```bash
uvicorn clinic_queue_app.main:app --reload
```

4. **Expose your server** to Twilio/Vonage using a tool like [ngrok](https://ngrok.com):

```bash
ngrok http 8000
```

5. **Configure your messaging provider**.  Point your Twilio phone number’s messaging webhook to `https://<your‑ngrok‑subdomain>/webhooks/sms/twilio`.  If you enable WhatsApp, set the appropriate webhook to `/webhooks/whatsapp`.

6. **Open the admin board** at `http://localhost:8000/admin/board?passcode=<YOUR_ADMIN_PASS>` to view and manage the queue.  Replace `<YOUR_ADMIN_PASS>` with the passcode you set in `.env`.

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

## Limitations and next steps

* The included React admin board is minimal and uses the React CDN to avoid a build step.  For a full front‑end project, you can scaffold a separate `create‑react‑app` and point it at the API.
* Twilio/WhatsApp sending logic in `workers/sms.py` is left as a stub.  Follow the Twilio quickstarts to implement actual SMS delivery.
* For the hackathon, start with the SQLite configuration.  Once the core loop is working, switch to Neon by updating your `DATABASE_URL`.

Happy hacking!