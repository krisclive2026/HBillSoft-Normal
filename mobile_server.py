"""
mobile_server.py  –  HBILLSOFT Mobile Ordering Server
Runs as a background Flask HTTP server so customers can
browse the menu and place orders from their mobile browser.
"""
 
import os
import sys
import json
import uuid
import datetime
import sqlite3
import socket
import threading
 
# ── Path helpers (same pattern as main.py) ───────────────────────────────────
_APP_DIR  = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_APP_DIR, '.hbillsoft')
DB_FILE   = os.path.join(_DATA_DIR, 'sales_data.db')
 
def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(_APP_DIR, filename)
 
# ── Detect local LAN IP ───────────────────────────────────────────────────────
def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'
 
MOBILE_PORT = 5050
LOCAL_IP    = get_local_ip()
MOBILE_URL  = f'http://{LOCAL_IP}:{MOBILE_PORT}'
 
# ── Pending orders helpers ────────────────────────────────────────────────────
def init_pending_table():
    """Ensure the pending_mobile_orders table exists."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pending_mobile_orders (
                id          TEXT PRIMARY KEY,
                received_at TEXT NOT NULL,
                customer    TEXT,
                table_no    TEXT,
                items_json  TEXT NOT NULL,
                note        TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[MobileServer] init_pending_table error: {e}')
 
def save_pending_order(order_id, customer, table_no, items, note=''):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            'INSERT INTO pending_mobile_orders (id, received_at, customer, table_no, items_json, note) VALUES (?,?,?,?,?,?)',
            (order_id, datetime.datetime.now().isoformat(), customer, table_no, json.dumps(items, ensure_ascii=False), note)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f'[MobileServer] save_pending_order error: {e}')
        return False
 
def get_all_pending() -> list:
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT * FROM pending_mobile_orders ORDER BY received_at ASC'
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                'id':          r['id'],
                'received_at': r['received_at'],
                'customer':    r['customer'] or '',
                'table_no':    r['table_no']  or '',
                'items':       json.loads(r['items_json']),
                'note':        r['note']  or '',
            })
        return result
    except Exception as e:
        print(f'[MobileServer] get_all_pending error: {e}')
        return []
 
def delete_pending(order_id: str) -> bool:
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('DELETE FROM pending_mobile_orders WHERE id = ?', (order_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f'[MobileServer] delete_pending error: {e}')
        return False
 
def get_menu_and_settings():
    """Read menu, categories and settings directly from SQLite."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
 
        menu_rows = conn.execute(
            'SELECT id, name, price, category, image, image_data FROM menu_items ORDER BY sort_order, id'
        ).fetchall()
        menu = []
        for r in menu_rows:
            item = {'id': r['id'], 'name': r['name'], 'price': r['price'],
                    'category': r['category'], 'image': r['image']}
            if r['image_data']:
                item['imageData'] = r['image_data']
            menu.append(item)
 
        cat_rows = conn.execute(
            'SELECT id, name, icon FROM categories ORDER BY sort_order, rowid'
        ).fetchall()
        categories = [{'id': r['id'], 'name': r['name'], 'icon': r['icon']} for r in cat_rows]
 
        settings_row = conn.execute('SELECT data FROM app_settings WHERE id=1').fetchone()
        settings = json.loads(settings_row['data']) if settings_row else {}
 
        conn.close()
        return menu, categories, settings
    except Exception as e:
        print(f'[MobileServer] get_menu_and_settings error: {e}')
        return [], [], {}
 
# ── Flask app ─────────────────────────────────────────────────────────────────
_flask_app = None
 
def create_flask_app():
    try:
        from flask import Flask, jsonify, request, send_from_directory
    except ImportError:
        print('[MobileServer] Flask not installed. Run: pip install flask')
        return None
 
    app = Flask(__name__)
 
    @app.after_request
    def add_cors(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
 
    @app.route('/')
    def index():
        mobile_html = resource_path('mobile_order.html')
        return send_from_directory(os.path.dirname(mobile_html),
                                   os.path.basename(mobile_html))
 
    @app.route('/api/menu')
    def api_menu():
        menu, categories, _ = get_menu_and_settings()
        return jsonify({'ok': True, 'menu': menu, 'categories': categories})
 
    @app.route('/api/settings')
    def api_settings():
        _, _, settings = get_menu_and_settings()
        return jsonify({
            'ok':             True,
            'restaurantName': settings.get('restaurantName', 'Restaurant'),
            'currency':       settings.get('currency', '₹'),
            'address':        settings.get('address', ''),
        })
 
    @app.route('/api/order', methods=['POST'])
    def api_order():
        try:
            data     = request.get_json(force=True)
            items    = data.get('items', [])
            customer = data.get('customer', '').strip()
            table_no = data.get('table_no', '').strip()
            note     = data.get('note', '').strip()
 
            if not items:
                return jsonify({'ok': False, 'error': 'No items in order'}), 400
 
            order_id = str(uuid.uuid4())[:8].upper()
            ok = save_pending_order(order_id, customer, table_no, items, note)
            if ok:
                return jsonify({'ok': True, 'order_id': order_id})
            else:
                return jsonify({'ok': False, 'error': 'Database error'}), 500
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
 
    @app.route('/api/pending')
    def api_pending():
        orders = get_all_pending()
        return jsonify({'ok': True, 'orders': orders})
 
    @app.route('/api/pending/<order_id>', methods=['DELETE'])
    def api_dismiss(order_id):
        ok = delete_pending(order_id)
        return jsonify({'ok': ok})
 
    return app
 
 
# ── Public start function ─────────────────────────────────────────────────────
def start_mobile_server():
    """
    Call this from main.py before webview.start().
    Runs Flask in a daemon thread so it dies when the main process exits.
    """
    init_pending_table()
 
    flask_app = create_flask_app()
    if flask_app is None:
        return  # Flask not available — skip silently
 
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)   # suppress Flask request logs in console
 
    def _run():
        flask_app.run(host='0.0.0.0', port=MOBILE_PORT, debug=False, use_reloader=False)
 
    t = threading.Thread(target=_run, daemon=True, name='MobileOrderServer')
    t.start()
    print(f'[MobileServer] Listening on {MOBILE_URL}')
