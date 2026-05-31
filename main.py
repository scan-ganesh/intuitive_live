import os
from neo_api_client import NeoAPI
from dotenv import load_dotenv

load_dotenv()

token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIyMzQ1Zjg0Ni02NTE0LTRkMDAtOTVjOS1hNDc2ZDkwZGJmOGYiLCJpc3MiOiJsb2dpbi1zZXJ2aWNlIiwic3ViIjoiOGY5YjMwNjYtNmU0YS00ZjhlLWI2MjItNjQ0NzBkOWRlYWM0IiwidWNjIjoiVjFaV0QiLCJuYXAiOiIiLCJ5Y2UiOiJlWVxcNiAuJTUodlx1MDAwMlxmXHUwMDAyfVx1MDAwMFx1MDAxMGIiLCJjYXRlZ29yaXNhdGlvbiI6IiIsInNjb3BlIjpbIlRyYWRlIl0sImV4cCI6MTc4MDE2NTgwMCwiaWF0IjoxNzgwMTIxMDE0LCJmZXRjaGNhY2hpbmdydWxlIjowfQ.MU_ousCuC-laFjq8x9aL2CRo9YaO7Bk0_kwKjf5pNH2gF446sY9W2tqMIzG-9zv-xTBwtVLEsHRabrVFs-Nk0cLjo8UkPhJwvJF-zmE7n-MQBzrY71xZVHBmndp2pcWQzvUBySFEw-knbKpXZnsEZMbSBpi9jO7KaWhZ0AMcrKKOVGRFnrg0tQZ0rU82hB9zYm15L3eUNkrMbuKQYbtpjP5TcgOqz61WbDNv3dib31HGKhUHzCjfw4OFG8NVbPDAoAFDfqeg-P7yQW4qdWjPrpQ7j3vUZ5zlUw7tYBmtC8GeCsfqY_tie2YRzBDov9IHoZ9tDTJ49DP6ycu4OatYIA"
sid = "18881488-1807-4243-a7f2-714ebcbead24"
rid = "431385e8-d3ca-496d-94b3-b5765b8fd168"
hsServerId = ""
dataCenter = "E21"
baseUrl = "https://e21.kotaksecurities.com"

# Initialize the NeoAPI client for login purposes
client = NeoAPI(environment='prod', access_token=None, neo_fin_key=None, consumer_key=os.getenv('NEO_TOKEN'))
client.configuration.edit_token = token
client.configuration.edit_sid = sid
client.configuration.edit_rid = rid
client.configuration.serverId = hsServerId
client.configuration.data_center = dataCenter
client.configuration.base_url = baseUrl

# This file is intended for login operations
# Uncomment and use the following lines when you need to perform login:

# Step 1: TOTP login
#totp_response = client.totp_login(mobile_number=os.getenv('NEO_MOBILE'), ucc=os.getenv('NEO_UCC'), totp='YOUR_TOTP_CODE')
#print("TOTP Login Response:", totp_response)

# Step 2: TOTP validation with MPIN (after getting TOTP success)
# if totp_response.get('status') == 'success':
#     mpin = os.getenv('NEO_MPIN')  # You should set this in your .env file
#     if mpin:
#         validate_response = client.totp_validate(mpin=mpin)
#         print("TOTP Validation Response:", validate_response)
#     else:
#         print("Please set NEO_MPIN in your .env file for validation")

# After successful validation, you can use the client for other API calls
print(client.holdings())

print("main.py is configured for login operations.")
print("Uncomment the login steps above when you need to authenticate.")
print("Your authentication data will be stored in daily.json after successful login.")