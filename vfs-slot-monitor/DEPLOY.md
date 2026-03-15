# Deploying TLScontact Slot Monitor on Azure VM

Complete step-by-step guide to deploy the visa slot monitor on an Azure VM
and connect it to your Telegram.

---

## Overview: What Happens in What Order

```
1. Create Azure VM
2. Install Docker on the VM
3. Create your Telegram bot (get bot token + your chat ID)
4. Clone the repo and configure secrets (.env)
5. Run --discover mode to find your TLScontact issuer IDs  <-- KEY STEP
6. Fill in config.yaml with discovered issuer IDs
7. Test each piece: login, slot check, notification
8. Start the monitor with Docker
```

The `--discover` step is critical because TLScontact encodes your
city/country combination into an `issuer_id` (e.g., `gbLON2fr` for
UK-London applying for France). This ID is part of every URL and must
be configured correctly.

---

## How TLScontact Differs from VFS Global

| | VFS Global | TLScontact |
|---|---|---|
| **Slot check method** | REST API (`lift-api.vfsglobal.com`) | Browser scraping (no API) |
| **Authentication** | JWT token | Keycloak session + cookies |
| **Check frequency** | Every 8 seconds | Every 5+ minutes (rate limited) |
| **Resource usage** | Low (HTTP requests) | Higher (Chrome browser running) |
| **Anti-bot** | Occasional CAPTCHA | Robot-protection landing page |

**Key implication**: The monitor keeps a Chrome browser running inside Docker.
This needs more RAM than a simple API poller. `Standard_B2s` (4 GB) works well.

---

## Step 1: Create an Azure VM

### Via Azure Portal

1. Go to https://portal.azure.com
2. **Create a resource** > **Virtual Machine**
3. Settings:
   - **Image**: Ubuntu 22.04 LTS (or 24.04)
   - **Size**: `Standard_B2s` (2 vCPU, 4 GB RAM) - needed for Chrome
   - **Authentication**: SSH public key (recommended)
   - **Inbound ports**: Allow SSH (22)
   - **Disk**: 30 GB Standard SSD
4. **Review + Create** > **Create**

### Via Azure CLI

```bash
az login
az group create --name tls-monitor-rg --location uksouth
az vm create \
  --resource-group tls-monitor-rg \
  --name tls-monitor-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard
```

### SSH into your VM

```bash
ssh azureuser@<YOUR_VM_IP>
```

---

## Step 2: Install Docker on the VM

```bash
sudo apt-get update && sudo apt-get upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
ssh azureuser@<YOUR_VM_IP>
docker --version
docker compose version
```

---

## Step 3: Create Your Telegram Bot

### 3a. Create the bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Choose a name: e.g., `My TLS Slot Monitor`
4. Choose a username: e.g., `my_tls_slots_bot` (must end in `bot`)
5. **Save the token** (e.g., `7123456789:AAH1234abcd5678efgh`)

### 3b. Get your Telegram chat ID

1. Search for **@userinfobot** in Telegram
2. Send `/start`
3. **Save your chat ID** (a number like `123456789`)

### 3c. Start a chat with your bot

1. Find your bot by username in Telegram
2. Send `/start` (required before the bot can message you)

---

## Step 4: Clone and Configure

### 4a. Clone the repo

```bash
cd ~
git clone https://github.com/stretchcloud/OCI-Diagram.git
cd OCI-Diagram/vfs-slot-monitor
```

### 4b. Create your .env file

```bash
cp .env.example .env
nano .env
```

Fill in your values:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAH1234abcd5678efgh
TELEGRAM_ADMIN_IDS=123456789
TLS_EMAIL=your_tlscontact_email@example.com
TLS_PASSWORD=your_tlscontact_password
CAPTCHA_API_KEY=
```

> **Note**: Use the same email/password you use to log in at
> `visas-fr.tlscontact.com` (or whichever country's TLS portal).

### 4c. Create your config.yaml

```bash
cp config/config.example.yaml config/config.yaml
nano config/config.yaml
```

Enable the country/city you want. Leave `issuer_id` empty for now -
we'll fill it in after the discover step.

---

## Step 5: Discover Your TLScontact Issuer IDs (THE KEY STEP)

TLScontact URLs contain an `issuer_id` that encodes your city and
destination country:

```
https://visas-fr.tlscontact.com/visa/gb/gbLON2fr/home
                                       ^^^^^^^^
                                       issuer_id = gbLON2fr
                                       (gb = from UK, LON = London, fr = to France)
