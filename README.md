# Personal Telegram Auto Forwarder

An owner-only Telegram control bot backed by a Telethon user session. It watches channels that your Telegram account can access and delivers new posts to channels where that account can post.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python login.py
python main.py
```

Get `API_ID` and `API_HASH` from https://my.telegram.org and a bot token from `@BotFather`. The first login asks for your phone number, Telegram code, and 2FA password if configured. It prints a `TELEGRAM_SESSION` value. This is a login credential: do not share it or commit it.

## Cloud deployment

Cloud containers cannot perform the interactive Telegram login. Run `python login.py` on your own computer, then add the printed value as a `TELEGRAM_SESSION` environment variable in your hosting dashboard. Keep `API_ID`, `API_HASH`, `BOT_TOKEN`, and `OWNER_USER_ID` there too. Do not put any of those secrets in GitHub.

Open your control bot and send `/start`. Add sources and targets through the inline menus. Enter a public channel as `@username` or its `t.me` link. For a private channel with no username, your signed-in account must already be a member and you must enter its numeric ID.

The bot also supports `/dashboard`, `/status`, `/pause`, `/resume`, `/profile`, and `/setprofile Your Bot Name`. Telegram's command menu is registered automatically each time the service starts.

## Behavior

- `Forward` keeps Telegram attribution.
- `Copy` reposts without the forwarded header when Telegram permits it.
- Protected-content channels cannot be relayed.
- Only new posts are processed; posts are not backfilled.
- Obtain permission to republish content and keep volumes reasonable.
