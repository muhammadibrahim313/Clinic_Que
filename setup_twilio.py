#!/usr/bin/env python3
"""
Twilio WhatsApp Setup Script

This script helps you set up Twilio WhatsApp integration for the clinic queue system.
It will guide you through the configuration process and test your setup.

Prerequisites:
1. Twilio account (free trial available)
2. WhatsApp Business API access through Twilio
3. A phone number for testing

Usage:
    python setup_twilio.py
"""

import os
import sys
from urllib.parse import quote

def print_header():
    print("🏥 Clinic Queue - Twilio WhatsApp Setup")
    print("=" * 50)

def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN',
        'TWILIO_WHATSAPP_NUMBER'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    return missing_vars

def get_twilio_credentials():
    """Interactive setup for Twilio credentials."""
    print("\n📝 Let's set up your Twilio credentials:")
    print("   (Find these at: https://console.twilio.com/)")
    
    account_sid = input("\n🔑 Enter your Twilio Account SID: ").strip()
    auth_token = input("🔐 Enter your Twilio Auth Token: ").strip()
    
    print("\n📱 WhatsApp Sandbox Setup:")
    print("   1. Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print("   2. Follow the sandbox setup instructions")
    print("   3. Note your WhatsApp sandbox number")
    
    whatsapp_number = input("\n📞 Enter your WhatsApp sandbox number (e.g., +14155238886): ").strip()
    
    if not whatsapp_number.startswith('+'):
        whatsapp_number = '+' + whatsapp_number
    
    return account_sid, auth_token, whatsapp_number

def create_env_file(account_sid, auth_token, whatsapp_number):
    """Create .env file with Twilio credentials."""
    env_content = f"""# Twilio Configuration for WhatsApp
TWILIO_ACCOUNT_SID={account_sid}
TWILIO_AUTH_TOKEN={auth_token}
TWILIO_WHATSAPP_NUMBER=whatsapp:{whatsapp_number}

# Admin Configuration
ADMIN_PASS=demo

# Redis Configuration (optional)
# REDIS_URL=redis://localhost:6379

# Database Configuration (optional)
# DATABASE_URL=sqlite:///queue.db
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print(f"\n✅ Created .env file with your Twilio configuration")

def setup_webhook_urls():
    """Provide webhook URL setup instructions."""
    print("\n🌐 Webhook Setup Instructions:")
    print("   You need to configure webhooks in your Twilio console:")
    print()
    print("   1. Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print("   2. In the Sandbox Configuration section:")
    print("   3. Set 'When a message comes in' to:")
    print("      https://your-domain.com/webhooks/whatsapp")
    print()
    print("   🚀 For local development, use ngrok:")
    print("      1. Install ngrok: https://ngrok.com/download")
    print("      2. Run: ngrok http 8000")
    print("      3. Use the https URL + /webhooks/whatsapp")
    print()
    print("   📱 Example webhook URL:")
    print("      https://abc123.ngrok.io/webhooks/whatsapp")

def test_setup():
    """Provide testing instructions."""
    print("\n🧪 Testing Your Setup:")
    print("   1. Start your clinic queue server:")
    print("      python -m uvicorn main:app --reload --port 8000")
    print()
    print("   2. Start the WhatsApp worker (in another terminal):")
    print("      python whatsapp_worker.py")
    print()
    print("   3. Test WhatsApp messages:")
    print("      • Send 'JOIN' to your WhatsApp sandbox number")
    print("      • Try 'STATUS', 'HELP', 'LOCATION' commands")
    print("      • Test the admin dashboard at: http://localhost:8000/admin/dashboard")

def show_deployment_tips():
    """Show production deployment tips."""
    print("\n🚀 Production Deployment Tips:")
    print()
    print("   📊 Use a production Redis instance:")
    print("      • Upstash: https://upstash.com/")
    print("      • Redis Cloud: https://redis.com/")
    print()
    print("   🗄️ Use a production database:")
    print("      • Neon PostgreSQL: https://neon.tech/")
    print("      • PlanetScale: https://planetscale.com/")
    print()
    print("   🌐 Deploy your API:")
    print("      • Railway: https://railway.app/")
    print("      • Render: https://render.com/")
    print("      • Vercel: https://vercel.com/")
    print()
    print("   🔧 Set environment variables on your hosting platform")
    print("   📱 Update Twilio webhooks to your production URLs")

def main():
    print_header()
    
    # Check if already configured
    missing_vars = check_environment()
    
    if not missing_vars:
        print("✅ Twilio environment variables already configured!")
        print(f"   Account SID: {os.getenv('TWILIO_ACCOUNT_SID', '')[:8]}...")
        print(f"   WhatsApp Number: {os.getenv('TWILIO_WHATSAPP_NUMBER', '')}")
    else:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        
        setup_choice = input("\n❓ Would you like to set up Twilio now? (y/n): ").lower()
        if setup_choice != 'y':
            print("👋 Setup cancelled. Run this script again when ready!")
            return
        
        # Get credentials
        account_sid, auth_token, whatsapp_number = get_twilio_credentials()
        
        # Create .env file
        create_env_file(account_sid, auth_token, whatsapp_number)
    
    # Show setup instructions
    setup_webhook_urls()
    test_setup()
    show_deployment_tips()
    
    print("\n" + "=" * 50)
    print("🎉 Setup complete! Your clinic queue is ready for WhatsApp!")
    print("📚 Need help? Check the README.md for more details.")

if __name__ == "__main__":
    main()