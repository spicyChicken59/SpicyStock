> [!WARNING]
> **This entire guide is out of date. Following any part of it will not work.**
> It documents an earlier build that used yfinance for market data and Gmail
> OAuth for delivery. The code now uses Alpaca and Resend. `.env.example` is
> the accurate list of what this project needs.
>
> Do not create any credential this file asks for. Specifically:
>
> - **Parts 1–2** have you create a Google Cloud OAuth client and run
>   `scripts/setup_gmail_oauth.py`. That script does not exist in this repo,
>   and no code here reads a Google credential.
> - **Part 4's** secrets table lists four Google secrets. The workflow reads
>   `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ANTHROPIC_API_KEY`,
>   `RESEND_API_KEY`, `RESEND_FROM` and `EMAIL_TO` instead.
> - **Part 5** says the log will read "Email sent via Gmail API". It says
>   "via Resend".
> - **Part 6a** tells you to mint a `github_pat_...` token with Actions
>   read/write and paste it into a third-party scheduling site. That is a
>   real, long-lived, repo-scoped credential and the current code does not
>   need it. Part 6b then points that token at `morning.yml/dispatches` —
>   a workflow that does not exist, so it would 404 forever.
>
> This file is kept only as a record of the original setup. It is scheduled
> to be rewritten.

# Setup Guide — start to finish (~20 minutes)

Names used throughout (use these exactly, or substitute your own consistently):

| Thing | Name |
|---|---|
| GitHub repository | `momentum-burst-scanner` |
| Google Cloud project | `momentum-burst-mailer` |
| OAuth app name (consent screen) | `Momentum Burst Mailer` |
| OAuth client (Desktop app) | `momentum-burst-desktop` |

---

## Part 1 — Google Cloud: "Sign in with Google" for Gmail sending

This replaces app passwords. The app gets ONE permission — `gmail.send` —
so it can send reports as you but can never read your inbox.

1. Go to https://console.cloud.google.com and sign in with the Gmail
   account that will SEND the daily reports.
2. Top bar → project selector → **New project** → name: `momentum-burst-mailer`
   → Create → make sure it's selected.
3. **Enable the Gmail API**: left menu → *APIs & Services → Library* →
   search "Gmail API" → open it → **Enable**.
4. **Consent screen**: *APIs & Services → OAuth consent screen* (Google may
   call this "Google Auth Platform → Branding/Audience").
   - App name: `Momentum Burst Mailer`
   - User support email: your Gmail
   - Audience/User type: **External**
   - Developer contact: your Gmail → Save.
5. **IMPORTANT — publish the app**: on the consent screen / Audience page,
   change Publishing status from *Testing* to **In production** (click
   "Publish app"). If you skip this, Google expires the refresh token every
   7 days and your emails silently stop. You do NOT need to submit for
   verification — personal use is fine.
6. **Create the OAuth client**: *APIs & Services → Credentials → + Create
   credentials → OAuth client ID*.
   - Application type: **Desktop app**
   - Name: `momentum-burst-desktop` → Create.
   - Copy the **Client ID** (`...apps.googleusercontent.com`) and
     **Client Secret** (`GOCSPX-...`). Keep them handy.

## Part 2 — One-time authorization (on your own computer)

```bash
pip install google-auth-oauthlib
python scripts/setup_gmail_oauth.py
```

- Paste the Client ID and Client Secret when prompted.
- A browser opens → choose the sending Gmail account.
- You'll see **"Google hasn't verified this app"** — expected, it's YOUR
  app. Click **Advanced → Go to Momentum Burst Mailer (unsafe) → Allow**.
- The script prints three values:
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`.
  Save them — they go into GitHub secrets next. The refresh token is
  long-lived; you only redo this if you revoke access or it sits unused
  for 6+ months.

## Part 3 — Anthropic API key

1. https://console.anthropic.com → **API Keys → Create key** →
   name: `momentum-burst` → copy the `sk-ant-...` value.
2. Make sure the account has billing enabled (usage is a few cents/day
   on `claude-sonnet-4-6`).

## Part 4 — GitHub repository

1. https://github.com/new → Repository name: `momentum-burst-scanner` →
   **Private** → Create (no README/gitignore — the folder has them).
2. Push the code:

```bash
cd momentum-burst
git init
git add .
git commit -m "4% Momentum Burst automated scanner"
git branch -M main
git remote add origin https://github.com/<YOUR-USERNAME>/momentum-burst-scanner.git
git push -u origin main
```

3. **Add secrets**: repo page → *Settings → Secrets and variables →
   Actions → New repository secret*. Create these six:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` from Part 3 |
