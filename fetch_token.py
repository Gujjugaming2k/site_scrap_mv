import requests
import re
import json
import base64
import subprocess

# Base64-encoded credentials
ENCODED_TOKEN = "MTExODY0NTYyNDpBQUZzNHBBd3NMRG9vOTVjWDZwUGU5cEQxb0w1QjFoaTlzNA=="
ENCODED_CHANNEL_ID = "LTEwMDIxOTY1MDM3MDU="

# Decode credentials
BOT_TOKEN = base64.b64decode(ENCODED_TOKEN).decode("utf-8")
CHANNEL_ID = base64.b64decode(ENCODED_CHANNEL_ID).decode("utf-8")

def get_cookie():
    url = "https://net51.cc/tv/p.php"
    response = requests.get(url)
    set_cookie = response.headers.get("Set-Cookie")
    if set_cookie:
        match = re.search(r't_hash_t=([^;]+)', set_cookie)
        if match:
            return match.group(1)
    return None

def get_prime_cookie():
    url = "https://net51.cc/tv/p.php"
    response = requests.get(url)
    set_cookie = response.headers.get("Set-Cookie")
    if set_cookie:
        match = re.search(r't_hash=([^;]+)', set_cookie)
        if match:
            return match.group(1)
    return None

def handle_netflix(cookie_value):
    url = "https://net20.cc/play.php"
    payload = {"id": "81705721"}
    headers = {"Cookie": f"t_hash_t={cookie_value}"}
    response = requests.post(url, data=payload, headers=headers)
    try:
        data = response.json()
        h_value = data.get("h", "")
        if h_value.startswith("in="):
            with open("netflix_cookie.txt", "w") as f:
                f.write(h_value)
            print("Netflix cookie saved to netflix_cookie.txt:", h_value)
            return h_value
        else:
            print("Unexpected format in Netflix response:", h_value)
    except json.JSONDecodeError:
        print("Failed to parse Netflix JSON response.")
    return None

def handle_prime(prime_cookie):
    url = "https://net51.cc/pv/playlist.php?id=0IOXQJ1CQWMH3Y1FNVUO30OSME&tm=1761932966"
    headers = {"Cookie": f"t_hash_t={prime_cookie}"}
    response = requests.post(url, headers=headers)
    try:
        data = response.json()
        seen = set()
        for item in data:
            for source in item.get("sources", []):
                file_url = source.get("file", "")
                match = re.search(r'in=([a-f0-9]{32}::[a-f0-9]{32}::\d+::[a-z]+)', file_url)
                if match:
                    in_value = f"in={match.group(1)}"
                    if in_value not in seen:
                        seen.add(in_value)
                        with open("prime_cookie.txt", "w") as f:
                            f.write(in_value)
                        print("Prime cookie saved to prime_cookie.txt:", in_value)
                        return in_value
    except json.JSONDecodeError:
        print("Failed to parse Prime JSON response.")
    return None

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("Message sent to Telegram.")
    else:
        print("Failed to send Telegram message:", response.text)

def run_update_script():
    try:
        subprocess.run(["python", "update_token.py"], check=True)
        print("update_token.py executed.")
    except subprocess.CalledProcessError as e:
        print("Error running update_token.py:", e)

# Main execution
cookie = get_prime_cookie()
prime_cookie = get_prime_cookie()

if cookie and prime_cookie:
    netflix_token = handle_netflix(cookie)
    prime_token = handle_prime(prime_cookie)

    if netflix_token and prime_token:
        message = f"*IOSMIRROR Token:*\n`{prime_token}`"
        send_to_telegram(message)
        #run_update_script()
    else:
        print("Missing one or both tokens. Telegram and update skipped.")
else:
    print("Failed to retrieve one or both cookies.")

