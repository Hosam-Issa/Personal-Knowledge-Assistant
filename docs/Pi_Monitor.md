# Pi System Monitor

A real-time system monitoring dashboard for the Raspberry Pi, built from scratch with Python and Flask. It collects live hardware metrics, persists historical data, triggers threshold-based alerts, and displays everything through a browser dashboard, running continuously as a background service.

![Dashboard Screenshot](docs/dashboard.png)

## Features

- **Live system metrics** — CPU usage, temperature, memory, disk, and network I/O, collected directly from the Pi's Linux interfaces (`psutil`, `/sys/class/thermal`)
- **REST API** — clean JSON endpoints for current metrics, historical data, and alert status
- **Real-time dashboard** — auto-refreshing browser UI with a live-updating chart (Chart.js)
- **Historical logging** — readings persisted to SQLite via a background thread, independent of whether the dashboard is open
- **Threshold alerting** — configurable CPU/temperature/memory thresholds, logged to file and surfaced on the dashboard
- **Runs on boot** — deployed as a `systemd` service with automatic restart on failure

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────────┐
│  metrics.py │────▶│    app.py    │─────▶│  templates/    │
│ (psutil +   │      │  (Flask API) │      │  index.html    │
│  /sys temp) │      └──────┬───────┘      │ (dashboard JS) │
└─────────────┘             │              └───────▲────────┘
                            │                      │
                    ┌────────▼────────┐            │
                    │  storage.py     │            │
                    │  (SQLite)       │◀───────────┘
                    └────────┬────────┘     fetch('/api/...')
                             │
                    ┌────────▼────────┐
                    │  alerts.py      │
                    │ (threshold      │
                    │  checks + log)  │
                    └─────────────────┘
```

A background thread inside `app.py` calls `metrics.py` every 10 seconds, saves the reading to SQLite via `storage.py`, and checks it against alert thresholds via `alerts.py` — independent of any browser being open. The Flask API exposes this data over HTTP, and the dashboard polls it to stay live.

## Tech Stack

- **Hardware:** Raspberry Pi 4 Model B, Raspberry Pi OS (Debian-based Linux)
- **Backend:** Python, Flask, psutil, SQLite
- **Frontend:** HTML/CSS/JavaScript, Chart.js
- **Deployment:** systemd service (auto-start on boot, auto-restart on crash)

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Dashboard (HTML) |
| `GET /api/metrics` | Current system metrics (JSON) |
| `GET /api/history` | Recent historical readings from SQLite (JSON) |
| `GET /api/check` | Current alert status against configured thresholds (JSON) |

## Setup

**On the Raspberry Pi:**

```bash
git clone https://github.com/Hosam-Issa/pi-monitor.git
cd pi-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Visit `http://<pi-ip>:5000` from any device on the same network.

**To run permanently as a service (survives reboots, no terminal needed):**

Create `/etc/systemd/system/pi-monitor.service`:

```ini
[Unit]
Description=Pi System Monitor
After=network.target

[Service]
User=<your-username>
WorkingDirectory=/home/<your-username>/pi-monitor
ExecStart=/home/<your-username>/pi-monitor/venv/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-monitor.service
sudo systemctl start pi-monitor.service
```

## Alert Thresholds

Configurable in `alerts.py`:

```python
THRESHOLDS = {
    "cpu_percent": 85,
    "temperature_c": 70,
    "memory_percent": 90,
}
```

Triggered alerts are logged to `alerts.log` and returned by `/api/check`.

## Possible Future Improvements

- Multi-device support (monitor several Pis from one dashboard)
- Webhook/email notifications on alert trigger, instead of just logging
- HTTPS support
- Docker containerization for easier deployment
- Log rotation for `alerts.log` and the SQLite database