```

### Option A: Run discover on your LOCAL machine (Recommended)

Discovery mode opens a visible Chrome browser so you can interact
with TLScontact.

```bash
# On your LOCAL machine
cd OCI-Diagram/vfs-slot-monitor
pip install undetected-chromedriver selenium pyyaml pydantic pydantic-settings python-dotenv structlog

# Create minimal .env with just TLS credentials
cp .env.example .env
# Edit .env - fill in TLS_EMAIL, TLS_PASSWORD

# Copy config
cp config/config.example.yaml config/config.yaml

# Run discover for France
PYTHONPATH=src python -m vfs_monitor --discover fr
```

**What happens:**

1. Chrome opens and navigates to `visas-fr.tlscontact.com`
2. You interact with the site:
   - Accept cookies
   - Select your country (United Kingdom)
   - Select your city (London)
   - Log in if prompted
3. **Watch the URL bar** - it changes to something like:
   `https://visas-fr.tlscontact.com/visa/gb/gbLON2fr/home`
4. Press **Enter** in your terminal
5. The tool prints the discovered issuer IDs:

```
============================================================
DISCOVERED ISSUER IDs:
============================================================

  issuer_id: gbLON2fr
  from_country: gb
  URL: https://visas-fr.tlscontact.com/visa/gb/gbLON2fr/home

Add these to your config.yaml like:
  issuer_id: "gbLON2fr"
  from_country: "gb"
```

Repeat for each country/city: `--discover de`, `--discover nl`, etc.

### Option B: Find the issuer_id manually (if discover doesn't work)

1. Open Chrome, go to `visas-fr.tlscontact.com`
2. Select your country (e.g., United Kingdom)
3. Select your city (e.g., London)
4. Look at the URL bar:
   `https://visas-fr.tlscontact.com/visa/gb/gbLON2fr/home`
5. The `issuer_id` is `gbLON2fr`

Common issuer_id patterns for UK applicants:
- France London: `gbLON2fr`
- France Edinburgh: `gbEDI2fr`
- France Manchester: `gbMAN2fr`
- Germany London: `gbLON2de`
- Germany Edinburgh: `gbEDI2de`

### Fill in your config.yaml

```yaml
centers:
  - country_code: "fr"
    country_name: "France"
    from_country: "gb"
    issuer_id: "gbLON2fr"    # From discovery
    city: "London"
    enabled: true

  - country_code: "de"
    country_name: "Germany"
    from_country: "gb"
    issuer_id: "gbLON2de"    # From discovery
    city: "London"
    enabled: true
```

---

## Step 6: Test Each Piece

### 6a. Validate your config

```bash
cd ~/OCI-Diagram/vfs-slot-monitor
docker compose build
docker compose run --rm tls-monitor python -m vfs_monitor --dry-run
```

Expected:
```
config_valid    centers=10 enabled=2
center          country=France code=fr city=London issuer_id=gbLON2fr
center          country=Germany code=de city=London issuer_id=gbLON2de
telegram_token_set  value=True
tls_email_set       value=True
```

### 6b. Test the browser login

```bash
docker compose run --rm tls-monitor python -m vfs_monitor --login-test
```

Expected:
```
tls_login_starting   country=fr city=London
cookies_accepted
tls_login_success
login_test_success   url=https://visas-fr.tlscontact.com/visa/gb/gbLON2fr/home
```

If this fails:
- Check your TLS credentials in `.env`
- Check `data/debug/` for screenshots
- TLScontact may limit login attempts - wait 1.5 hours and retry

### 6c. Test a slot check

```bash
docker compose run --rm tls-monitor python -m vfs_monitor --check-test
```

Expected:
```
establishing_initial_session
tls_login_success
slot_check_complete  center=France city=London slots_found=0 response_ms=4200
```

`slots_found=0` is normal - just means no slots right now.

### 6d. Test Telegram notifications

