<!-- ✨ Animated Header (Top) -->

<p align="center">
  <img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" />
</p>

<!-- 👤 Avatar + Typing Banner -->

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="https://files.catbox.moe/r2ga8f.jpg" width="90px" style="border-radius: 50%;" />
      </td>
      <td>
        <img src="https://readme-typing-svg.herokuapp.com?color=00BFFF&width=600&lines=Hey+There,+This+is+Certified+Coder+%F0%9F%A5%80+%E2%9D%97%EF%B8%8F" />
      </td>
    </tr>
  </table>
</div>

<!-- 👁 Visitor Counter -->

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=CertifiedCoders&style=flat-square" />
</p>

<h1 align="center">
  <img src="https://readme-typing-svg.herokuapp.com?color=FF69B4&width=500&lines=Welcome+to+TuneViaBot+%F0%9F%8E%B6;The+Ultimate+Telegram+Music+Bot" />
</h1>


<p align="center">
  <a href="https://t.me/CertifiedCoders">
    <img src="https://files.catbox.moe/d0ynvn.jpg" width="450">
  </a>
</p>

<p align="center">
  <a href="https://t.me/TuneViaBot"><img src="https://img.shields.io/badge/Try%20Bot-@TuneViaBot-blue?style=for-the-badge&logo=telegram" /></a>
</p>


<p align="center">
  <a href="https://github.com/CertifiedCoders/TuneViaBot/stargazers"><img src="https://img.shields.io/github/stars/CertifiedCoders/TuneViaBot?style=flat-square"/></a>
  <a href="https://github.com/CertifiedCoders/TuneViaBot/network/members"><img src="https://img.shields.io/github/forks/CertifiedCoders/TuneViaBot?style=flat-square"/></a>
  <a href="https://github.com/CertifiedCoders/TuneViaBot/issues"><img src="https://img.shields.io/github/issues/CertifiedCoders/TuneViaBot?style=flat-square"/></a>
  <a href="https://github.com/CertifiedCoders/TuneViaBot/commits/main"><img src="https://img.shields.io/github/last-commit/CertifiedCoders/TuneViaBot?style=flat-square"/></a>
  <a href="https://github.com/CertifiedCoders/TuneViaBot/actions"><img src="https://img.shields.io/badge/CI-Status-grey?style=flat-square"/></a>
</p>

## 🌟 What is TuneViaBot?

**TuneViaBot** is a blazing fast, modern Telegram music bot built with **Pyrogram** and **PyTgCalls**. It streams high-quality music into your group voice chats and supports various platforms like YouTube, Spotify, Apple Music, and more.

## 🚀 Features
<table>
<tr>
<td>
  <img src="https://files.catbox.moe/la0sxq.jpg" width="300" />
</td>
<td>

| 🌟 Feature                | 🔎 Description                              |
| ------------------------- | ------------------------------------------- |
| 🎶 HQ Music Streaming     | Lag‑free HD audio in group voice chats      |
| 🌐 Multi‑Platform Sources | YouTube, Spotify, Apple Music, Resso, etc.  |
| ⚡ Fast Setup              | One‑click Heroku, VPS, or Docker deployment |
| 🔄 Auto Config            | Quick setup script with pre‑checks          |

</td>
</tr>
</table>

## 🔑 Environment Variables

Below are the required and optional environment variables for deployment.

```env
API_ID=              # Required - Get from https://my.telegram.org
API_HASH=            # Required - From https://my.telegram.org
BOT_TOKEN=           # Required - Get t.me/BotFather
OWNER_ID=            # Required - Your Telegram user ID
LOGGER_ID=           # Required - Log group/channel ID
STRING_SESSION=      # Required - Generate from @SessionBuilderbot
MONGO_DB_URI=        # Required - MongoDB connection string
COOKIE_URL=          # Required - YT Cookies url

API_KEY=             # Optional - External API key for song Download
VIDEO_API_URL=       # Optional - External API url for video Download
API_URL=             # Optional - External API url for audio Download
```

