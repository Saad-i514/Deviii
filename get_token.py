#!/usr/bin/env python3
"""
Script to get Bearer token for API authentication
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def get_bearer_token():
    """Get Bearer token by logging in"""
    
    # First, register a user (if not already registered)
    print("🔐 Step 1: Register a user...")
    register_data = {
        "email": "admin@devcon.com",
        "password": "adminpassword123",
        "full_name": "Admin User",
        "university": "Devcon University",
        "phone_number": "+923001234567",
        "role": "admin"  # or "participant", "ambassador", "registration_team"
    }
    
    register_response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)
    if register_response.status_code == 201:
        print("✅ User registered successfully")
    elif register_response.status_code == 400:
        print("ℹ️ User already exists, proceeding to login...")
    else:
        print(f"❌ Registration failed: {register_response.status_code}")
        return None
    
    # Login to get token
    print("\n🔑 Step 2: Login to get Bearer token...")
    login_data = {
        "username": "admin@devcon.com",  # Use email as username
        "password": "adminpassword123"
    }
    
    login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    
    if login_response.status_code == 200:
        token_data = login_response.json()
        access_token = token_data["access_token"]
        
        print("✅ Login successful!")
        print(f"\n🎯 Your Bearer Token:")
        print(f"Bearer {access_token}")
        print(f"\n📋 For API testing, use this in Authorization header:")
        print(f"Authorization: Bearer {access_token}")
        
        # Test the token
        print(f"\n🧪 Testing token with /auth/me endpoint...")
        headers = {"Authorization": f"Bearer {access_token}"}
        me_response = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
        
        if me_response.status_code == 200:
            user_info = me_response.json()
            print(f"✅ Token works! User: {user_info['full_name']} ({user_info['role']})")
        else:
            print(f"❌ Token test failed: {me_response.status_code}")
        
        return access_token
    else:
        print(f"❌ Login failed: {login_response.status_code}")
        try:
            error = login_response.json()
            print(f"Error: {error.get('detail', 'Unknown error')}")
        except:
            print(f"Error: {login_response.text}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 GETTING BEARER TOKEN FOR API AUTHENTICATION")
    print("=" * 60)
    
    # Start the server first
    print("⚠️ Make sure your FastAPI server is running:")
    print("   uvicorn app.main:app --reload --port 8000")
    print()
    
    token = get_bearer_token()
    
    if token:
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! You can now use this token for API calls")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Failed to get token")
        print("=" * 60)