```bash
docker compose run --rm tls-monitor python -m vfs_monitor --notify-test
```

Check your Telegram - you should receive a test notification.

### 6e. Test the subscribe flow

1. Open Telegram, find your bot
2. Send `/subscribe`
3. Send `/status` to see monitor health

---

## Step 7: Start the Monitor

```bash
cd ~/OCI-Diagram/vfs-slot-monitor

# Start in detached mode
docker compose up -d

# Watch the logs
docker compose logs -f
```

You should see:
```
tls_monitor_starting     centers=['France (London)', 'Germany (London)'] interval=300
establishing_initial_session
tls_login_success
slot_check_complete       center=France city=London slots_found=0 response_ms=4200
next_check_in             seconds=312.4
slot_check_complete       center=France city=London slots_found=0 response_ms=3800
...
```

The monitor:
- Checks TLScontact every ~5 minutes for each enabled center
- Instantly notifies you on Telegram when slots appear
- Re-authenticates every 4 hours to keep the session fresh
- Backs off automatically if rate limited or blocked
- Auto-restarts if it crashes (Docker `restart: unless-stopped`)

### Docker commands

```bash
docker compose ps          # Check if running
docker compose logs -f     # Follow logs
docker compose restart     # Restart
docker compose down        # Stop
docker compose up -d --build  # Rebuild after config changes
```

---

## Step 8: Telegram Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Welcome message |
| `/subscribe` | Start receiving slot notifications |
| `/unsubscribe` | Stop notifications |
| `/status` | Uptime, session status, check stats |
| `/check` | Force an immediate check (admin only) |
| `/help` | List all commands |

---

## Troubleshooting

### "login_failed: could not find login link"

TLScontact may have updated their page layout. Check `data/debug/`
for screenshots. The tool tries multiple selectors, but TLS occasionally
changes their HTML structure.

### Rate limiting / being blocked

TLScontact limits authentication attempts per day. The default 5-minute
check interval is safe, but if you get blocked:

1. **Wait 1.5 hours** before trying again
2. Increase `slot_check_interval_seconds` to 600 (10 minutes)
3. Enable `browser.user_data_dir` to persist cookies across restarts:
   ```yaml
   browser:
     user_data_dir: "/app/data/chrome-profile"
   ```
4. Consider adding proxies:
   ```yaml
   proxy:
     enabled: true
     urls:
       - "http://user:pass@residential-proxy:8080"
   ```

### CAPTCHA keeps blocking login

Enable 2captcha:

1. Sign up at https://2captcha.com and add funds (~$3)
2. Add your API key to `.env`:
   ```
   CAPTCHA_API_KEY=your_2captcha_api_key
   ```
3. Enable in `config.yaml`:
   ```yaml
   captcha:
     provider: "2captcha"
     enabled: true
   ```

### Browser crashes (out of memory)

The Chrome browser uses significant memory. Increase VM size:
- `Standard_B2s` (4 GB) - recommended minimum
- `Standard_B2ms` (8 GB) - for monitoring many centers

Also, the `shm_size: '2gb'` in docker-compose.yml helps Chrome
with shared memory.

### Not receiving Telegram messages

1. Did you send `/start` to your bot?
2. Did you send `/subscribe`?
3. Is your chat ID in `TELEGRAM_ADMIN_IDS`?
4. Run `--notify-test`
5. Check logs: `docker compose logs | grep telegram`

### VM costs

- `Standard_B2s` (4 GB): ~$30/month
- Stop the VM when not needed (disk: ~$1/month)
- Set up auto-shutdown in Azure Portal

---

## Check Interval Recommendations

| Interval | Risk Level | Notes |
|----------|-----------|-------|
| 300s (5 min) | Safe | Default, recommended |
| 180s (3 min) | Moderate | May work, watch for blocks |
| 60s (1 min) | Risky | Germany TLS reported OK, France may block |
| 30s or less | Dangerous | Will likely get blocked quickly |

TLScontact releases new slots daily, typically in the morning (UK time).
The 5-minute interval catches slots within minutes of release.

---

## Auto-Start on VM Boot

```bash
sudo systemctl enable docker
```

Docker starts on boot, and your container auto-restarts with it.
