# Agents Guidance for intuitive_live
## Project Setup
- Initialize a new Python project with uv: `uv init`
## Dependency Management
- Use uv for adding packages: `uv add <package-name>`
- Required packages for this project:
  - requests (for REST API calls)
  - python-dotenv (for environment variable management)
  - breeze-connect (for Breeze API interactions)
## Breeze API Usage
### Authentication Flow
1. The authentication details should be stored in `.env` with this structure:
```makefile
API_KEY=<api_key>
API_SECRET=<api_secret>
SESSION_ID=<session_id>
```
2. For historical data API calls:
  - Endpoint: `get_historical_data_v2` method of `breeze_connect` library
  - Parameters: stock_code, exchange_code, product_type, expiry_date, from_date, to_date, interval
### Development Workflow
- Store authentication data securely in `.env` (add to .gitignore)
- Use `intuitive.py` for Breeze API interactions
- Use separate scripts (like `get_holdings.py`) for other API calls to avoid interfering with Breeze API process
## Notes
- This AGENTS.md will be updated as the project structure becomes clearer.
- The Breeze API documentation can be referenced at: https://github.com/Idirect-Tech/Breeze-Python-SDK