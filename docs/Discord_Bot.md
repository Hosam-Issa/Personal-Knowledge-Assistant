# OSRS Bingo Discord Bot

A Discord bot for running an Old School RuneScape clan bingo event. Players submit drop
screenshots for board tiles, admins approve or reject them, and a live team-scores and
player-standings leaderboard updates automatically in a dedicated channel.

## Features

- **`/register`** — players register themselves to a team automatically, based on a
  Discord role they hold (re-running it updates their info if their team/name changes).
- **`/submit`** — players submit a drop screenshot for a specific board tile, with a
  free-text drop name.
- **Admin review** — every submission is posted to an admin-only channel with **Approve**
  and **Reject** buttons. Rejecting prompts the admin for a reason. 
- **Live leaderboard channel** — each team's board (with completed tiles marked), an
  overall team standings embed, and a per-team top-players embed, all auto-updating after
  every approval.
- **`/setup_leaderboard`** — posts (or refreshes in place, if already posted) the initial
  boards and leaderboard messages.
- **`/refresh_board`** — manually force a refresh of one team's board and both
  leaderboards, in case something falls out of sync.

## Tech stack

- Python 3.11+, [discord.py](https://discordpy.readthedocs.io/) (slash commands, buttons,
  modals, persistent views)
- SQLite for storage (no external database server required)
- Pillow for rendering marked-up board images
- `python-dotenv` for configuration

## Project structure

```
osrs-bingo-bot/
├── bot/
│   ├── main.py                  # entry point — loads cogs, syncs commands, starts the bot
│   ├── config.py                # loads and exposes .env values
│   ├── cogs/
│   │   ├── submissions.py       # /submit
│   │   ├── teams.py             # /register
│   │   ├── approvals.py         # Approve/Reject buttons + rejection modal
│   │   └── leaderboards.py      # /setup_leaderboard, /refresh_board, leaderboard rendering
│   ├── rendering/
│   │   └── board_image.py       # draws completed-tile overlays onto the board image
│   └── db/
│       ├── models.py            # CREATE TABLE statements
│       ├── database.py          # connection + all queries
│       ├── seed.py              # seeds teams + tiles on first run
│       └── bingo.db             # SQLite database file (created automatically)
├── assets/
│   └── board_base.png           # the clean, unmarked board template image
├── images/
│   ├── submissions/             # saved screenshots from player submissions
│   └── boards/                  # generated, marked-up board images per team
├── .env                          
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

### 1. Prerequisites

- Python 3.11 or newer
- A Discord application + bot token (from the
  [Discord Developer Portal](https://discord.com/developers/applications))
- A Discord server with:
  - One role per team
  - An admin role for approvers
  - A channel for admin review
  - A channel for the public leaderboard

### 2. Clone and install

```bash
git clone https://github.com/Hosam-Issa/osrs-bot
cd osrs-bingo-bot
python -m venv venv
venv\Scripts\Activate.ps1      # Windows PowerShell
# source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id
ADMIN_ROLE_ID=your_admin_role_id
ADMIN_CHANNEL_ID=your_admin_review_channel_id
LEADERBOARD_CHANNEL_ID=your_leaderboard_channel_id
```

### 4. Set team role IDs

Team role IDs are stored in the database, not `.env`. After creating your 4 team roles in
Discord, either:

- edit the placeholder values in `bot/db/seed.py` before first run, or
- run `UPDATE teams SET role_id = ? WHERE name = ?` directly against `bingo.db` afterward

### 5. Add your board image

Place a square (or near-square) image of your bingo board at `assets/board_base.png`. It
will automatically be cropped/resized to a clean grid on render — no need for pixel-perfect
dimensions.

### 6. Run the bot

```bash
python -m bot.main
```

On first run, this creates `bingo.db`, creates all tables, and seeds the 4 teams and 25
tiles (with the center tile marked as free).

### 7. Post the leaderboard

In Discord, run `/setup_leaderboard` (as an admin) in your leaderboard channel. This posts
the 4 team boards, the team standings embed, and the player standings embed. It's safe to
run again later — it updates the existing messages in place rather than posting duplicates.

## Usage flow

1. Players run `/register osrs_name:<name>` (requires having a team role already).
2. Players run `/submit tile:<tile> drop_name:<name> image:<screenshot>` to submit a drop.
3. The bot posts the submission to the admin channel with Approve/Reject buttons.
4. An admin clicks Approve (marks the tile complete for that team, updates all
   leaderboards) or Reject (prompts for a reason, no leaderboard changes).
5. If a leaderboard message ever looks out of sync, an admin can run
   `/refresh_board team_id:<id>` or re-run `/setup_leaderboard`.

## Notes on tile point values

By default, all seeded tiles share the same point value. To run a weighted bingo (some
tiles worth more than others), update the `point_value` column on individual rows in the
`tiles` table before the event starts.

## Known limitations / possible future work

- Team role IDs must be set manually after seeding (see Setup step 4).
- Duplicate pending submissions for the same tile are currently allowed (not
  auto-superseded) — an admin can reject the unwanted one manually.
- No Google Sheets mirror yet (planned).
- Currently intended for a single guild/server (`GUILD_ID` in `.env`).

## Deployment

This bot is designed to run continuously (e.g. on a Raspberry Pi) via a process manager
such as `systemd`, so it restarts automatically on crash or reboot. See project notes for
Raspberry Pi setup steps.