⚠️ **Never expose raw cookies or tokens in public repos.** Use safe paste services like [Pastebin](https://pastebin.com) or [Batbin](https://batbin.me).

##

<details>
  <summary><b>Where do I get each key?</b></summary>

  <!-- Added: Well‑organized helper table -->

  <br/>

  <table>
    <thead>
      <tr>
        <th>Key</th>
        <th>Where to Get It</th>
        <th>Steps</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>API_ID</code> &amp; <code>API_HASH</code></td>
        <td><a href="https://my.telegram.org" target="_blank">my.telegram.org</a> → <i>API Development Tools</i></td>
        <td>
          1) Log in with Telegram →
          2) Open <b>API Development Tools</b> →
          3) Create app →
          4) Copy values
        </td>
        <td>Keep these private. Needed by both userbot &amp; bot client.</td>
      </tr>
      <tr>
        <td><code>BOT_TOKEN</code></td>
        <td><a href="https://t.me/BotFather" target="_blank">@BotFather</a></td>
        <td>
          1) <b>/newbot</b> →
          2) Set name &amp; username →
          3) Copy the token
        </td>
        <td>Rotate if leaked. Store in <code>.env</code>.</td>
      </tr>
      <tr>
        <td><code>STRING_SESSION</code></td>
        <td><a href="https://t.me/SessionBuilderbot" target="_blank">@SessionBuilderbot</a></td>
        <td>
          1) Start bot →
          2) Provide <code>API_ID</code>/<code>API_HASH</code> →
          3) Complete login →
          4) Copy string
        </td>
        <td>Userbot auth for Pyrogram.</td>
      </tr>
      <tr>
        <td><code>LOGGER_ID</code></td>
        <td>Telegram <b>Channel/Group</b> you own</td>
        <td>
          1) Create private channel/group →
          2) Add your bot as admin →
          3) Get ID via <code>@AnnieXRobot</code> or <code>@MissRose_Bot</code>
        </td>
        <td>Use a private space so logs aren’t public.</td>
      </tr>
      <tr>
        <td><code>MONGO_DB_URI</code></td>
        <td><a href="https://www.mongodb.com/atlas/database" target="_blank">MongoDB Atlas</a></td>
        <td>
          1) Create free cluster →
          2) Add database user &amp; IP allowlist →
          3) Copy connection string (<code>mongodb+srv://...</code>)
        </td>
        <td>Required for persistence (queues, configs, etc.).</td>
      </tr>
      <tr>
        <td><code>COOKIE_URL</code></td>
        <td>Any secure host (e.g., <a href="https://pastebin.com" target="_blank">Pastebin</a>, <a href="https://batbin.me" target="_blank">Batbin</a>)</td>
        <td>
          1) Upload your <code>cookies.txt</code> privately →
          2) Set paste visibility to <b>Unlisted</b> →
          3) Copy the <b>raw</b> URL
        </td>
        <td>Improves YouTube reliability. Never commit raw cookies.</td>
      </tr>
      <tr>
        <td><code>API_KEY</code> / <code>API_URL or VIDEO_API_URL</code></td>
        <td>Provider of your choice</td>
        <td>generate key → paste here</td>
        <td>Optional integrations.</td>
      </tr>
    </tbody>
  </table>

  <br/>
</details>

##

### ☕ VPS Setup Guide

<img src="https://img.shields.io/badge/Show%20/Hide-VPS%20Steps-0ea5e9?style=for-the-badge" alt="Toggle VPS Steps"/>
<div align="left">
  <details>

```bash
🎵 Deploy TuneViaBot on VPS

# Step 1: Update & Install Dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl python3-pip python3-venv ffmpeg unzip tmux

# Step 2: Install Deno (for yt-dlp) —
curl -fsSL https://deno.land/install.sh | sh
# → When prompted: "Edit shell configs to add deno to the PATH? (y/n)" → Type: y
source ~/.bashrc

# Step 3: Clone & Setup
git clone https://github.com/CertifiedCoders/TuneViaBot 
cd TuneViaBot
tmux new -s tune

# Inside tmux:
python3 -m venv venv
source venv/bin/activate
pip install -U pip && pip install -r requirements.txt

bash setup  # Fill: API_ID, BOT_TOKEN, COOKIE_URL, etc.
bash start  # Run bot

### Useful Commands
tmux detach                      # Use Ctrl+B, then D
tmux attach-session -t tune       # Reattach session
tmux kill-session -t tune         # Kill bot session
rm -rf TuneViaBot                 # Uninstall bot
```

  </details>
