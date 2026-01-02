"""
AIMX CloudTouch Discord Bot - Enhanced Name Sniffer
Full-featured username availability checker with real verification methods
Requires: pip install discord.py aiohttp requests beautifulsoup4
"""
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
import asyncio
import aiohttp
import os
import sys
import random
import string
import time
# import requests  # Removed - using aiohttp instead
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO
import json
import threading
import concurrent.futures

# Bot configuration
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "MTQ1MTk3ODkyNzE3NzIwNzgyOQ.G6ZQe9.ZuVCcTLnpH8ZG1cx8U87lH7cksB6jRzBE-aH_U")
MAIN_WEBHOOK = "https://discord.com/api/webhooks/1456569880508891157/arH7x_HovsM7iEszGUoZKaZhyZJ3yNUPwqSayXvTSQtkJVwIiQkjxikURTvKBSBEKFCi"
DISCORD_USER_ID = "1385239185006268457"
OWNER_ROLE_ID = 1456739151247314975
TESTER_ROLE_ID = 1456739453786919121
APPLE_PAY_NUMBER = "7656156371"

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store active operations
active_scans = {}
available_names_by_platform = {}
scan_logs = {}
bot_should_restart = False
bot_should_shutdown = False

# Vercel API URL (set in Railway environment variables)
VERCEL_API_URL = os.getenv("VERCEL_API_URL", "https://your-project.vercel.app/api")