| `GOOGLE_CLIENT_ID` | from Part 2 output |
| `GOOGLE_CLIENT_SECRET` | from Part 2 output |
| `GOOGLE_REFRESH_TOKEN` | from Part 2 output |
| `GMAIL_SENDER` | the Gmail address you authorized |
| `EMAIL_TO` | manager's email (comma-separate multiple) |

4. **Enable workflows**: repo → **Actions** tab → if prompted, click
   "I understand my workflows, enable them".

## Part 5 — Test it

1. Actions tab → **Evening scan (5:30 PM ET)** → **Run workflow** →
   Run. (Manual runs bypass the time-of-day guard.)
2. Watch the log: universe download → scan batches → 2LYNCH gate →
   Claude scoring → "Email sent via Gmail API".
3. Check the recipient inbox for **[4% Burst] Evening candidates: ...**
   with the ranked table and inline charts.
4. Each run also uploads `results/*.csv` and the chart PNGs as a workflow
   artifact (Actions → the run → Artifacts) — this becomes your
   backtesting dataset.

That's everything. From now on it runs itself every weekday at 8:30 AM
and 5:30 PM Eastern, year-round, DST handled automatically.

## Troubleshooting

- **`invalid_grant` when sending** → the refresh token was revoked or the
  consent screen was left in Testing mode (Part 1 step 5). Publish the app,
  rerun Part 2, update the `GOOGLE_REFRESH_TOKEN` secret.
- **No email but run is green** → open the run log; if zero candidates
  passed the gate, the email still sends with "No candidates passed the
  quality gate today."
- **Yahoo data errors** → transient batches are retried and skipped; if it
  becomes chronic, see README "Notes" for the Polygon/Alpaca swap.
- **Change schedule** → edit the two cron lines and the guard window in
  `.github/workflows/*.yml` (they're commented).


---

## Part 6 — Exact-time triggering (external scheduler)

GitHub's own cron is best-effort and can run late or skip. For time-critical
delivery, the primary trigger is an external scheduler calling GitHub's API
at the exact minute; the crons inside the workflows are now backup-only
(they fire ~50 min later and only run if the primary never completed).

### 6a. Create a trigger token

GitHub → Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token:
- Name: `momentum-burst-trigger`
- Expiration: 1 year (set a calendar reminder to rotate)
- Repository access: Only select repositories → `momentum-burst-scanner`
- Permissions → Repository permissions → **Actions: Read and write**
  (nothing else)
Copy the `github_pat_...` value.

### 6b. Create two jobs on cron-job.org (free)

Sign up at https://cron-job.org → Create cronjob. For the MORNING job:

- Title: `momentum-morning`
- URL:
  `https://api.github.com/repos/<YOUR-USERNAME>/momentum-burst-scanner/actions/workflows/morning.yml/dispatches`
- Schedule: select **timezone America/New_York** (this makes DST automatic),
  days Mon-Fri, time e.g. **08:10** — the scan takes 10-20 min, so trigger
  ~20 min before you want the email in the inbox.
- Advanced settings:
  - Request method: **POST**
  - Headers:
    - `Authorization`: `Bearer github_pat_...` (your token)
    - `Accept`: `application/vnd.github+json`
  - Request body: `{"ref":"main"}`
- Save, then use "Test run" — a run should appear in your Actions tab
  within seconds.

Duplicate the job for the EVENING run: title `momentum-evening`, URL ending
`/evening.yml/dispatches`, time e.g. **17:10** America/New_York.

cron-job.org emails you if a trigger request fails, giving independent
monitoring of the trigger path.

### Timing summary

| Event | Time (ET) |
|---|---|
| External trigger fires | the exact minute you set |
| Workflow starts | seconds later |
| Email in inbox | ~10-20 min later (scan duration) |
| GitHub backup cron | ~9:16 AM / ~6:16 PM, runs only if primary missed |
