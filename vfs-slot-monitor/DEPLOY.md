# Deploying VFS Slot Monitor on Azure VM

Complete step-by-step guide to deploy the visa slot monitor on an Azure VM
and connect it to your Telegram.

---

## Overview: What Happens in What Order

```
1. Create Azure VM
2. Install Docker on the VM
3. Create your Telegram bot (get bot token + your chat ID)
4. Clone the repo and configure secrets (.env)
5. Run --discover mode to find your VFS center codes  <-- THIS IS THE KEY STEP
6. Fill in config.yaml with discovered codes
7. Test each piece: login, API, notification
8. Start the monitor with Docker
```

The `--discover` step is critical because the VFS API needs internal codes
(`center_code`, `visa_category_code`) that aren't publicly documented.
The discover mode opens a real browser, lets you walk through the VFS
booking flow, and captures the API calls to extract these codes.

---

## Step 1: Create an Azure VM

### Via Azure Portal

1. Go to https://portal.azure.com
2. **Create a resource** > **Virtual Machine**
3. Settings:
   - **Image**: Ubuntu 22.04 LTS (or 24.04)
   - **Size**: `Standard_B2s` (2 vCPU, 4 GB RAM) - this is enough and costs ~$30/month
   - **Authentication**: SSH public key (recommended) or password
   - **Inbound ports**: Allow SSH (22)
   - **Disk**: 30 GB Standard SSD is fine
4. **Review + Create** > **Create**
5. Note your VM's **public IP address**

### Via Azure CLI (faster)

```bash
# Login
az login

# Create resource group
az group create --name vfs-monitor-rg --location uksouth

# Create VM (UK South for lowest latency to VFS UK)
az vm create \
  --resource-group vfs-monitor-rg \
  --name vfs-monitor-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard

# Note the publicIpAddress in the output
```

### SSH into your VM

```bash
ssh azureuser@<YOUR_VM_IP>
```

---

## Step 2: Install Docker on the VM

```bash
# Update packages
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add your user to docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# Log out and back in for group change to take effect
exit
ssh azureuser@<YOUR_VM_IP>

# Verify Docker works
docker --version
docker compose version
```

---

## Step 3: Create Your Telegram Bot

### 3a. Create the bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name: e.g., `My VFS Slot Monitor`
4. Choose a username: e.g., `my_vfs_slots_bot` (must end in `bot`)
5. BotFather gives you a **token** like: `7123456789:AAH1234abcd5678efgh`
6. **Save this token** - you'll need it for `.env`

### 3b. Get your Telegram chat ID

1. Open Telegram and search for **@userinfobot**
2. Send `/start`
3. It replies with your **chat ID** (a number like `123456789`)
4. **Save this ID** - this is your `TELEGRAM_ADMIN_IDS`

### 3c. Start a chat with your bot

1. Find your new bot in Telegram by its username
2. Send `/start` to it (important - you must do this before the bot can message you)

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
VFS_EMAIL=your_vfs_global_email@example.com
VFS_PASSWORD=your_vfs_global_password
CAPTCHA_API_KEY=
```

> **Note**: Use the same email/password you use to log in at
> visa.vfsglobal.com. You need an existing VFS Global account.

### 4c. Create your config.yaml

```bash
cp config/config.example.yaml config/config.yaml
nano config/config.yaml
```

For now, just enable the country/countries you want. Leave `center_code`
and `visa_category_code` empty - we'll fill them in after the discover step.

Example - monitoring France and Netherlands:

```yaml
centers:
  - country_code: "fra"
    country_name: "France"
    mission_code: "fra"
    center_code: ""                  # Will fill after --discover
    visa_category_code: ""           # Will fill after --discover
    centers: ["London"]
    enabled: true

  - country_code: "nld"
    country_name: "Netherlands"
    mission_code: "nld"
    center_code: ""                  # Will fill after --discover
    visa_category_code: ""           # Will fill after --discover
    centers: ["London"]
    enabled: true
```

---

## Step 5: Discover Your VFS Center Codes (THE KEY STEP)

This is the step that finds the internal API codes VFS uses. The `--discover`
mode opens a **real Chrome browser** where you manually walk through the
VFS booking flow. The tool watches the network requests and captures the
API parameters.

### Why is this needed?

The VFS API endpoint needs codes like `centerCode=FRUK` and
`visaCategoryCode=002`, but these aren't shown anywhere on the website.
They're hidden in the API calls the frontend makes. Discovery mode
intercepts these calls.

### Option A: Run discover on your LOCAL machine (Recommended)

Discovery mode needs a **visible** browser (not headless) so you can
interact with the VFS site. This is easiest on your local machine with
a display.

```bash
# On your LOCAL machine (not the VM), clone and install
git clone https://github.com/stretchcloud/OCI-Diagram.git
cd OCI-Diagram/vfs-slot-monitor

# Install Python deps locally (needs Python 3.11+)
pip install undetected-chromedriver selenium httpx pyyaml pydantic pydantic-settings python-dotenv structlog

