import configparser
import io
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText

import segno
from flask import Flask, abort, redirect, render_template, request, send_file, url_for

CONFIG_FILE = os.environ.get(
    'QREPORT_CONFIG',
    os.path.join(os.path.dirname(__file__), '..', 'config.ini'),
)

app = Flask(__name__)


# ── config helpers ────────────────────────────────────────────────────────────

def load_config():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(CONFIG_FILE)
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        cfg.write(f)


def get_objects(cfg):
    return {
        s[7:]: dict(cfg[s])
        for s in cfg.sections()
        if s.startswith('object:')
    }


def resolve(cfg, section, field):
    """Object-level value if non-empty, else global default."""
    val = cfg.get(section, field, fallback='').strip()
    return val if val else cfg.get('defaults', field, fallback='')


class _SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def render_template_str(tmpl, **kwargs):
    try:
        return tmpl.format_map(_SafeDict(**kwargs))
    except ValueError:
        return tmpl


# ── mail ──────────────────────────────────────────────────────────────────────

def _send_mail(cfg, *, to, subject, body):
    if cfg.get('smtp', 'debug_mail', fallback='false').lower() == 'true':
        print(
            f'--- debug mail ---\nTo: {to}\nSubject: {subject}\n\n{body}\n------------------',
            file=sys.stderr,
        )
        return

    smtp_host = cfg.get('smtp', 'host', fallback='localhost')
    smtp_port = int(cfg.get('smtp', 'port', fallback='25'))
    smtp_user = cfg.get('smtp', 'user', fallback='')
    smtp_pass = cfg.get('smtp', 'password', fallback='')
    smtp_from = cfg.get('smtp', 'from', fallback='noreply@example.com')
    use_tls   = cfg.get('smtp', 'use_tls', fallback='false').lower() == 'true'

    msg = MIMEText(body, 'plain')
    msg['From'] = smtp_from
    msg['To'] = to
    msg['Subject'] = subject

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if use_tls:
            server.starttls()
        if smtp_user:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)


# ── public form ───────────────────────────────────────────────────────────────

@app.route('/object/<obj_id>', methods=['GET', 'POST'])
def object_form(obj_id):
    cfg = load_config()
    section = f'object:{obj_id}'
    if section not in cfg:
        abort(404)

    obj_title = resolve(cfg, section, 'title')
    obj_email = resolve(cfg, section, 'email')
    obj_desc  = resolve(cfg, section, 'description')

    error = None

    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        now = datetime.now()
        fmt_vars = dict(
            object_id=obj_id,
            date=now.strftime('%Y-%m-%d'),
            time=now.strftime('%H:%M:%S'),
            message=message or '[No message]',
        )
        subject = render_template_str(
            cfg.get('template', 'subject', fallback='Report'), **fmt_vars
        )
        body = render_template_str(
            cfg.get('template', 'body', fallback='{message}'), **fmt_vars
        )
        try:
            _send_mail(cfg, to=obj_email, subject=subject, body=body)
            return redirect(url_for('thank_you'))
        except Exception as e:
            error = f'Failed to send email: {e}'

    return render_template(
        'form.html',
        obj_title=obj_title,
        obj_desc=obj_desc,
        error=error,
    )


@app.route('/thank_you')
def thank_you():
    cfg = load_config()
    thankyou     = cfg.get('template', 'thankyou',        fallback='Thank you. Your message has been sent.')
    redirect_url = cfg.get('app',      'redirect_url',    fallback='')
    redirect_timeout = cfg.get('app',  'redirect_timeout', fallback='5')
    return render_template('thanks.html', thankyou=thankyou,
                           redirect_url=redirect_url, redirect_timeout=redirect_timeout)


# ── admin panel ───────────────────────────────────────────────────────────────

@app.route('/admin')
def admin():
    cfg = load_config()
    return render_template(
        'admin.html',
        objects=get_objects(cfg),
        defaults={k: cfg.get('defaults', k, fallback='') for k in ('title', 'email', 'description')},
        template={k: cfg.get('template', k, fallback='') for k in ('subject', 'body', 'thankyou')},
        smtp={k: cfg.get('smtp', k, fallback='') for k in ('host', 'port', 'user', 'password', 'from', 'use_tls', 'debug_mail')},
        base_url=cfg.get('app', 'base_url', fallback=request.host_url.rstrip('/')),
        redirect_url=cfg.get('app', 'redirect_url', fallback=''),
        redirect_timeout=cfg.get('app', 'redirect_timeout', fallback='5'),
    )