</div>

##

### 🐳 Docker Deployment

<img src="https://img.shields.io/badge/Show%20/Hide-Docker%20Steps-10b981?style=for-the-badge" alt="Toggle Docker Steps"/>

<div align="left">
  <details>

```bash
### Step 1: Clone Repo
git clone https://github.com/CertifiedCoders/TuneViaBot
cd TuneViaBot

### Step 2: Create .env File
nano .env
# Paste your environment variables here (API_ID, API_HASH, BOT_TOKEN, MONGO_DB_URI, COOKIE_URL, etc.)
# Save with Ctrl+O, Enter, then Ctrl+X

### Step 3: Build Docker Image
docker build -t tuneviabot .

### Step 4: Run Container
docker run -d \
  --name tune \
  --env-file .env \
  --restart unless-stopped \
  tuneviabot

### Step 5: Manage Container
docker logs -f tune         # View logs (Ctrl+C to exit)
docker stop tune            # Stop container
docker start tune           # Start container
docker rm -f tune           # Remove container
docker rmi tuneviabot       # Remove image
```

  </details>
</div>



##
### ☁️ Quick Deploy

| Platform                | Deploy Link                                                                                                                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🔑 **Generate Session** | <a href="https://t.me/SessionBuilderbot"><img src="https://img.shields.io/badge/Session%20-Generator-blue?style=for-the-badge&logo=telegram"/></a>                                                    |
| 🌍 **Heroku Deploy**    | <a href="http://dashboard.heroku.com/new?template=https://github.com/CertifiedCoders/TuneViaBot"><img src="https://img.shields.io/badge/Deploy%20to-Heroku-purple?style=for-the-badge&logo=heroku"/></a> |




## 💬 Community & Support

<p align="center">
  <a href="https://t.me/CertifiedCoders">
    <img src="https://img.shields.io/badge/Support_Group-Telegram-0088cc?style=for-the-badge&logo=telegram&logoColor=white" />
  </a>
  <a href="https://t.me/CertifiedCodes">
    <img src="https://img.shields.io/badge/Updates_Channel-Telegram-6A5ACD?style=for-the-badge&logo=telegram&logoColor=white" />
  </a>
  <a href="https://t.me/CertifiedCoder">
    <img src="https://img.shields.io/badge/Contact_Owner-Telegram-4CAF50?style=for-the-badge&logo=telegram&logoColor=white" />
  </a>
  <a href="https://youtube.com/@rajnisha3">
    <img src="https://img.shields.io/badge/Subscribe-YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" />
  </a>
  <a href="https://instagram.com/rajnishthegreat">
    <img src="https://img.shields.io/badge/Follow-Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" />
  </a>
  <a href="mailto:rajnishmishraaa1@gmail.com">
    <img src="https://img.shields.io/badge/Contact-Email-0078D4?style=for-the-badge&logo=gmail&logoColor=white" />
  </a>
</p>


##
### 🔖 Credits

* <b> *sᴩᴇᴄɪᴀʟ ᴛʜᴀɴᴋs ᴛᴏ <a href="https://github.com/AnonymousX1025">ᴀɴᴏɴʏ</a> ғᴏʀ <a href="https://github.com/AnonymousX1025/AnonXMusic">ᴀɴᴏɴxᴍᴜsɪᴄ</a>* </b>
* <b> *ᴄʀᴀғᴛᴇᴅ ᴡɪᴛʜ ᴘᴀssɪᴏɴ ʙʏ <a href="https://github.com/CertifiedCoders">ᴄᴇʀᴛɪғɪᴇᴅ ᴄᴏᴅᴇʀs</a>* </b>