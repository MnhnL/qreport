# qreport

A minimal Flask web app that lets staff scan a QR code on a physical exhibit, fill in a short report, and send it by email to a configured recipient. Objects, SMTP settings, and the email template are managed through a web admin panel.

## Features

- `/object/<id>` — public report form (optional title, description, free-text message)
- `/thank_you` — configurable thank-you page with optional auto-redirect
- `/admin` — admin panel secured by nginx basic auth; manages objects, SMTP, email template, and global defaults
- QR code download per object (PNG + SVG) linking to the form
- Per-object override of recipient email, title, and description; falls back to global defaults
- Plain INI file (`config.ini`) as persistent config — no database

## Requirements

- Python 3.10+
- nginx (for basic auth on `/admin`)

Python dependencies (see `requirements.txt`):

```
flask
segno
gunicorn
```

## Running locally

```sh
python -m venv venv
source venv/bin/activate
pip install -e .
python -m qreport.app
```

The app listens on `http://127.0.0.1:5000`. A default `config.ini` is created on first run next to the package directory.

## Configuration

`config.ini` is created automatically with defaults on first start. All settings are editable through the admin panel at `/admin`.

| Section | Key | Description |
|---|---|---|
| `[app]` | `base_url` | Base URL used to build QR code links |
| `[app]` | `redirect_url` | URL to redirect to after thank-you page (blank = no redirect) |
| `[app]` | `redirect_timeout` | Seconds before redirect (default: 5) |
| `[defaults]` | `title` | Default form title |
| `[defaults]` | `email` | Default recipient email |
| `[defaults]` | `description` | Default message shown above the form |
| `[smtp]` | `host`, `port`, `user`, `password`, `from` | SMTP credentials |
| `[smtp]` | `use_tls` | `true` to enable STARTTLS |
| `[smtp]` | `debug_mail` | `true` to print emails to stderr instead of sending |
| `[template]` | `subject` | Email subject (supports `{object_id}`, `{date}`, `{time}`, `{message}`) |
| `[template]` | `body` | Email body (same variables) |
| `[template]` | `thankyou` | Text shown on the thank-you page |
| `[object:ID]` | `title`, `email`, `description` | Per-object overrides; blank falls back to `[defaults]` |

## Deployment

The Makefile targets wrap build, rsync, and systemd management via SSH. Copy `Makefile` and fill in the three variables:

```makefile
app_name     = qreport
install_host = user@your.server
instance_name = qreport.example.com
```

Then:

```sh
make            # build + prepare + update (first deploy)
make update     # reinstall package and restart
make restart    # restart service only
```

`make prepare` runs `deploy_prepare.sh` on the server (once per instance): installs the systemd service, configures nginx, and creates the venv.

### nginx basic auth

```sh
htpasswd -c /usr/local/etc/django/<instance_name>/.htpasswd <username>
```

The nginx config proxies `/admin` behind basic auth and forwards everything else to the gunicorn socket.

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).