# Premium system files - Railway persistent storage
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
KEYS_FILE = os.path.join(DATA_DIR, "premium_keys.json")
USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")
CLOUDTOUCH_ACCESS_FILE = os.path.join(DATA_DIR, "cloudtouch_access.json")
CLOUDTOUCH_DOWNLOAD_LINK = os.getenv("CLOUDTOUCH_DOWNLOAD_LINK", "")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Load premium keys
def load_keys():
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_keys(keys_data):
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys_data, f, indent=2)

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_data(user_data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(user_data, f, indent=2)

# CloudTouch access management
def load_cloudtouch_access():
    if os.path.exists(CLOUDTOUCH_ACCESS_FILE):
        try:
            with open(CLOUDTOUCH_ACCESS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cloudtouch_access(access_data):
    with open(CLOUDTOUCH_ACCESS_FILE, 'w') as f:
        json.dump(access_data, f, indent=2)

def has_cloudtouch_access(user_id):
    """Check if user has CloudTouch access"""
    access_data = load_cloudtouch_access()
    return str(user_id) in access_data

def generate_key():
    """Generate a unique premium key"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def has_premium_access(user_id):
    """Check if user has premium access (key or role)"""
    # Check role first (fallback)
    try:
        # This will be checked in the command itself
        pass
    except:
        pass
    
    # Check key
    keys_data = load_keys()
    for key, data in keys_data.items():
        if str(data.get("user_id")) == str(user_id):
            return True, key
    return False, None

async def log_to_webhook(user_id, action, data=None):
    """Log user activity to webhook with embed"""
    try:
        user = await bot.fetch_user(user_id)
        username = f"{user.name}#{user.discriminator}" if hasattr(user, 'discriminator') else user.name
    except:
        username = f"Unknown ({user_id})"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create embed for better formatting
    embed_data = {
        "title": f"📊 {action}",
        "description": f"**User:** {username} ({user_id})\n**Time:** {timestamp}",
        "color": 0x00ff00,  # Green
        "fields": []
    }
    
    if data:
        for key, value in data.items():
            embed_data["fields"].append({
                "name": key.replace("_", " ").title(),
                "value": str(value)[:1024],  # Discord field limit
                "inline": True
            })
    
    payload = {
        "embeds": [embed_data]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MAIN_WEBHOOK, json=payload) as resp:
                return resp.status == 200
    except Exception:
        # Fallback to text
        log_content = f"**{action}**\n**User:** {username} ({user_id})\n**Time:** {timestamp}"
        if data:
            log_content += f"\n**Data:** ```json\n{json.dumps(data, indent=2)}\n```"
        await send_webhook(MAIN_WEBHOOK, log_content)

# ==================== PLATFORM CHECKERS (Async Methods - No Blocking) ====================

class PlatformChecker:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        self.timeout = aiohttp.ClientTimeout(total=4)
    
    async def check(self, username):
        return "unknown", ["unsupported"]
    
    def confirm(self, signals):
        """Confirm status based on signals. Returns 'taken' if any taken signal, 'available' if 2+ available signals, otherwise 'unknown'"""
        if "taken" in signals:
            return "taken"
        if signals.count("available") >= 2:
            return "available"
        return "unknown"  # Changed from "taken" to "unknown" to allow retries
    
    async def async_get(self, url, headers=None, allow_redirects=True):
        """Async HTTP GET helper"""
        merged_headers = {**self.headers}
        if headers:
            merged_headers.update(headers)
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=merged_headers) as session:
                async with session.get(url, allow_redirects=allow_redirects) as resp:
                    text = await resp.text()
                    return resp, text
        except Exception as e:
            return None, None
    
    async def async_post(self, url, json_data=None, headers=None):
        """Async HTTP POST helper"""
        merged_headers = {**self.headers}
        if headers:
            merged_headers.update(headers)
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=merged_headers) as session:
                async with session.post(url, json=json_data) as resp:
                    text = await resp.text()
                    return resp, text
        except Exception as e:
            return None, None

class TikTokChecker(PlatformChecker):
    async def check(self, username):
        """Check TikTok - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Strongest API - user/detail (most reliable)
        try:
            url = f"https://www.tiktok.com/api/user/detail/?uniqueId={username}"
            r, text = await self.async_get(url)
            if r:
                logs.append(f"API:detail -> {r.status}")
                if r.status == 200:
                    try:
                        j = await r.json()
                        if j.get("userInfo") and j["userInfo"].get("user"):
                            signals.append("taken")
                            logs.append("✓ TAKEN")
                            if "taken" in signals:
                                return self.confirm(signals), logs
                        else:
                            signals.append("available")
                            logs.append("✓ AVAILABLE")
                    except:
                        pass
        except:
            logs.append("API:error")
        
        # Method 2: Web profile (backup) - only if no definitive answer
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url2 = f"https://www.tiktok.com/@{username}"
                r2, text2 = await self.async_get(url2)
                if r2:
                    logs.append(f"WEB:profile -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        if "Couldn't find" in text2 or "User not found" in text2:
                            signals.append("available")
                            logs.append("✓ AVAILABLE")
                        elif f"@{username.lower()}" in text2.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error")
        
        return self.confirm(signals), logs

class InstagramChecker(PlatformChecker):
    async def check(self, username):
        """Check Instagram - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Strongest API - web_profile_info (most reliable)
        try:
            api = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            r, text = await self.async_get(api, headers={"X-Requested-With": "XMLHttpRequest"})
            if r:
                logs.append(f"API:web_profile -> {r.status}")
                if r.status == 200:
                    try:
                        j = await r.json()
                        if j.get("data") and j["data"].get("user"):
                            signals.append("taken")
                            logs.append("✓ TAKEN")
                            if "taken" in signals:
                                return self.confirm(signals), logs
                        else:
                            signals.append("available")
                            logs.append("✓ AVAILABLE")
                    except:
                        if "\"user\"" in text.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
                            if "taken" in signals:
                                return self.confirm(signals), logs
        except:
            logs.append("API:error")
        
        # Method 2: Web profile (backup) - only if no definitive answer
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url = f"https://www.instagram.com/{username}/"
                r, text = await self.async_get(url)
                if r:
                    logs.append(f"WEB:profile -> {r.status}")
                    if r.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r.status == 200:
                        if "Sorry, this page isn't available" in text:
                            signals.append("available")
                            logs.append("✓ AVAILABLE")
                        elif f"\"username\":\"{username.lower()}\"" in text.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error")
        
        return self.confirm(signals), logs

class TwitterChecker(PlatformChecker):
    async def check(self, username):
        """Check Twitter/X - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Direct profile check (strongest)
        try:
            url = f"https://x.com/{username}"
            r, text = await self.async_get(url, allow_redirects=True)
            if r:
                logs.append(f"WEB:profile -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    if f"@{username.lower()}" in text.lower() or f'"{username.lower()}"' in text.lower():
                        signals.append("taken")
                        logs.append("✓ TAKEN")
                        if "taken" in signals:
                            return self.confirm(signals), logs
                    else:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
        except:
            logs.append("WEB:error")
        
        # Method 2: Alternative check (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url2 = f"https://twitter.com/{username}"
                r2, text2 = await self.async_get(url2, allow_redirects=True)
                if r2:
                    logs.append(f"WEB:twitter -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        if f"@{username.lower()}" in text2.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error2")
        
        return self.confirm(signals), logs

class YouTubeChecker(PlatformChecker):
    async def check(self, username):
        """Check YouTube - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Handle check (strongest)
        try:
            url = f"https://www.youtube.com/@{username}"
            r, text = await self.async_get(url)
            if r:
                logs.append(f"WEB:handle -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    if f"@{username.lower()}" in text.lower() or "channel" in text.lower():
                        signals.append("taken")
                        logs.append("✓ TAKEN")
                        if "taken" in signals:
                            return self.confirm(signals), logs
                    else:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
        except:
            logs.append("WEB:error")
        
        # Method 2: User check (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url2 = f"https://www.youtube.com/user/{username}"
                r2, text2 = await self.async_get(url2)
                if r2:
                    logs.append(f"WEB:user -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        if username.lower() in text2.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error2")
        
        return self.confirm(signals), logs

class TwitchChecker(PlatformChecker):
    async def check(self, username):
        """Check Twitch - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Profile check (strongest)
        try:
            url = f"https://www.twitch.tv/{username}"
            r, text = await self.async_get(url)
            if r:
                logs.append(f"WEB:profile -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    if "Unless you've got a time machine" in text or "doesn't exist" in text.lower():
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    else:
                        signals.append("taken")
                        logs.append("✓ TAKEN")
                        if "taken" in signals:
                            return self.confirm(signals), logs
        except:
            logs.append("WEB:error")
        
        # Method 2: API check (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                api = f"https://api.twitch.tv/helix/users?login={username}"
                r2, text2 = await self.async_get(api, headers={"Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko"})
                if r2:
                    logs.append(f"API:helix -> {r2.status}")
                    if r2.status == 200:
                        try:
                            j = await r2.json()
                            if j.get("data") and len(j["data"]) > 0:
                                signals.append("taken")
                                logs.append("✓ TAKEN")
                            else:
                                signals.append("available")
                                logs.append("✓ AVAILABLE")
                        except:
                            pass
            except:
                logs.append("API:error")
        
        return self.confirm(signals), logs

class RedditChecker(PlatformChecker):
    async def check(self, username):
        """Check Reddit - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Strongest API - about.json
        try:
            url = f"https://www.reddit.com/user/{username}/about.json"
            r, text = await self.async_get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r:
                logs.append(f"API:about -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    try:
                        j = await r.json()
                        if j.get("data") and j["data"].get("name"):
                            signals.append("taken")
                            logs.append("✓ TAKEN")
                            if "taken" in signals:
                                return self.confirm(signals), logs
                        else:
                            signals.append("available")
                            logs.append("✓ AVAILABLE")
                    except:
                        signals.append("taken")
                        logs.append("✓ TAKEN")
                        if "taken" in signals:
                            return self.confirm(signals), logs
        except:
            logs.append("API:error")
        
        # Method 2: Web profile (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url2 = f"https://www.reddit.com/user/{username}"
                r2, text2 = await self.async_get(url2)
                if r2:
                    logs.append(f"WEB:profile -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        if username.lower() in text2.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error")
        
        return self.confirm(signals), logs

class GitHubChecker(PlatformChecker):
    async def check(self, username):
        """Check GitHub - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Strongest API - GitHub REST API
        try:
            api = f"https://api.github.com/users/{username}"
            r, text = await self.async_get(api)
            if r:
                logs.append(f"API:users -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    signals.append("taken")
                    logs.append("✓ TAKEN")
                    if "taken" in signals:
                        return self.confirm(signals), logs
        except:
            logs.append("API:error")
        
        # Method 2: Web profile (backup) - only if no definitive answer
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url = f"https://github.com/{username}"
                r2, text2 = await self.async_get(url)
                if r2:
                    logs.append(f"WEB:profile -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        signals.append("taken")
                        logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error")
        
        return self.confirm(signals), logs

class PSNChecker(PlatformChecker):
    async def check(self, username):
        """Check PSN - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Strongest - psnprofiles direct
        try:
            url = f"https://psnprofiles.com/{username}"
            r, text = await self.async_get(url)
            if r:
                logs.append(f"WEB:psnprofiles -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    if "No users were found" in text or "doesn't exist" in text.lower():
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    else:
                        signals.append("taken")
                        logs.append("✓ TAKEN")
                        if "taken" in signals:
                            return self.confirm(signals), logs
        except:
            logs.append("WEB:error")
        
        # Method 2: playstation.com (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url2 = f"https://www.playstation.com/en-us/profile/{username}"
                r2, text2 = await self.async_get(url2)
                if r2:
                    logs.append(f"WEB:playstation -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        if username.lower() in text2.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error2")
        
        # Method 3: my.playstation.com (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url3 = f"https://my.playstation.com/profile/{username}"
                r3, text3 = await self.async_get(url3)
                if r3:
                    logs.append(f"WEB:myplaystation -> {r3.status}")
                    if r3.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
            except:
                logs.append("WEB:error3")
        
        return self.confirm(signals), logs

class XboxChecker(PlatformChecker):
    async def check(self, username):
        """Check Xbox - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: xboxgamertag.com (strongest)
        try:
            url = f"https://xboxgamertag.com/search/{username}"
            r, text = await self.async_get(url)
            if r:
                logs.append(f"WEB:gamertag -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    if "not found" in text.lower() or "doesn't exist" in text.lower():
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif "Gamertag" in text or username.lower() in text.lower():
                        signals.append("taken")
                        logs.append("✓ TAKEN")
                        if "taken" in signals:
                            return self.confirm(signals), logs
        except:
            logs.append("WEB:error")
        
        # Method 2: xbox.com profile (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url2 = f"https://account.xbox.com/en-us/profile?gamertag={username}"
                r2, text2 = await self.async_get(url2)
                if r2:
                    logs.append(f"WEB:xbox -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        if username.lower() in text2.lower():
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error2")
        
        return self.confirm(signals), logs

class SteamChecker(PlatformChecker):
    async def check(self, username):
        """Check Steam - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Custom URL (strongest)
        try:
            url = f"https://steamcommunity.com/id/{username}"
            r, text = await self.async_get(url)
            if r:
                logs.append(f"WEB:profile -> {r.status}")
                if r.status == 404:
                    signals.append("available")
                    logs.append("✓ AVAILABLE")
                elif r.status == 200:
                    if "could not be found" in text.lower() or "doesn't exist" in text.lower():
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    else:
                        signals.append("taken")
                        logs.append("✓ TAKEN")
                        if "taken" in signals:
                            return self.confirm(signals), logs
        except:
            logs.append("WEB:error")
        
        # Method 2: Profile search (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url2 = f"https://steamcommunity.com/profiles/{username}"
                r2, text2 = await self.async_get(url2)
                if r2:
                    logs.append(f"WEB:profiles -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
            except:
                logs.append("WEB:error2")
        
        return self.confirm(signals), logs

class RobloxChecker(PlatformChecker):
    async def check(self, username):
        """Check Roblox - tries multiple methods until definitive answer"""
        logs = []
        signals = []
        
        # Method 1: Strongest API - get-by-username
        try:
            api = f"https://api.roblox.com/users/get-by-username?username={username}"
            r, text = await self.async_get(api)
            if r:
                logs.append(f"API:get-by-username -> {r.status}")
                if r.status == 200:
                    try:
                        j = await r.json()
                        if j.get("Id"):
                            signals.append("taken")
                            logs.append("✓ TAKEN")
                            if "taken" in signals:
                                return self.confirm(signals), logs
                        else:
                            signals.append("available")
                            logs.append("✓ AVAILABLE")
                    except:
                        pass
        except:
            logs.append("API:error")
        
        # Method 2: Web profile (backup) - only if no definitive answer
        if "taken" not in signals and signals.count("available") < 2:
            try:
                url = f"https://www.roblox.com/users/profile?username={username}"
                r2, text2 = await self.async_get(url)
                if r2:
                    logs.append(f"WEB:profile -> {r2.status}")
                    if r2.status == 404:
                        signals.append("available")
                        logs.append("✓ AVAILABLE")
                    elif r2.status == 200:
                        if "not found" in text2.lower() or "doesn't exist" in text2.lower():
                            signals.append("available")
                            logs.append("✓ AVAILABLE")
                        else:
                            signals.append("taken")
                            logs.append("✓ TAKEN")
            except:
                logs.append("WEB:error")
        
        # Method 3: Users API (backup)
        if "taken" not in signals and signals.count("available") < 2:
            try:
                api2 = f"https://users.roblox.com/v1/usernames/users"
                r3, text3 = await self.async_post(api2, json_data={"usernames": [username]})
                if r3:
                    logs.append(f"API:users -> {r3.status}")
                    if r3.status == 200:
                        try:
                            j = await r3.json()
                            if j.get("data") and len(j["data"]) > 0:
                                signals.append("taken")
                                logs.append("✓ TAKEN")
                            else:
                                signals.append("available")
                                logs.append("✓ AVAILABLE")
                        except:
                            pass
            except:
                logs.append("API:error2")
        
        return self.confirm(signals), logs

class EpicGamesChecker(PlatformChecker):
    async def check(self, username):
        logs = []
        signals = []
        try:
            url = f"https://www.epicgames.com/account/personal?productName=&lang=en"
            # Epic Games doesn't have a direct username check API, so we check via account page
            # This is a placeholder - Epic Games requires authentication
            logs.append("Epic Games requires authentication for username check")
            signals.append("unknown")
        except Exception as e:
            logs.append(f"error: {e}")
        return self.confirm(signals), logs

class DiscordChecker(PlatformChecker):
    async def check(self, username):
        logs = []
        signals = []
        try:
            # Discord username check via API (requires token, but we can try public endpoints)
            url = f"https://discord.com/api/v9/users/@me"
            # This requires authentication, so we return unknown
            logs.append("Discord handle availability requires authenticated API")
            # Try alternative: check if username format is valid
            if len(username) >= 2 and len(username) <= 32 and username.replace('_', '').replace('.', '').isalnum():
                logs.append("username format valid")
            else:
                logs.append("username format invalid")
        except Exception as e:
            logs.append(f"error: {e}")
        return "unknown", logs

PLATFORMS = {
    "TikTok": TikTokChecker,
    "Instagram": InstagramChecker,
    "X (Twitter)": TwitterChecker,
    "YouTube": YouTubeChecker,
    "Twitch": TwitchChecker,
    "Reddit": RedditChecker,
    "GitHub": GitHubChecker,
    "PSN": PSNChecker,
    "Xbox": XboxChecker,
    "Steam": SteamChecker,
    "Roblox": RobloxChecker,
    "Epic Games": EpicGamesChecker,
    "Discord": DiscordChecker,
}

def generate_username(length, mode):
    if mode == "Letters":
        pool = string.ascii_lowercase
    else:
        pool = string.ascii_lowercase + string.digits
    return "".join(random.choice(pool) for _ in range(length))

# ==================== NAME SNIFFER VIEW ====================

class NameSnifferView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.settings = {
            "platform": "TikTok",
            "length": 3,
            "charset": "Letters",
            "max_checks": 100,
            "delay": 0.3,
            "timeout": 8,
            "retries": 3,
            "webhook": MAIN_WEBHOOK
        }
    
    @discord.ui.select(
        placeholder="Select Platform",
        options=[
            discord.SelectOption(label="TikTok", value="TikTok", emoji="🎵"),
            discord.SelectOption(label="Instagram", value="Instagram", emoji="📷"),
            discord.SelectOption(label="X (Twitter)", value="X (Twitter)", emoji="🐦"),
            discord.SelectOption(label="YouTube", value="YouTube", emoji="📺"),
            discord.SelectOption(label="Twitch", value="Twitch", emoji="🎮"),
            discord.SelectOption(label="Reddit", value="Reddit", emoji="🤖"),
            discord.SelectOption(label="GitHub", value="GitHub", emoji="💻"),
            discord.SelectOption(label="PSN", value="PSN", emoji="🎮"),
            discord.SelectOption(label="Xbox", value="Xbox", emoji="🎮"),
            discord.SelectOption(label="Steam", value="Steam", emoji="🎮"),
            discord.SelectOption(label="Roblox", value="Roblox", emoji="🎮"),
            discord.SelectOption(label="Epic Games", value="Epic Games", emoji="🎮"),
            discord.SelectOption(label="Discord", value="Discord", emoji="💬"),
        ],
        row=0
    )
    async def platform_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
            return
        self.settings["platform"] = select.values[0]
        await interaction.response.edit_message(embed=create_name_sniffer_embed(self.settings), view=self)
    
    @discord.ui.select(
        placeholder="Select Length",
        options=[
            discord.SelectOption(label="3 characters", value="3"),
            discord.SelectOption(label="4 characters", value="4"),
            discord.SelectOption(label="5 characters", value="5"),
        ],
        row=1
    )
    async def length_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
            return
        self.settings["length"] = int(select.values[0])
        await interaction.response.edit_message(embed=create_name_sniffer_embed(self.settings), view=self)
    
    @discord.ui.select(
        placeholder="Select Charset",
        options=[
            discord.SelectOption(label="Letters only", value="Letters"),
            discord.SelectOption(label="Letters + Numbers", value="Letters+Numbers"),
        ],
        row=2
    )
    async def charset_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
            return
        self.settings["charset"] = select.values[0]
        await interaction.response.edit_message(embed=create_name_sniffer_embed(self.settings), view=self)
    
    @discord.ui.select(
        placeholder="Max Checks",
        options=[
            discord.SelectOption(label="50 checks", value="50"),
            discord.SelectOption(label="100 checks", value="100"),
            discord.SelectOption(label="250 checks", value="250"),
            discord.SelectOption(label="500 checks", value="500"),
            discord.SelectOption(label="1000 checks", value="1000"),
            discord.SelectOption(label="2500 checks", value="2500"),
            discord.SelectOption(label="5000 checks", value="5000"),
        ],
        row=3
    )
    async def max_checks_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
            return
        self.settings["max_checks"] = int(select.values[0])
        await interaction.response.edit_message(embed=create_name_sniffer_embed(self.settings), view=self)
    
    @discord.ui.button(label="⚙️ Advanced", style=discord.ButtonStyle.secondary, row=4)
    async def advanced_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
            return
        modal = AdvancedSettingsModal(self.settings, self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="▶️ Start Scan", style=discord.ButtonStyle.success, row=4)
    async def start_scan_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ Starting scan on **{self.settings['platform']}**...", ephemeral=True)
        asyncio.create_task(run_name_scan_interactive(interaction, self.settings))
    
    @discord.ui.button(label="⏹️ Stop Scan", style=discord.ButtonStyle.danger, row=4)
    async def stop_scan_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
            return
        scan_id = f"{self.user_id}_scan"
        if scan_id in active_scans:
            active_scans[scan_id]["running"] = False
            await interaction.response.send_message("✅ Scan stopped", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No active scan found", ephemeral=True)

# ==================== MODALS ====================

class AdvancedSettingsModal(Modal):
    def __init__(self, settings, parent_view):
        super().__init__(title="Advanced Settings")
        self.settings = settings
        self.parent_view = parent_view
        self.delay_input = TextInput(
            label="Delay Between Checks (seconds)",
            placeholder="0.3",
            default=str(settings.get("delay", 0.3)),
            required=False,
            max_length=4
        )
        self.timeout_input = TextInput(
            label="Request Timeout (seconds)",
            placeholder="8",
            default=str(settings.get("timeout", 8)),
            required=False,
            max_length=2
        )
        self.add_item(self.delay_input)
        self.add_item(self.timeout_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Update delay
            delay_val = float(self.delay_input.value.strip())
            if 0.1 <= delay_val <= 5.0:
                self.settings["delay"] = delay_val
            else:
                await interaction.response.send_message("❌ Delay must be between 0.1 and 5.0 seconds", ephemeral=True)
                return
            
            # Update timeout
            timeout_val = int(self.timeout_input.value.strip())
            if 5 <= timeout_val <= 30:
                self.settings["timeout"] = timeout_val
            else:
                await interaction.response.send_message("❌ Timeout must be between 5 and 30 seconds", ephemeral=True)
                return
            
            await interaction.response.send_message(f"✅ Settings updated: Delay={delay_val}s, Timeout={timeout_val}s", ephemeral=True)
            # Try to update the original message if it's not ephemeral
            try:
                if interaction.message and not interaction.message.flags.ephemeral:
                    await interaction.message.edit(embed=create_name_sniffer_embed(self.settings), view=self.parent_view)
            except:
                pass  # Message might not be editable, that's okay
        except ValueError:
            await interaction.response.send_message("❌ Invalid value. Delay must be a number (e.g., 0.3), Timeout must be an integer (e.g., 8)", ephemeral=True)

# ==================== EMBED CREATORS ====================

def create_name_sniffer_embed(settings=None):
    if settings is None:
        settings = {
            "platform": "TikTok",
            "length": 3,
            "charset": "Letters",
            "max_checks": 100,
            "delay": 0.3,
            "timeout": 8,
        }
    
    embed = discord.Embed(
        title="🔍 Name Sniffer - Configuration",
        description="Configure your username scanning settings:",
        color=discord.Color.green()
    )
    embed.add_field(name="Platform", value=settings["platform"], inline=True)
    embed.add_field(name="Length", value=str(settings["length"]), inline=True)
    embed.add_field(name="Charset", value=settings["charset"], inline=True)
    embed.add_field(name="Max Checks", value=str(settings["max_checks"]), inline=True)
    embed.add_field(name="Delay", value=f"{settings['delay']}s", inline=True)
    embed.add_field(name="Timeout", value=f"{settings['timeout']}s", inline=True)
    embed.set_footer(text="Use the dropdowns above to configure, then click Start Scan")
    return embed

# ==================== SCANNING FUNCTIONS ====================

async def check_username_with_retries(checker, username, max_retries=8):
    """Check username with retries until definitive answer - async optimized"""
    status = "unknown"
    logs = []
    for attempt in range(max_retries):
        try:
            status, attempt_logs = await checker.check(username)
            logs.extend(attempt_logs)
            if status in ("taken", "available"):
                return status, logs
            # If unknown, retry with minimal delay
            if attempt < max_retries - 1:
                await asyncio.sleep(0.05)  # Very fast retry
        except Exception as e:
            logs.append(f"Retry:{attempt+1}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.05)
    # Final attempt
    if status == "unknown":
        try:
            status, final_logs = await checker.check(username)
            logs.extend(final_logs)
        except:
            pass
    return status, logs

async def run_name_scan_interactive(interaction, settings):
    """Run name scan with interactive updates, live logging, and downloadable results"""
    scan_id = f"{interaction.user.id}_scan"
    checker = PLATFORMS[settings["platform"]]()
    available_names = []
    taken_count = 0
    checked_names = []
    
    # Create status message
    status_embed = discord.Embed(
        title=f"🔍 Scanning {settings['platform']}",
        description=f"✅ Available: 0\n❌ Taken: 0\n🔍 Checked: 0/{settings['max_checks']}",
        color=discord.Color.blue()
    )
    status_msg = await interaction.channel.send(embed=status_embed)
    
    # Create live log message
    log_embed = discord.Embed(
        title="📋 Live Check Log",
        description="```\nWaiting for checks...\n```",
        color=discord.Color.blue()
    )
    log_msg = await interaction.channel.send(embed=log_embed)
    
    # Create available names message
    available_embed = discord.Embed(
        title=f"✅ Available Names - {settings['platform']}",
        description="```\nNo available names found yet...\n```",
        color=discord.Color.green()
    )
    available_msg = await interaction.channel.send(embed=available_embed)
    
    active_scans[scan_id] = {"running": True, "user": interaction.user.id}
    scan_logs[scan_id] = []
    
    last_log_update = time.time()
    log_buffer = []
    
    for count in range(settings["max_checks"]):
        if not active_scans.get(scan_id, {}).get("running", False):
            break
        
        name = generate_username(settings["length"], settings["charset"])
        
        # Show live progress - checking
        timestamp = datetime.now().strftime("%H:%M:%S")
        progress_pct = int((count + 1) / settings['max_checks'] * 100)
        
        # Use retry wrapper to ensure definitive answer - keeps trying until confirmed (async)
        status, logs = await check_username_with_retries(checker, name, max_retries=8)
        
        # Simplified log entry with method info
        method_info = " | ".join([log.split("->")[0].strip() if "->" in log else log.split(":")[0].strip() if ":" in log else "" for log in logs[:2]])
        log_entry = f"[{timestamp}] {name} | {method_info} | {status.upper()}"
        checked_names.append((name, status, timestamp))
        scan_logs[scan_id].append(log_entry)
        log_buffer.append(log_entry)
        
        if status == "available":
            available_names.append(name)
            # Update available names message
            names_text = "\n".join([f"`{name}`" for name in available_names[-50:]])  # Last 50
            if len(available_names) > 50:
                names_text = f"... {len(available_names) - 50} more names above ...\n" + names_text
            available_embed.description = f"```\n{names_text}\n```"
            available_embed.set_footer(text=f"Total: {len(available_names)} available names")
            await available_msg.edit(embed=available_embed)
            
            # Send individual notification
            embed = discord.Embed(
                title=f"✅ Available: `{name}`",
                description=f"Platform: {settings['platform']}\nFound at {timestamp}",
                color=discord.Color.green()
            )
            await interaction.channel.send(embed=embed)
            
            # Send to webhook silently
            if settings.get("webhook"):
                content = f"✅ **Available Username Found!**\n\n**Platform:** {settings['platform']}\n**Username:** `{name}`\n**Time:** {timestamp}"
                await send_webhook(settings["webhook"], content)
        elif status == "taken":
            taken_count += 1
        
        # Update status every check (live progress)
        progress_pct = int((count + 1) / settings['max_checks'] * 100)
        progress_bar = "█" * (progress_pct // 5) + "░" * (20 - progress_pct // 5)
        status_embed.description = (
            f"✅ Available: **{len(available_names)}**\n"
            f"❌ Taken: **{taken_count}**\n"
            f"🔍 Checked: **{count+1}/{settings['max_checks']}** ({progress_pct}%)\n"
            f"`{progress_bar}`\n"
            f"⏱️ Current: `{name}` → **{status.upper()}**"
        )
        await status_msg.edit(embed=status_embed)
        
        # Update log every check (live logging)
        if log_buffer:
            log_text = "\n".join(log_buffer[-15:])  # Last 15 entries
            log_embed.description = f"```\n{log_text}\n```"
            await log_msg.edit(embed=log_embed)
            if len(log_buffer) >= 15:
                log_buffer.pop(0)  # Keep buffer size manageable
        
        await asyncio.sleep(settings["delay"])
    
    # Final summary
    final_embed = discord.Embed(
        title=f"📊 Scan Complete - {settings['platform']}",
        description=f"✅ Available: {len(available_names)}\n❌ Taken: {taken_count}\n🔍 Total Checked: {count+1}",
        color=discord.Color.gold()
    )
    if available_names:
        names_text = "\n".join([f"`{name}`" for name in available_names[:30]])
        if len(available_names) > 30:
            names_text += f"\n... and {len(available_names) - 30} more"
        final_embed.add_field(name="Available Names", value=names_text, inline=False)
    
    await status_msg.edit(embed=final_embed)
    
    # Create downloadable files
    if available_names:
        # Create names file
        names_content = "\n".join(available_names)
        names_file = discord.File(fp=BytesIO(names_content.encode('utf-8')), filename=f"available_names_{settings['platform']}.txt")
        
        # Create full log file
        log_content = "\n".join(scan_logs[scan_id])
        log_file = discord.File(fp=BytesIO(log_content.encode('utf-8')), filename=f"scan_log_{settings['platform']}.txt")
        
        # Create organized JSON file
        json_data = {
            "platform": settings["platform"],
            "scan_date": datetime.now().isoformat(),
            "total_checked": count + 1,
            "available_count": len(available_names),
            "taken_count": taken_count,
            "available_names": available_names,
            "checked_names": [{"name": n, "status": s, "time": t} for n, s, t in checked_names]
        }
        json_content = json.dumps(json_data, indent=2)
        json_file = discord.File(fp=BytesIO(json_content.encode('utf-8')), filename=f"scan_results_{settings['platform']}.json")
        
        download_embed = discord.Embed(
            title="📥 Download Results",
            description="Download available names and logs:",
            color=discord.Color.blue()
        )
        download_embed.add_field(name="Files", value="• Available Names (TXT)\n• Full Scan Log (TXT)\n• Organized Results (JSON)", inline=False)
        await interaction.channel.send(embed=download_embed, files=[names_file, log_file, json_file])
    
    if scan_id in active_scans:
        del active_scans[scan_id]
    if scan_id in scan_logs:
        del scan_logs[scan_id]

async def send_webhook(webhook_url, content):
    """Send message to webhook"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"content": content}
            async with session.post(webhook_url, json=payload) as resp:
                return resp.status == 200
    except Exception:
        return False

# ==================== BOT EVENTS ====================

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print("\n" + "="*60)
    print("TERMINAL CONTROLS:")
    print("1 - Restart bot")
    print("2 - Shutdown bot")
    print("3 - List all servers bot is in")
    print("4 - Remove bot from server")
    print("5 - Assign premium key to user")
    print("6 - List all premium keys")
    print("7 - Revoke premium key")
    print("8 - Assign CloudTouch access to user")
    print("9 - List all CloudTouch access")
    print("10 - Revoke CloudTouch access from user")
    print("11 - Hard scan user (gather all info)")
    print("="*60 + "\n")

# ==================== MAIN COMMAND ====================

# ==================== PREMIUM ACCESS CHECK ====================

def check_premium():
    """Decorator to check premium access"""
    async def predicate(interaction: discord.Interaction):
        user_id = interaction.user.id
        
        # Check role (fallback)
        if isinstance(interaction.user, discord.Member):
            if interaction.user.get_role(TESTER_ROLE_ID):
                return True
        
        # Check key
        has_access, key = has_premium_access(user_id)
        if has_access:
            return True
        
        return False
    return app_commands.check(predicate)

@bot.tree.command(name="namesniffer", description="Open Name Sniffer - Check username availability [PREMIUM]")
@check_premium()
async def namesniffer(interaction: discord.Interaction):
    """Main command to open the Name Sniffer - Premium only"""
    # Track user data and log usage
    user_data = load_user_data()
    user_id_str = str(interaction.user.id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "user_id": user_id_str,
            "username": f"{interaction.user.name}#{interaction.user.discriminator}" if hasattr(interaction.user, 'discriminator') else interaction.user.name,
            "key": None,
            "first_used": datetime.now().isoformat(),
            "usage_count": 0,
            "last_used": None,
            "ip_addresses": [],
            "ipv6_addresses": [],
            "hwid": None,
            "commands_used": [],
            "guild_ids": [],
            "channel_ids": []
        }
    
    user_data[user_id_str]["usage_count"] = user_data[user_id_str].get("usage_count", 0) + 1
    user_data[user_id_str]["last_used"] = datetime.now().isoformat()
    user_data[user_id_str]["username"] = f"{interaction.user.name}#{interaction.user.discriminator}" if hasattr(interaction.user, 'discriminator') else interaction.user.name
    if "namesniffer" not in user_data[user_id_str].get("commands_used", []):
        user_data[user_id_str].setdefault("commands_used", []).append("namesniffer")
    
    # Get key info
    has_access, key = has_premium_access(interaction.user.id)
    if key:
        user_data[user_id_str]["key"] = key
    
    # Track guild/channel IDs (proxy for location tracking)
    try:
        if interaction.guild:
            if str(interaction.guild.id) not in user_data[user_id_str].get("guild_ids", []):
                user_data[user_id_str].setdefault("guild_ids", []).append(str(interaction.guild.id))
        if interaction.channel:
            if str(interaction.channel.id) not in user_data[user_id_str].get("channel_ids", []):
                user_data[user_id_str].setdefault("channel_ids", []).append(str(interaction.channel.id))
    except:
        pass
    
    save_user_data(user_data)
    
    # Log to webhook with full user data including HWID/IP tracking
    await log_to_webhook(interaction.user.id, "Name Sniffer Used", {
        "command": "namesniffer",
        "user_id": user_id_str,
        "username": user_data[user_id_str]["username"],
        "usage_count": user_data[user_id_str]["usage_count"],
        "key": key,
        "total_commands": len(user_data[user_id_str].get("commands_used", [])),
        "first_used": user_data[user_id_str].get("first_used"),
        "last_used": user_data[user_id_str].get("last_used"),
        "hwid": user_data[user_id_str].get("hwid"),
        "ip_addresses": user_data[user_id_str].get("ip_addresses", []),
        "ipv6_addresses": user_data[user_id_str].get("ipv6_addresses", []),
        "guild_ids": user_data[user_id_str].get("guild_ids", []),
        "channel_ids": user_data[user_id_str].get("channel_ids", [])
    })
    
    embed = create_name_sniffer_embed()
    view = NameSnifferView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@namesniffer.error
async def namesniffer_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        embed = discord.Embed(
            title="🔒 Premium Access Required",
            description="This command requires a premium key.\n\n**How to get access:**\n• Purchase premium using `/payment` (Owner only)\n• Receive a key from an administrator\n• Have the Tester role assigned",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stop", description="Stop your active name scan [PREMIUM]")
@check_premium()
async def stop_scan(interaction: discord.Interaction):
    """Stop active scan for user - Premium only"""
    scan_id = f"{interaction.user.id}_scan"
    if scan_id in active_scans:
        active_scans[scan_id]["running"] = False
        await interaction.response.send_message("✅ Your scan has been stopped.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ No active scan found for you.", ephemeral=True)

@stop_scan.error
async def stop_scan_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        embed = discord.Embed(
            title="🔒 Premium Access Required",
            description="This command requires a premium key.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== PAYMENT COMMAND ====================

class PaymentModal(Modal):
    def __init__(self):
        super().__init__(title="Premium Payment")
        self.amount_input = TextInput(
            label="Amount ($)",
            placeholder="Enter amount",
            default="10.00",
            required=True
        )
        self.apple_pay_input = TextInput(
            label="Apple Pay Number",
            placeholder=APPLE_PAY_NUMBER,
            default=APPLE_PAY_NUMBER,
            required=True
        )
        self.add_item(self.amount_input)
        self.add_item(self.apple_pay_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        amount = self.amount_input.value
        apple_pay = self.apple_pay_input.value
        
        embed = discord.Embed(
            title="💳 Payment Information",
            description=f"**Amount:** ${amount}\n**Apple Pay:** {apple_pay}\n\nSend the payment to the Apple Pay number above, then contact an administrator to receive your premium key.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log payment attempt
        await log_to_webhook(interaction.user.id, "Payment Attempt", {
            "amount": amount,
            "apple_pay": apple_pay
        })

# ==================== PERMANENT PAYMENT GUI ====================

class PermanentPaymentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="💳 Purchase Premium", style=discord.ButtonStyle.success, row=0)
    async def purchase_button(self, interaction: discord.Interaction, button: Button):
        # Check owner role
        if isinstance(interaction.user, discord.Member):
            if not interaction.user.get_role(OWNER_ROLE_ID):
                await interaction.response.send_message("❌ This command is only available to owners.", ephemeral=True)
                return
        
        modal = PaymentModal()
        await interaction.response.send_modal(modal)

class CloudTouchPaymentView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="💳 Purchase CloudTouch", style=discord.ButtonStyle.success, row=0)
    async def purchase_button(self, interaction: discord.Interaction, button: Button):
        # Check owner role
        if isinstance(interaction.user, discord.Member):
            if not interaction.user.get_role(OWNER_ROLE_ID):
                await interaction.response.send_message("❌ This command is only available to owners.", ephemeral=True)
                return
        
        modal = CloudTouchPaymentModal()
        await interaction.response.send_modal(modal)

class CloudTouchPaymentModal(Modal):
    def __init__(self):
        super().__init__(title="CloudTouch Payment")
        self.amount_input = TextInput(
            label="Amount ($)",
            placeholder="Enter amount",
            default="25.00",
            required=True
        )
        self.apple_pay_input = TextInput(
            label="Apple Pay Number",
            placeholder=APPLE_PAY_NUMBER,
            default=APPLE_PAY_NUMBER,
            required=True
        )
        self.add_item(self.amount_input)
        self.add_item(self.apple_pay_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        amount = self.amount_input.value
        apple_pay = self.apple_pay_input.value
        
        embed = discord.Embed(
            title="💳 CloudTouch Payment Information",
            description=f"**Amount:** ${amount}\n**Apple Pay:** {apple_pay}\n\nSend the payment to the Apple Pay number above, then contact an administrator to receive your CloudTouch access.",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log payment attempt
        await log_to_webhook(interaction.user.id, "CloudTouch Payment Attempt", {
            "amount": amount,
            "apple_pay": apple_pay
        })

@bot.tree.command(name="payment", description="Purchase premium access [OWNER ONLY]")
async def payment(interaction: discord.Interaction):
    """Payment command - Owner only"""
    # Check owner role
    if isinstance(interaction.user, discord.Member):
        if not interaction.user.get_role(OWNER_ROLE_ID):
            await interaction.response.send_message("❌ This command is only available to owners.", ephemeral=True)
            return
    
    # Send permanent payment GUI to channel (visible to everyone)
    embed = discord.Embed(
        title="💳 Premium Payment",
        description="**Purchase premium access to use the Name Sniffer bot!**\n\nClick the button below to open the payment form.",
        color=discord.Color.gold()
    )
    embed.add_field(name="💰 Price", value="Contact owner for pricing", inline=True)
    embed.add_field(name="📱 Payment Method", value=f"Apple Pay: `{APPLE_PAY_NUMBER}`", inline=True)
    embed.add_field(name="✅ Benefits", value="• Unlimited name checks\n• All platforms\n• Priority support", inline=False)
    embed.set_footer(text="This message is permanent - visible to everyone")
    
    view = PermanentPaymentView()
    await interaction.response.send_message(embed=embed, view=view)
    
    # Log payment GUI creation
    await log_to_webhook(interaction.user.id, "Payment GUI Created", {
        "channel_id": interaction.channel.id,
        "guild_id": interaction.guild.id if interaction.guild else None
    })

@bot.tree.command(name="cloudtouch-payment", description="Purchase CloudTouch tool access [OWNER ONLY]")
async def cloudtouch_payment(interaction: discord.Interaction):
    """CloudTouch payment command - Owner only"""
    # Check owner role
    if isinstance(interaction.user, discord.Member):
        if not interaction.user.get_role(OWNER_ROLE_ID):
            await interaction.response.send_message("❌ This command is only available to owners.", ephemeral=True)
            return
    
    # Send permanent payment GUI to channel (visible to everyone)
    embed = discord.Embed(
        title="💻 CloudTouch Tool Payment",
        description="**Purchase access to the CloudTouch premium tool!**\n\nClick the button below to open the payment form.",
        color=discord.Color.blue()
    )
    embed.add_field(name="💰 Price", value="Contact owner for pricing", inline=True)
    embed.add_field(name="📱 Payment Method", value=f"Apple Pay: `{APPLE_PAY_NUMBER}`", inline=True)
    embed.add_field(name="✅ Benefits", value="• Full CloudTouch tool access\n• All premium features\n• Lifetime access", inline=False)
    embed.set_footer(text="This message is permanent - visible to everyone")
    
    view = CloudTouchPaymentView()
    await interaction.response.send_message(embed=embed, view=view)
    
    # Log payment GUI creation
    await log_to_webhook(interaction.user.id, "CloudTouch Payment GUI Created", {
        "channel_id": interaction.channel.id,
        "guild_id": interaction.guild.id if interaction.guild else None
    })

# ==================== TERMINAL CONTROLS ====================

def terminal_control_loop():
    """Handle terminal input for bot controls"""
    global bot_should_restart, bot_should_shutdown
    
    # Wait for bot to be ready
    while not bot.is_ready():
        time.sleep(0.5)
    
    while True:
        try:
            choice = input("\nEnter command (1-11): ").strip()
            
            if choice == "1":
                print("🔄 Restarting bot...")
                bot_should_restart = True
                if bot.loop and bot.loop.is_running():
                    asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
                else:
                    bot.close()
                
            elif choice == "2":
                print("🛑 Shutting down bot...")
                bot_should_shutdown = True
                if bot.loop and bot.loop.is_running():
                    asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
                else:
                    bot.close()
                
            elif choice == "3":
                print("\n📋 Servers bot is in:")
                print("-" * 60)
                if bot.is_ready():
                    guilds = list(bot.guilds)
                    if not guilds:
                        print("Bot is not in any servers.")
                    else:
                        for i, guild in enumerate(guilds, 1):
                            print(f"{i}. {guild.name} (ID: {guild.id}) - {guild.member_count} members")
                else:
                    print("Bot is not ready yet. Please wait...")
                print("-" * 60)
                
            elif choice == "4":
                if not bot.is_ready():
                    print("❌ Bot is not ready yet. Please wait...")
                    continue
                guild_id_input = input("Enter Guild/Server ID to leave: ").strip()
                try:
                    guild_id = int(guild_id_input)
                    guild = bot.get_guild(guild_id)
                    if guild:
                        print(f"🚪 Leaving server: {guild.name} (ID: {guild_id})...")
                        if bot.loop and bot.loop.is_running():
                            asyncio.run_coroutine_threadsafe(guild.leave(), bot.loop)
                        else:
                            asyncio.run(guild.leave())
                        print(f"✅ Left server: {guild.name}")
                    else:
                        print(f"❌ Server with ID {guild_id} not found.")
                except ValueError:
                    print("❌ Invalid server ID. Please enter a number.")
                except Exception as e:
                    print(f"❌ Error leaving server: {e}")
            
            elif choice == "5":
                if not bot.is_ready():
                    print("❌ Bot is not ready yet. Please wait...")
                    continue
                user_id_input = input("Enter Discord User ID to assign key: ").strip()
                try:
                    user_id = int(user_id_input)
                    keys_data = load_keys()
                    
                    # Generate new key
                    new_key = generate_key()
                    keys_data[new_key] = {
                        "user_id": str(user_id),
                        "created_at": datetime.now().isoformat(),
                        "created_by": "terminal"
                    }
                    save_keys(keys_data)
                    
                    # Assign tester role and send DM (async)
                    async def assign_key_async():
                        try:
                            user = await bot.fetch_user(user_id)
                            # Find user in all guilds and assign role
                            for guild in bot.guilds:
                                member = guild.get_member(user_id)
                                if member:
                                    role = guild.get_role(TESTER_ROLE_ID)
                                    if role:
                                        await member.add_roles(role)
                                        print(f"✅ Assigned tester role in {guild.name}")
                        except Exception as e:
                            print(f"⚠️ Could not assign role: {e}")
                        
                        # Send DM to user
                        try:
                            user = await bot.fetch_user(user_id)
                            embed = discord.Embed(
                                title="🔑 Premium Key Assigned",
                                description=f"Congratulations! You have been awarded a premium key for the Name Sniffer bot.\n\n**Your Key:** `{new_key}`\n\nYou can now use all premium commands!",
                                color=discord.Color.green()
                            )
                            await user.send(embed=embed)
                            print(f"✅ Sent DM to {user.name}")
                        except Exception as e:
                            print(f"⚠️ Could not send DM: {e}")
                        
                        # Log to webhook
                        await log_to_webhook(user_id, "Key Assigned", {
                            "key": new_key,
                            "assigned_by": "terminal"
                        })
                    
                    if bot.loop and bot.loop.is_running():
                        asyncio.run_coroutine_threadsafe(assign_key_async(), bot.loop)
                    else:
                        asyncio.run(assign_key_async())
                    
                    print(f"✅ Key {new_key} assigned to user {user_id}")
                except ValueError:
                    print("❌ Invalid user ID. Please enter a number.")
                except Exception as e:
                    print(f"❌ Error assigning key: {e}")
            
            elif choice == "6":
                keys_data = load_keys()
                print("\n📋 Premium Keys:")
                print("-" * 60)
                if not keys_data:
                    print("No keys assigned.")
                else:
                    for key, data in keys_data.items():
                        user_id = data.get("user_id", "Unknown")
                        created = data.get("created_at", "Unknown")
                        print(f"Key: {key}")
                        print(f"  User ID: {user_id}")
                        print(f"  Created: {created}")
                        print()
                print("-" * 60)
            
            elif choice == "7":
                key_input = input("Enter key to revoke: ").strip()
                keys_data = load_keys()
                if key_input in keys_data:
                    user_id = keys_data[key_input].get("user_id")
                    del keys_data[key_input]
                    save_keys(keys_data)
                    
                    # Remove tester role (async)
                    async def revoke_key_async():
                        try:
                            for guild in bot.guilds:
                                member = guild.get_member(int(user_id))
                                if member:
                                    role = guild.get_role(TESTER_ROLE_ID)
                                    if role:
                                        await member.remove_roles(role)
                                        print(f"✅ Removed tester role in {guild.name}")
                        except:
                            pass
                        
                        # Log to webhook
                        await log_to_webhook(int(user_id), "Key Revoked", {
                            "key": key_input
                        })
                    
                    if bot.loop and bot.loop.is_running():
                        asyncio.run_coroutine_threadsafe(revoke_key_async(), bot.loop)
                    else:
                        asyncio.run(revoke_key_async())
                    
                    print(f"✅ Key {key_input} revoked")
                else:
                    print("❌ Key not found.")
            
            elif choice == "8":
                if not bot.is_ready():
                    print("❌ Bot is not ready yet. Please wait...")
                    continue
                user_id_input = input("Enter Discord User ID to grant CloudTouch access: ").strip()
                try:
                    user_id = int(user_id_input)
                    access_data = load_cloudtouch_access()
                    
                    if str(user_id) in access_data:
                        print(f"⚠️ User {user_id} already has CloudTouch access.")
                        continue
                    
                    access_data[str(user_id)] = {
                        "granted_at": datetime.now().isoformat(),
                        "granted_by": "terminal",
                        "download_link": CLOUDTOUCH_DOWNLOAD_LINK
                    }
                    save_cloudtouch_access(access_data)
                    
                    # Update Vercel API
                    try:
                        import requests
                        requests.post(f"{VERCEL_API_URL}/update_access", 
                                    json={"user_id": str(user_id), "action": "grant", "download_link": CLOUDTOUCH_DOWNLOAD_LINK}, 
                                    timeout=5)
                    except Exception as e:
                        print(f"⚠️ Could not update Vercel API: {e}")
                    
                    # Send DM to user (async)
                    async def grant_access_async():
                        try:
                            user = await bot.fetch_user(user_id)
                            embed = discord.Embed(
                                title="💻 CloudTouch Access Granted!",
                                description=f"Congratulations! You have been granted access to the CloudTouch premium tool.\n\n**Download Link:**\n{CLOUDTOUCH_DOWNLOAD_LINK}\n\n**Instructions:**\n1. Download the tool using the link above\n2. Run the tool\n3. Enter your Discord ID when prompted: `{user_id}`\n\nEnjoy your premium access!",
                                color=discord.Color.green()
                            )
                            await user.send(embed=embed)
                            print(f"✅ Sent DM to {user.name}")
                        except Exception as e:
                            print(f"⚠️ Could not send DM: {e}")
                        
                        # Log to webhook
                        await log_to_webhook(user_id, "CloudTouch Access Granted", {
                            "granted_by": "terminal",
                            "download_link": CLOUDTOUCH_DOWNLOAD_LINK,
                            "user_id": str(user_id)
                        })
                        
                        # Update Vercel API (live update)
                        try:
                            import requests
                            requests.post(f"{VERCEL_API_URL}/update_access", 
                                        json={"user_id": str(user_id), "action": "grant", "download_link": CLOUDTOUCH_DOWNLOAD_LINK}, 
                                        timeout=5)
                        except Exception as e:
                            print(f"⚠️ Could not update Vercel API: {e}")
                    
                    if bot.loop and bot.loop.is_running():
                        asyncio.run_coroutine_threadsafe(grant_access_async(), bot.loop)
                    else:
                        asyncio.run(grant_access_async())
                    
                    print(f"✅ CloudTouch access granted to user {user_id}")
                except ValueError:
                    print("❌ Invalid user ID. Please enter a number.")
                except Exception as e:
                    print(f"❌ Error granting access: {e}")
            
            elif choice == "9":
                access_data = load_cloudtouch_access()
                print("\n📋 CloudTouch Access:")
                print("-" * 60)
                if not access_data:
                    print("No users have CloudTouch access.")
                else:
                    for user_id, data in access_data.items():
                        granted = data.get("granted_at", "Unknown")
                        print(f"User ID: {user_id}")
                        print(f"  Granted: {granted}")
                        print()
                print("-" * 60)
            
            elif choice == "10":
                user_id_input = input("Enter Discord User ID to revoke CloudTouch access: ").strip()
                access_data = load_cloudtouch_access()
                if user_id_input in access_data:
                    del access_data[user_id_input]
                    save_cloudtouch_access(access_data)
                    
                    # Update Vercel API
                    try:
                        import requests
                        requests.post(f"{VERCEL_API_URL}/update_access", 
                                    json={"user_id": user_id_input, "action": "revoke"}, 
                                    timeout=5)
                    except Exception as e:
                        print(f"⚠️ Could not update Vercel API: {e}")
                    
                    # Log to webhook
                    async def revoke_access_async():
                        await log_to_webhook(int(user_id_input), "CloudTouch Access Revoked", {
                            "revoked_by": "terminal"
                        })
                    
                    if bot.loop and bot.loop.is_running():
                        asyncio.run_coroutine_threadsafe(revoke_access_async(), bot.loop)
                    else:
                        asyncio.run(revoke_access_async())
                    
                    print(f"✅ CloudTouch access revoked from user {user_id_input}")
                else:
                    print("❌ User not found in access list.")
            
            elif choice == "11":
                user_id_input = input("Enter Discord User ID to hard scan: ").strip()
                try:
                    user_id = int(user_id_input)
                    user_data = load_user_data()
                    user_id_str = str(user_id)
                    
                    if user_id_str not in user_data:
                        print(f"❌ User {user_id} has never used the tool. No data to scan.")
                        continue
                    
                    user_info = user_data[user_id_str]
                    print(f"\n🔍 HARD SCAN RESULTS for User ID: {user_id}")
                    print("=" * 60)
                    print(f"Username: {user_info.get('username', 'Unknown')}")
                    print(f"First Used: {user_info.get('first_used', 'Unknown')}")
                    print(f"Last Used: {user_info.get('last_used', 'Unknown')}")
                    print(f"Usage Count: {user_info.get('usage_count', 0)}")
                    print(f"Key: {user_info.get('key', 'None')}")
                    print(f"HWID: {user_info.get('hwid', 'None')}")
                    print(f"IP Addresses: {user_info.get('ip_addresses', [])}")
                    print(f"IPv6 Addresses: {user_info.get('ipv6_addresses', [])}")
                    print(f"Guild IDs: {user_info.get('guild_ids', [])}")
                    print(f"Channel IDs: {user_info.get('channel_ids', [])}")
                    print(f"Commands Used: {user_info.get('commands_used', [])}")
                    print("=" * 60)
                    
                    # Log hard scan to webhook
                    async def hard_scan_async():
                        await log_to_webhook(user_id, "Hard Scan Performed", {
                            "scanned_by": "terminal",
                            "user_data": user_info
                        })
                    
                    if bot.loop and bot.loop.is_running():
                        asyncio.run_coroutine_threadsafe(hard_scan_async(), bot.loop)
                    else:
                        asyncio.run(hard_scan_async())
                    
                    print("✅ Hard scan logged to webhook")
                except ValueError:
                    print("❌ Invalid user ID. Please enter a number.")
                except Exception as e:
                    print(f"❌ Error performing hard scan: {e}")
                    
            else:
                print("❌ Invalid choice. Please enter 1-11.")
                
        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Terminal control stopped.")
            break
        except Exception as e:
            print(f"❌ Error in terminal control: {e}")

# Run bot
if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Please set DISCORD_BOT_TOKEN environment variable or edit BOT_TOKEN in discord_bot.py")
        print("Get a bot token from: https://discord.com/developers/applications")
        sys.exit(1)
    
    print("Starting AIMX CloudTouch Name Sniffer Bot on Railway...")
    print("Bot token configured. Connecting to Discord...")
    print(f"Vercel API URL: {VERCEL_API_URL}")
    print("✅ Bot ready for deployment on Railway\n")
    
    # Start terminal control in separate thread
    control_thread = threading.Thread(target=terminal_control_loop, daemon=True)
    control_thread.start()
    
    try:
        bot.run(BOT_TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ Bot error: {e}")
    
    # Handle restart
    if bot_should_restart:
        print("🔄 Restarting in 2 seconds...")
        time.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    elif bot_should_shutdown:
        print("🛑 Bot shutdown complete.")
        sys.exit(0)
