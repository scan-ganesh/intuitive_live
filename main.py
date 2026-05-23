import os
from neo_api_client import NeoAPI
from dotenv import load_dotenv

load_dotenv()

# Initialize the NeoAPI client for login purposes
client = NeoAPI(environment='prod', access_token=None, neo_fin_key=None, consumer_key=os.getenv('NEO_TOKEN'))

# This file is intended for login operations
# Uncomment and use the following lines when you need to perform login:

# Step 1: TOTP login
# totp_response = client.totp_login(mobile_number="+919566044494", ucc="V1ZWD", totp='YOUR_TOTP_CODE')
# print("TOTP Login Response:", totp_response)

# Step 2: TOTP validation with MPIN (after getting TOTP success)
# if totp_response.get('status') == 'success':
#     mpin = os.getenv('NEO_MPIN')  # You should set this in your .env file
#     if mpin:
#         validate_response = client.totp_validate(mpin=mpin)
#         print("TOTP Validation Response:", validate_response)
#     else:
#         print("Please set NEO_MPIN in your .env file for validation")

# After successful validation, you can use the client for other API calls
# Example: print(client.holdings())

print("main.py is configured for login operations.")
print("Uncomment the login steps above when you need to authenticate.")
print("Your authentication data will be stored in daily.json after successful login.")