# Create minimal .env with just VFS credentials
cp .env.example .env
# Edit .env - fill in VFS_EMAIL, VFS_PASSWORD (Telegram token not needed for this step)

# Copy config
cp config/config.example.yaml config/config.yaml

# Run discover for France
PYTHONPATH=src python -m vfs_monitor --discover fra
```

**What happens:**

1. A Chrome window opens and navigates to VFS France booking page
2. You see the VFS website in the browser
3. **You manually**:
   - Log in with your email and password
   - Select your visa category (e.g., "Schengen Visa" > "Tourism")
   - Select your center (e.g., "London")
   - Wait for the calendar/availability page to load
4. Press **Enter** in your terminal when done
5. The tool prints all captured API calls with their parameters:

```
============================================================
DISCOVERED API CALLS:
============================================================

  https://lift-api.vfsglobal.com/appointment/slots?countryCode=gbr&missionCode=fra&centerCode=FRUK&loginUser=you@email.com&visaCategoryCode=002&languageCode=en-US&applicantsCount=1&days=90&slotType=2
    countryCode=gbr
    missionCode=fra
    centerCode=FRUK               <-- THIS IS YOUR center_code
    visaCategoryCode=002           <-- THIS IS YOUR visa_category_code
    ...

Copy the centerCode and visaCategoryCode into your config.yaml
```

6. Repeat for each country: `--discover nld`, `--discover ita`, etc.

### Option B: Run discover on the VM via SSH X-forwarding

If you can't run it locally, you can forward the browser display over SSH:

```bash
# On your local machine, connect with X forwarding
ssh -X azureuser@<YOUR_VM_IP>

# On the VM, install Chrome and deps
sudo apt-get install -y google-chrome-stable
pip install undetected-chromedriver selenium

# Run discover (the browser window appears on YOUR screen via X11)
cd ~/OCI-Diagram/vfs-slot-monitor
PYTHONPATH=src python -m vfs_monitor --discover fra
```

### Option C: Manual network inspection (no discover mode needed)

If neither option works, you can find the codes yourself:

1. Open Chrome on your local machine
2. Go to `visa.vfsglobal.com/gbr/en/fra/book-an-appointment`
3. Press **F12** to open DevTools > **Network** tab
4. Filter by `lift-api` in the network filter bar
5. Log in and navigate through the booking flow
6. When you select a center and the calendar loads, you'll see a request to
   `lift-api.vfsglobal.com/appointment/slots`
7. Click on it and look at the **Query String Parameters**
8. Copy `centerCode` and `visaCategoryCode` values

### Fill in your config.yaml

After discovery, update your `config/config.yaml` on the VM:

```yaml
centers:
  - country_code: "fra"
    country_name: "France"
    mission_code: "fra"
    center_code: "FRUK"              # From discovery
    visa_category_code: "002"        # From discovery
    centers: ["London"]
    enabled: true

  - country_code: "nld"
    country_name: "Netherlands"
    mission_code: "nld"
    center_code: "NLUK"              # From discovery
    visa_category_code: "003"        # From discovery
    centers: ["London"]
    enabled: true
```

---

## Step 6: Test Each Piece

SSH into your VM and run these tests one at a time.

### 6a. Validate your config

```bash
cd ~/OCI-Diagram/vfs-slot-monitor
docker compose build
docker compose run --rm vfs-monitor python -m vfs_monitor --dry-run
```

Expected output:
```
config_valid    centers=10 enabled=2
center          country=France code=fra
center          country=Netherlands code=nld
telegram_token_set  value=True
vfs_email_set       value=True
```

### 6b. Test the browser login + JWT extraction

```bash
docker compose run --rm vfs-monitor python -m vfs_monitor --login-test
```

Expected output:
```
browser_login_starting   country=fra
browser_login_success    token_prefix=eyJhbGciOiJSUzI1...
login_test_success       token_length=1842 prefix=eyJhbGciOiJSUzI1NiIsInR5...
```

If this fails:
- Check your VFS credentials in `.env`
- Check `data/debug/` for screenshots showing what the browser saw
- If CAPTCHA appeared, consider enabling 2captcha (see Troubleshooting below)

### 6c. Test the API call

```bash
docker compose run --rm vfs-monitor python -m vfs_monitor --api-test
```

Expected output:
```
jwt_refresh_starting
browser_login_success    ...
api_check_complete       center=France slots_found=0 response_ms=142
api_check_complete       center=Netherlands slots_found=0 response_ms=98
```

`slots_found=0` is normal - it just means no slots are available right now.
The important thing is that the API call succeeded (no errors).

### 6d. Test Telegram notifications

```bash
docker compose run --rm vfs-monitor python -m vfs_monitor --notify-test
```

**Check your Telegram** - you should receive a test notification that looks like:

```
🔔 VISA SLOT AVAILABLE

🇳🇱 Netherlands - Schengen Visa
📍 London
📅 Saturday, 21 March 2026
🕒 3 slot(s) available

