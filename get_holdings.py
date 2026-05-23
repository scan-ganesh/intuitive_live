"""
Script to get portfolio holdings using Kotak Neo API v2 REST API.
This script reads authentication data from daily.json and makes REST API calls
without using the Python SDK.
"""

import ast
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def load_auth_data():
    """Load authentication data from daily.json"""
    try:
        with open('daily.json', 'r') as f:
            content = f.read()
            auth_data = ast.literal_eval(content)  # Safely evaluate Python literal
        return auth_data
    except FileNotFoundError:
        print("❌ Error: daily.json not found. Please run login first to generate authentication data.")
        return None
    except Exception as e:
        print(f"❌ Error reading daily.json: {e}")
        return None

def get_holdings():
    """Get portfolio holdings using REST API"""
    # Load authentication data
    auth_data = load_auth_data()
    if not auth_data:
        return None
    
    # Extract necessary tokens and URLs
    try:
        access_token = auth_data['data']['token']
        sid = auth_data['data']['sid']
        base_url = auth_data['data']['baseUrl']
    except KeyError as e:
        print(f"❌ Error: Missing expected key in daily.json: {e}")
        return None
    
    print("Loaded authentication data:")
    print(f"Base URL: {base_url}")
    print(f"Access Token: {access_token[:50]}...")
    print(f"SID: {sid}")
    
    # Set up headers exactly as specified in the documentation
    headers = {
        'Auth': access_token,  # Note: Using 'Auth' not 'Authorization' or 'Bearer'
        'Sid': sid,
        'neo-fin-key': 'neotradeapi',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Make the API call for holdings
    endpoint = "/portfolio/v1/holdings"
    url = f"{base_url}{endpoint}"
    
    print(f"\nMaking API call to:")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            holdings_data = response.json()
            print("✓ Success! Received holdings data:")
            return holdings_data
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error making request: {e}")
        print("Please check your network connection and the validity of the tokens.")
        return None

def display_holdings_summary(holdings_data):
    """Display a summary of the holdings"""
    if not holdings_data or 'data' not in holdings_data:
        print("No holdings data to display")
        return
    
    holdings = holdings_data['data']
    print(f"\n📊 Holdings Summary:")
    print(f"Total Holdings: {len(holdings)}")
    
    # Calculate total market value
    total_mkt_value = sum(item.get('mktValue', 0) for item in holdings)
    total_holding_cost = sum(item.get('holdingCost', 0) for item in holdings)
    total_pl = sum(item.get('unrealisedGainLoss', 0) for item in holdings)
    
    print(f"Total Market Value: ₹{total_mkt_value:,.2f}")
    print(f"Total Holding Cost: ₹{total_holding_cost:,.2f}")
    print(f"Total P/L: ₹{total_pl:,.2f} ({((total_pl/total_holding_cost)*100) if total_holding_cost != 0 else 0:.2f}%)")
    
    # Show top 5 holdings by market value
    sorted_holdings = sorted(holdings, key=lambda x: x.get('mktValue', 0), reverse=True)
    print(f"\n🔝 Top 5 Holdings by Market Value:")
    for i, holding in enumerate(sorted_holdings[:5], 1):
        print(f"{i}. {holding.get('tradingsymbol', holding.get('symbol', 'N/A'))}: "
              f"₹{holding.get('mktValue', 0):,.2f} ({holding.get('quantity', 0)} units)")

if __name__ == "__main__":
    print("=" * 60)
    print("Kotak Neo API v2 - Portfolio Holdings (REST API)")
    print("=" * 60)
    
    holdings_data = get_holdings()
    
    if holdings_data:
        display_holdings_summary(holdings_data)
        
        # Optionally save to file for inspection
        output_file = "holdings_response.json"
        with open(output_file, 'w') as f:
            json.dump(holdings_data, f, indent=2)
        print(f"\n💾 Full response saved to: {output_file}")
    else:
        print("\n❌ Failed to retrieve holdings data")
        
    print("\n" + "=" * 60)