@app.route('/admin/save', methods=['POST'])
def admin_save():
    cfg = load_config()
    for section in ('app', 'defaults', 'smtp', 'template'):
        if section not in cfg:
            cfg[section] = {}

    cfg['app']['base_url']         = request.form.get('base_url', '').rstrip('/')
    cfg['app']['redirect_url']     = request.form.get('redirect_url', '')
    cfg['app']['redirect_timeout'] = request.form.get('redirect_timeout', '5')

    cfg['defaults']['title']       = request.form.get('default_title', '')
    cfg['defaults']['email']       = request.form.get('default_email', '')
    cfg['defaults']['description'] = request.form.get('default_description', '')

    for field in ('host', 'port', 'user', 'from'):
        cfg['smtp'][field] = request.form.get(field, '')
    new_password = request.form.get('password', '')
    if new_password:
        cfg['smtp']['password'] = new_password
    cfg['smtp']['use_tls']    = 'true' if request.form.get('use_tls')    else 'false'
    cfg['smtp']['debug_mail'] = 'true' if request.form.get('debug_mail') else 'false'

    cfg['template']['subject'] = request.form.get('subject', '')
    cfg['template']['body']    = request.form.get('body', '')
    cfg['template']['thankyou'] = request.form.get('thankyou', '')

    save_config(cfg)
    return redirect(url_for('admin'))


@app.route('/admin/object/add', methods=['POST'])
def admin_add_object():
    cfg = load_config()
    obj_id = request.form.get('id', '').strip()
    if not obj_id or not obj_id.isalnum():
        return redirect(url_for('admin'))
    section = f'object:{obj_id}'
    if section not in cfg:
        cfg[section] = {
            'title': request.form.get('title', ''),
            'email': request.form.get('email', ''),
            'description': request.form.get('description', ''),
        }
        save_config(cfg)
    return redirect(url_for('admin'))


@app.route('/admin/object/edit/<obj_id>', methods=['POST'])
def admin_edit_object(obj_id):
    cfg = load_config()
    section = f'object:{obj_id}'
    if section not in cfg:
        abort(404)
    cfg[section]['title'] = request.form.get('title', '')
    cfg[section]['email'] = request.form.get('email', '')
    cfg[section]['description'] = request.form.get('description', '')
    save_config(cfg)
    return redirect(url_for('admin'))


@app.route('/admin/object/delete/<obj_id>', methods=['POST'])
def admin_delete_object(obj_id):
    cfg = load_config()
    section = f'object:{obj_id}'
    if section in cfg:
        cfg.remove_section(section)
        save_config(cfg)
    return redirect(url_for('admin'))


# ── QR code downloads ─────────────────────────────────────────────────────────

@app.route('/admin/object/qr/<obj_id>.<fmt>')
def object_qr(obj_id, fmt):
    if fmt not in ('png', 'svg'):
        abort(400)
    cfg = load_config()
    if f'object:{obj_id}' not in cfg:
        abort(404)

    base_url = cfg.get('app', 'base_url', fallback=request.host_url.rstrip('/'))
    url = f'{base_url}/object/{obj_id}'
    qr = segno.make(url, error='m')

    if fmt == 'png':
        buf = io.BytesIO()
        qr.save(buf, kind='png', scale=10)
        buf.seek(0)
        return send_file(buf, mimetype='image/png',
                         as_attachment=True, download_name=f'qr-{obj_id}.png')

    buf = io.BytesIO()
    qr.save(buf, kind='svg', scale=5, xmldecl=True)
    buf.seek(0)
    return send_file(buf, mimetype='image/svg+xml',
                     as_attachment=True, download_name=f'qr-{obj_id}.svg')


# ── startup ───────────────────────────────────────────────────────────────────

def init_config():
    if os.path.exists(CONFIG_FILE):
        return
    cfg = configparser.ConfigParser(interpolation=None)
    cfg['app'] = {
        'base_url': 'http://localhost:5000',
        'redirect_url': '',
        'redirect_timeout': '5',
    }
    cfg['defaults'] = {'title': '', 'email': '', 'description': ''}
    cfg['smtp'] = {
        'host': 'localhost',
        'port': '25',
        'user': '',
        'password': '',
        'from': 'noreply@example.com',
        'use_tls': 'false',
        'debug_mail': 'false',
    }
    cfg['template'] = {
        'subject': 'Report for {object_id} — {date}',
        'body': (
            'Object: {object_id}\n'
            'Date:   {date}\n'
            'Time:   {time}\n'
            '\n'
            'Message:\n'
            '{message}'
        ),
        'thankyou': 'Thank you. Your message has been sent.',
    }
    save_config(cfg)


init_config()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
