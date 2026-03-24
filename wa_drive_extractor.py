#!/usr/bin/env python3

"""
WhatsApp Google Drive Backup Extractor
Usage: python3 wa_drive_extractor.py help|info|list|sync

    help    Show this help.
    info    Show WhatsApp backups metadata.
    list    Show list of files in the WhatsApp backup.
    sync    Download all WhatsApp backup files to local storage.
"""

import os
import sys
import json
import hashlib
import requests
import gpsoauth
import traceback
import configparser
from base64 import b64decode
from getpass import getpass
from multiprocessing.pool import ThreadPool
from textwrap import dedent

def human_size(size):
    for s in ["B", "kiB", "MiB", "GiB", "TiB", "PiB"]:
        if abs(size) < 1024:
            break
        size = int(size / 1024)
    return "{}{}".format(size, s)

def have_file(file, size, md5):
    if not os.path.exists(file) or size != os.path.getsize(file):
        return False
    digest = hashlib.md5()
    with open(file, "br") as f:
        while True:
            b = f.read(8 * 1024)
            if not b:
                break
            digest.update(b)
    return md5 == digest.digest()

def download_file(file, stream):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, "bw") as dest:
        for chunk in stream.iter_content(chunk_size=None):
            if chunk:
                dest.write(chunk)

class WaBackup:
    def __init__(self, gmail, password, android_id, oauth_token=None):
        self.gmail = gmail
        self.android_id = android_id
        
        if oauth_token:
            print("[*] Logging in via OAuth Token...")
            token = gpsoauth.exchange_token(gmail, oauth_token, android_id)
        else:
            print("[*] Logging in via Password...")
            token = gpsoauth.perform_master_login(gmail, password, android_id)
        
        if "Error" in token:
            print(f"ERROR: {token['Error']}")
            if "NeedsBrowser" in token:
                print("Hint: 2FA is active. Use an App Password or OAuth token.")
            sys.exit(1)

        if "Token" not in token:
            quit("ERROR: Failed to retrieve Master Token.")

        self.auth = gpsoauth.perform_oauth(
            gmail, token["Token"], android_id,
            "oauth2:https://www.googleapis.com/auth/drive.appdata",
            "com.whatsapp",
            "38a0f7d505fe18fec64fbf343ecaaaf310dbd799")
        
        if "Auth" not in self.auth:
            quit("ERROR: OAuth failed. Check your credentials.")

    def get(self, path, params=None, **kwargs):
        headers = {"Authorization": "Bearer {}".format(self.auth["Auth"])}
        url = "https://backup.googleapis.com/v1/{}".format(path)
        response = requests.get(url, headers=headers, params=params, **kwargs)
        response.raise_for_status()
        return response

    def list_path(self, path):
        last_component = path.split("/")[-1]
        page_token = None
        while True:
            params = {"pageToken": page_token} if page_token else {}
            page = self.get(path, params=params).json()
            if last_component in page:
                for item in page[last_component]:
                    yield item
            if "nextPageToken" not in page:
                break
            page_token = page["nextPageToken"]

    def backups(self):
        return self.list_path("clients/wa/backups")

    def backup_files(self, backup):
        return self.list_path("{}/files".format(backup["name"]))

    def fetch(self, file):
        # Clean path for cross-platform compatibility
        raw_name = "/".join(file["name"].split("/")[3:])
        name = os.path.normpath(raw_name)
        
        md5_hash = b64decode(file["md5Hash"])
        size = int(file["sizeBytes"])

        if not have_file(name, size, md5_hash):
            safe_url_name = file["name"].replace("%", "%25").replace("+", "%2B")
            download_file(name, self.get(safe_url_name, {"alt": "media"}, stream=True))
        return name, size, md5_hash

    def fetch_all(self, backup, cksums):
        num_files = 0
        total_size = 0
        target_size = int(backup["sizeBytes"])
        
        with ThreadPool(5) as pool: # Lower thread count for stability
            downloads = pool.imap_unordered(lambda f: self.fetch(f), self.backup_files(backup))
            for name, size, md5_hash in downloads:
                num_files += 1
                total_size += size
                progress = (total_size / target_size) * 100 if target_size > 0 else 0
                print(f"\rProgress: {progress:7.2f}% | Local: {name[-40:]}", end="", flush=True)
                cksums.write(f"{md5_hash.hex()} *{name}\n")

        print(f"\nCompleted: {num_files} files ({human_size(total_size)})")

def get_configs():
    config = configparser.ConfigParser()
    if not os.path.isfile("settings.cfg"):
        create_settings_file()
        print("Created 'settings.cfg'. Please fill in your details and run again.")
        sys.exit(0)

    config.read("settings.cfg")
    try:
        gmail = config.get("auth", "gmail")
        password = config.get("auth", "password", fallback="")
        android_id = config.get("auth", "android_id")
        oauth_token = config.get("auth", "oauth_token", fallback=None)

        if not password and not oauth_token:
            password = getpass(f"Enter password for {gmail}: ")

        return {"gmail": gmail, "password": password, "android_id": android_id, "oauth_token": oauth_token}
    except Exception as e:
        quit(f"Error reading config: {e}")

def create_settings_file():
    content = dedent("""
        [auth]
        gmail = yourname@gmail.com
        password = your_app_password
        android_id = 0000000000000000
        oauth_token = 
    """).strip()
    with open("settings.cfg", "w") as f:
        f.write(content)

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("info", "list", "sync"):
        print(__doc__.format(sys.argv[0]))
        return

    configs = get_configs()
    wa = WaBackup(**configs)
    backups = list(wa.backups())

    mode = sys.argv[1]
    for b in backups:
        confirm = input(f"\nProcess backup {b['name'].split('/')[-1]}? [y/n]: ")
        if confirm.lower() != 'y': continue

        if mode == "info":
            meta = json.loads(b["metadata"])
            print(f"--- Backup Info ---")
            print(f"Update Time: {b['updateTime']}")
            print(f"Messages: {meta.get('numOfMessages')}")
            print(f"Size: {human_size(int(b['sizeBytes']))}")

        elif mode == "list":
            for f in wa.backup_files(b):
                print("/".join(f["name"].split("/")[3:]))

        elif mode == "sync":
            with open("md5sum.txt", "a") as cksums:
                wa.fetch_all(b, cksums)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