🔗 Book now on VFS Global
⏰ Detected at 14:32:05 UTC
```

If you don't receive it:
- Make sure you sent `/start` to your bot in Telegram first
- Make sure you `/subscribe`'d (or the `--notify-test` sends to admin IDs directly)
- Check that `TELEGRAM_ADMIN_IDS` in `.env` matches your chat ID

### 6e. Test the subscribe flow

1. Open Telegram, find your bot
2. Send `/subscribe`
3. Bot should reply confirming your subscription
4. Send `/status` to see monitor health

---

## Step 7: Start the Monitor

Everything tested? Let's go live.

```bash
cd ~/OCI-Diagram/vfs-slot-monitor

# Start in detached mode
docker compose up -d

# Watch the logs
docker compose logs -f
```

You should see:
```
vfs_monitor_starting     centers=['France', 'Netherlands'] interval=8
obtaining_initial_jwt
browser_login_success    ...
api_check_complete       center=France slots_found=0 response_ms=134
api_check_complete       center=Netherlands slots_found=0 response_ms=98
next_check_in            seconds=9.2
api_check_complete       center=France slots_found=0 response_ms=121
...
```

The monitor is now running. It will:
- Poll VFS every ~8 seconds for each enabled country
- Instantly notify you on Telegram when slots appear
- Re-login via browser every 2 hours to refresh the JWT token
- Back off automatically if rate limited
- Auto-restart if it crashes (Docker `restart: unless-stopped`)

### Useful Docker commands

```bash
# Check if it's running
docker compose ps

# View recent logs
docker compose logs --tail 100

# Follow logs in real-time
docker compose logs -f

# Restart
docker compose restart

# Stop
docker compose down

# Rebuild after config changes
docker compose up -d --build
```

---

## Step 8: Telegram Bot Commands Reference

Once running, interact with your bot in Telegram:

| Command | What it does |
|---------|-------------|
| `/start` | Welcome message and instructions |
| `/subscribe` | Start receiving slot notifications |
| `/unsubscribe` | Stop notifications |
| `/status` | Show uptime, check count, success rate, JWT health |
| `/check` | Force an immediate check right now |
| `/help` | List all commands |

---

## Troubleshooting

### "login_failed: could not find email input field"

VFS changed their page layout. Check `data/debug/` for screenshots.
You may need to update the CSS selectors in
`src/vfs_monitor/auth/browser_login.py` (the `email_selectors` and
`password_selectors` lists).

### CAPTCHA keeps blocking login

Enable 2captcha:

1. Sign up at https://2captcha.com and add funds (~$3 gets you thousands of solves)
2. Copy your API key
3. Edit `.env`:
   ```
   CAPTCHA_API_KEY=your_2captcha_api_key
   ```
4. Edit `config/config.yaml`:
   ```yaml
   captcha:
     provider: "2captcha"
     enabled: true
   ```
5. Rebuild: `docker compose up -d --build`

### "JWT expired (401)" errors in logs

This is normal and self-healing. The monitor detects the 401, triggers a
browser re-login, gets a fresh JWT, and continues. You'll see:

```
api_auth_expired         center=France
triggering_jwt_refresh_due_to_401
browser_login_success    ...
api_check_complete       center=France slots_found=0
```

### "Rate limited (429)" errors

The monitor automatically backs off with exponential delay. If it persists:
- Increase `slot_check_interval_seconds` to 15 or 20 in config.yaml
- Enable proxy rotation:
  ```yaml
  proxy:
    enabled: true
    urls:
      - "http://user:pass@residential-proxy1:8080"
      - "http://user:pass@residential-proxy2:8080"
  ```

### Not receiving Telegram messages

1. Did you send `/start` to your bot? (Required before bot can message you)
2. Did you send `/subscribe`?
3. Is your chat ID in `TELEGRAM_ADMIN_IDS`?
4. Run `docker compose run --rm vfs-monitor python -m vfs_monitor --notify-test`
5. Check logs: `docker compose logs | grep telegram`

### VM running costs

- `Standard_B2s`: ~$30/month (plenty for this)
- `Standard_B1s`: ~$15/month (1 vCPU, 2 GB - works but tight when Chrome runs)
- You can **stop the VM** when you don't need monitoring and only pay for disk (~$1/month)
- Set up auto-shutdown schedule in Azure Portal to save costs

---

## Optional: Monitoring Multiple Countries

Just enable more countries in `config/config.yaml` after running `--discover`
for each one. The monitor checks all enabled countries in sequence, with a
1-3 second random pause between each.

With 3 countries and 8-second intervals, the effective check rate is:
- Country 1 checked every ~30 seconds
- Country 2 checked every ~30 seconds
- Country 3 checked every ~30 seconds

To check more frequently, reduce `slot_check_interval_seconds` to 5 (aggressive)
and consider adding proxies.

---

## Optional: Auto-Start on VM Boot

The Docker `restart: unless-stopped` policy handles container restarts, but
if the VM itself reboots you need Docker to start automatically:

```bash
sudo systemctl enable docker
```

Docker will start on boot, and your container will auto-restart.
