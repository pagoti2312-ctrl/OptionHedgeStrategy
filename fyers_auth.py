import os
import json
import hashlib
import urllib.request
import urllib.parse
import urllib.error

CONFIG_FILE = "fyers_config.json"
TOKEN_FILE = "fyers_token.txt"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("fyers_config.json not found. Let's configure your Fyers credentials.")
        client_id = input("Enter your Fyers Client ID/App ID (e.g. ABC123-100): ").strip()
        secret_key = input("Enter your Fyers Secret Key: ").strip()
        redirect_uri = input("Enter your Fyers Redirect URI (e.g. http://127.0.0.1:8000/): ").strip()
        
        config = {
            "client_id": client_id,
            "secret_key": secret_key,
            "redirect_uri": redirect_uri
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        print("Configuration saved to " + CONFIG_FILE)
        return config
    else:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

def try_token_exchange(app_id_hash, auth_code, label=""):
    """Try to exchange auth_code for token with a given appIdHash."""
    token_url = "https://api-t1.fyers.in/api/v3/token"
    payload = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": auth_code
    }
    
    json_data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(
        token_url,
        data=json_data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )
    
    try:
        print("[" + label + "] Trying token exchange with appIdHash: " + app_id_hash[:16] + "...")
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body)
            return {"success": True, "data": res_json}
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode('utf-8')
        except:
            pass
        return {"success": False, "code": e.code, "reason": e.reason, "body": err_body}
    except Exception as e:
        return {"success": False, "code": 0, "reason": str(e), "body": ""}

def run_auth_flow():
    config = load_config()
    client_id = config["client_id"]
    secret_key = config["secret_key"]
    redirect_uri = config["redirect_uri"]
    
    # 1. Generate authorization code URL
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": "fyers_option_bot"
    }
    query_string = urllib.parse.urlencode(params)
    login_url = "https://api-t1.fyers.in/api/v3/generate-authcode?" + query_string
    
    print("=== FYERS API V3 AUTHENTICATION ===")
    print("1. Open the following URL in your web browser:")
    print("")
    print(login_url)
    print("")
    print("2. Login to Fyers, complete your security checks (OTP/PIN).")
    print("3. After login, your browser will redirect you to your Redirect URI.")
    print("4. Copy the entire redirect URL or the auth_code value.")
    
    redirected_input = input("\nPaste the auth_code or redirect URL: ").strip()
    
    # Extract auth_code if they pasted the whole URL
    auth_code = redirected_input
    if "auth_code=" in redirected_input:
        parsed_url = urllib.parse.urlparse(redirected_input)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        auth_code = query_params.get("auth_code", [None])[0]
        
    if not auth_code:
        print("ERROR: Could not extract auth_code.")
        return
        
    print("Extracted Auth Code: " + auth_code[:20] + "...")
    
    # 2. Try multiple hash formats - Fyers docs say SHA256(app_id:secret_key)
    # but it's unclear whether app_id includes the -100 suffix or not
    
    # Attempt 1: Full client_id with suffix (e.g. "8UFYKQNBXK-100:LTTBDDL8QH")
    hash_input_1 = client_id + ":" + secret_key
    hash_1 = hashlib.sha256(hash_input_1.encode('utf-8')).hexdigest()
    
    # Attempt 2: Base app_id without suffix (e.g. "8UFYKQNBXK:LTTBDDL8QH")
    base_app_id = client_id.split("-")[0] if "-" in client_id else client_id
    hash_input_2 = base_app_id + ":" + secret_key
    hash_2 = hashlib.sha256(hash_input_2.encode('utf-8')).hexdigest()
    
    print("")
    print("Debug info:")
    print("  client_id  = " + client_id)
    print("  base_app   = " + base_app_id)
    print("  secret_key = " + secret_key[:4] + "***" + secret_key[-2:])
    print("  hash1 (full)  = " + hash_1[:20] + "...")
    print("  hash2 (base)  = " + hash_2[:20] + "...")
    print("")
    
    # Try Attempt 1: full client_id
    result = try_token_exchange(hash_1, auth_code, "Attempt 1: full app_id")
    
    if result["success"]:
        handle_success(result["data"], client_id)
        return
    else:
        print("  -> Failed: HTTP " + str(result["code"]) + " " + result["reason"])
        print("  -> Response: " + result["body"])
        print("")
    
    # Try Attempt 2: base app_id (without -100)
    result = try_token_exchange(hash_2, auth_code, "Attempt 2: base app_id")
    
    if result["success"]:
        handle_success(result["data"], client_id)
        return
    else:
        print("  -> Failed: HTTP " + str(result["code"]) + " " + result["reason"])
        print("  -> Response: " + result["body"])
        print("")
    
    # Both failed
    print("=" * 60)
    print("BOTH attempts failed.")
    print("")
    print("This usually means the 'secret_key' in fyers_config.json is wrong.")
    print("On the Fyers dashboard (myapi.fyers.in):")
    print("  1. Click on your app name 'optionbot'")
    print("  2. Look for 'Secret Key' (NOT 'Secret ID')")
    print("  3. You may need to click a three-dot menu or 'Show' button")
    print("  4. The Secret Key is typically a longer alphanumeric string")
    print("")
    print("Once you have the correct Secret Key, update fyers_config.json")
    print("and run this script again.")
    print("=" * 60)

def handle_success(res_json, client_id):
    if res_json.get("s") == "ok" or "access_token" in res_json:
        access_token = res_json.get("access_token")
        full_auth_token = client_id + ":" + access_token
        
        with open(TOKEN_FILE, "w") as f:
            f.write(full_auth_token)
            
        print("")
        print("SUCCESS! Access token generated and saved to " + TOKEN_FILE)
        print("This token is valid for today. Run this script daily before market hours.")
    else:
        print("Unexpected response from Fyers: " + json.dumps(res_json))

if __name__ == "__main__":
    run_auth_flow()
