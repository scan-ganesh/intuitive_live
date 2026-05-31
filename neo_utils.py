"""
Script to get portfolio holdings using Kotak Neo API v2 REST API.
This script reads authentication data from Google Cloud Secret Manager
and makes REST API calls without using the Python SDK.
"""

import requests
import json
import os
from google.cloud import secretmanager
from dotenv import load_dotenv
from neo_api_client import NeoAPI

load_dotenv()

# GCP Project Configuration - loaded from environment variables or fallback values
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "795383211266")
SECRET_ID = "NEO_CREDENTIALS"

def load_auth_data_from_secret():
    """Load authentication data from Google Cloud Secret Manager"""
    try:
        # Initialize the Secret Manager Client
        client = secretmanager.SecretManagerServiceClient()
        
        # Build the resource name for the latest version of your secret
        secret_name = f"projects/{GCP_PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
        
        print(f"Retrieving active credentials from secret: {SECRET_ID}...")
        response = client.access_secret_version(request={"name": secret_name})
        
        # Parse the secret payload string back into a Python dictionary
        secret_payload = response.payload.data.decode("UTF-8")
        auth_data = json.loads(secret_payload)
        return auth_data
        
    except Exception as e:
        print(f"❌ Error fetching secret '{SECRET_ID}' from Secret Manager: {e}")
        print("Please verify your GCP_PROJECT_ID and ensure your runtime identity has the 'Secret Manager Secret Viewer' role.")
        return None
    
def get_client():
    data = load_auth_data_from_secret()
    if not data:
        print("Failed to load authentication data. Cannot initialize NeoAPI client.")
        return None
    client = NeoAPI(environment='prod', access_token=None, neo_fin_key=None, consumer_key=os.getenv('NEO_TOKEN'))
    client.configuration.edit_token = data.get("data", {}).get("token")
    client.configuration.edit_sid = data.get("data", {}).get("sid")
    client.configuration.edit_rid = data.get("data", {}).get("rid")
    client.configuration.serverId = data.get("data", {}).get("hsServerId")
    client.configuration.data_center = data.get("data", {}).get("dataCenter")
    client.configuration.base_url = data.get("data", {}).get("baseUrl")
    return client

def get_holdings_v2():
    client = get_client()
    if not client:
        print("Failed to initialize NeoAPI client.")
        return None
    return client.holdings()


def get_portfolio_positions():
    client = get_client()
    if not client:
        print("Failed to initialize NeoAPI client.")
        return None
    return client.positions()


if __name__ == "__main__":
    positions = get_portfolio_positions()
    print("\nCurrent Portfolio Positions:")
    print(json.dumps(positions, indent=2))