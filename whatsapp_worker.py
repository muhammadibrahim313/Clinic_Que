#!/usr/bin/env python3
"""
WhatsApp Notification Worker

This script processes queued WhatsApp notifications and sends them via Twilio.
Run this as a separate background process for production use.

Usage:
    python whatsapp_worker.py

Environment Variables Required:
    TWILIO_ACCOUNT_SID - Your Twilio Account SID
    TWILIO_AUTH_TOKEN - Your Twilio Auth Token  
    TWILIO_WHATSAPP_NUMBER - Your Twilio WhatsApp number (e.g., whatsapp:+14155238886)
    REDIS_URL - Redis connection URL
"""

import os
import json
import time
import redis
from datetime import datetime
from typing import Optional

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Warning: Twilio not installed. Install with: pip install twilio")

# Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN") 
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class WhatsAppWorker:
    def __init__(self):
        self.redis_client = None
        self.twilio_client = None
        self.setup_connections()
    
    def setup_connections(self):
        """Initialize Redis and Twilio connections."""
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            print(f"✅ Connected to Redis: {REDIS_URL}")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            return False
        
        if TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            try:
                self.twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                print(f"✅ Connected to Twilio WhatsApp: {TWILIO_WHATSAPP_NUMBER}")
            except Exception as e:
                print(f"❌ Failed to connect to Twilio: {e}")
                return False
        else:
            print("⚠️  Twilio not configured - running in simulation mode")
        
        return True
    
    def send_whatsapp_message(self, to_number: str, message: str) -> bool:
        """Send WhatsApp message via Twilio."""
        try:
            if not self.twilio_client:
                print(f"📱 [SIMULATION] WhatsApp to {to_number}: {message[:50]}...")
                return True
            
            # Ensure number has whatsapp: prefix
            if not to_number.startswith('whatsapp:'):
                to_number = f'whatsapp:{to_number}'
            
            message_obj = self.twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=message,
                to=to_number
            )
            
            print(f"✅ WhatsApp sent to {to_number}: {message_obj.sid}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send WhatsApp to {to_number}: {e}")
            return False
    
    def process_notifications(self):
        """Main worker loop to process notification queue."""
        print("🚀 WhatsApp Worker started - waiting for notifications...")
        
        while True:
            try:
                # Block and wait for notifications (up to 5 seconds)
                notification_data = self.redis_client.brpop("whatsapp_notifications", timeout=5)
                
                if not notification_data:
                    continue  # Timeout - check again
                
                # Parse notification
                notification = json.loads(notification_data[1])
                
                phone = notification.get("phone")
                message = notification.get("message")
                notification_type = notification.get("type")
                
                if not phone or not message:
                    print(f"⚠️  Invalid notification: {notification}")
                    continue
                
                # Add timestamp to message for better tracking
                timestamp = datetime.now().strftime("%H:%M")
                formatted_message = f"{message}\n\n_Sent at {timestamp}_"
                
                # Send the message
                success = self.send_whatsapp_message(phone, formatted_message)
                
                if success:
                    # Log successful send
                    log_data = {
                        "phone": phone[-4:],  # Last 4 digits for privacy
                        "type": notification_type,
                        "sent_at": datetime.utcnow().isoformat(),
                        "status": "sent"
                    }
                    self.redis_client.lpush("whatsapp_logs", json.dumps(log_data))
                else:
                    # Retry failed messages (simple retry once)
                    retry_notification = notification.copy()
                    retry_notification["retry"] = True
                    if not notification.get("retry"):  # Don't retry twice
                        self.redis_client.lpush("whatsapp_notifications", json.dumps(retry_notification))
                
            except KeyboardInterrupt:
                print("\n🛑 Worker stopped by user")
                break
            except Exception as e:
                print(f"❌ Error processing notification: {e}")
                time.sleep(1)  # Brief pause on error

    def get_stats(self) -> dict:
        """Get worker statistics."""
        try:
            queue_length = self.redis_client.llen("whatsapp_notifications")
            logs_count = self.redis_client.llen("whatsapp_logs")
            
            return {
                "queue_length": queue_length,
                "total_sent": logs_count,
                "worker_status": "running",
                "last_check": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}


def main():
    """Main entry point."""
    print("🏥 Clinic Queue - WhatsApp Notification Worker")
    print("=" * 50)
    
    # Check environment
    if not REDIS_URL:
        print("❌ REDIS_URL environment variable required")
        return
    
    if not TWILIO_AVAILABLE:
        print("⚠️  Running without Twilio - messages will be simulated")
        print("   Install Twilio: pip install twilio")
        print("   Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
    
    # Start worker
    worker = WhatsAppWorker()
    
    if worker.redis_client:
        try:
            worker.process_notifications()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
    else:
        print("❌ Cannot start without Redis connection")


if __name__ == "__main__":
    main()