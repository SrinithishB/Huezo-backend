import requests
import json
from urllib.parse import urlparse, parse_qs

def main():
    print("==================================================")
    print("      Zoho Books Refresh Token Generator         ")
    print("==================================================")
    
    # 1. Ask for credentials
    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()
    
    raw_input = input("Paste the FULL browser redirect URL (or just the Code): ").strip()
    
    # Automatically parse the code and region if a full URL is pasted
    code = raw_input
    accounts_domain = "https://accounts.zoho.in"  # default
    
    if "code=" in raw_input or "callback" in raw_input:
        try:
            parsed = urlparse(raw_input)
            params = parse_qs(parsed.query)
            if "code" in params:
                code = params["code"][0]
            if "accounts-server" in params:
                accounts_domain = params["accounts-server"][0]
            elif "location=us" in raw_input:
                accounts_domain = "https://accounts.zoho.com"
        except Exception as e:
            print(f"Error parsing URL, using raw input as code: {e}")

    redirect_uri = input("Enter Redirect URI [default: https://api-console.zoho.in/oauth/callback]: ").strip()
    if not redirect_uri:
        redirect_uri = "https://api-console.zoho.in/oauth/callback"
        
    print(f"\nDetected Zoho Accounts Domain: {accounts_domain}")
    print("Requesting tokens from Zoho...")
    
    # 2. Make request to Zoho
    url = f"{accounts_domain.rstrip('/')}/oauth/v2/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    try:
        response = requests.post(url, data=data)
        res_data = response.json()
        
        if response.status_code == 200 and "refresh_token" in res_data:
            print("\nSUCCESS!")
            print("--------------------------------------------------")
            print(f"Refresh Token: {res_data['refresh_token']}")
            print(f"Access Token (expires in 1 hr): {res_data['access_token']}")
            print("--------------------------------------------------")
            print("Copy the Refresh Token and paste it into your .env file as ZOHO_REFRESH_TOKEN.")
        else:
            print("\nFAILED TO GENERATE REFRESH TOKEN:")
            print(json.dumps(res_data, indent=2))
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
