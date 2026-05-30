"""
mobile_order_server.py  —  RestoBill Mobile Order Server
=========================================================
Waiter scans a QR code → phone browser opens a web form
→ submits order → main app receives it via callback.

QR CODE BEHAVIOUR:
  - Generated ONCE at server start from the fixed LAN IP URL
  - Stored as self._qr_pil (PIL image) — never regenerated
  - show_qr_window() just displays the cached image instantly
  - Menu changes reflect live when waiters refresh the page
  - If mobile_url_override is set in settings, that URL is used for QR

Dependencies (install once):
    pip install qrcode[pil] pillow

The server runs on port 5000 by default.
"""

import json
import socket
import threading
import time
import io
import os
import sys
import subprocess
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote_plus
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

# ── Optional QR-code library ────────────────────────────────
try:
    import qrcode
    from PIL import Image, ImageTk
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


# ── Detect LAN IP ───────────────────────────────────────────
def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── Safe JSON embedding helper ───────────────────────────────
def _safe_json_for_html(data) -> str:
    raw = json.dumps(data, ensure_ascii=True)
    raw = raw.replace("</", "<\\/")
    raw = raw.replace("<!--", "<\\!--")
    raw = raw.replace("\u2028", "\\u2028")
    raw = raw.replace("\u2029", "\\u2029")
    return raw


# ── HTML templates ──────────────────────────────────────────
_HTML_ORDER_FORM = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>RestoBill — Place Order</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0d0d0d; --surface: #161616; --card: #1e1e1e; --border: #2a2a2a;
    --accent: #FF6B35; --accent2: #FFA500; --text: #f0f0f0; --muted: #666;
    --green: #4CAF50; --red: #e53935; --radius: 14px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; min-height: 100vh; padding-bottom: 80px; }
  header { background: linear-gradient(135deg, #1a0800 0%, #0d0d0d 100%); padding: 14px 20px 12px; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 100; backdrop-filter: blur(10px); }
  .header-inner { display: flex; align-items: center; gap: 10px; }
  .header-logo { width: 42px; height: 42px; border-radius: 8px; object-fit: cover; flex-shrink: 0; }
  header h1 { font-family: 'Playfair Display', serif; font-size: 22px; color: var(--accent); letter-spacing: 0.5px; }
  header p { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .refresh-btn { position: absolute; right: 16px; top: 16px; background: none; border: 1px solid var(--accent); color: var(--accent); border-radius: 8px; padding: 6px 12px; font-size: 12px; cursor: pointer; font-family: 'DM Sans', sans-serif; }
  .container { max-width: 480px; margin: 0 auto; padding: 16px; }
  .table-bar { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 10px; }
  .table-bar label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; display: block; margin-bottom: 4px; }
  .table-bar input { width: 100%; background: var(--card); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: 'DM Sans', sans-serif; font-size: 16px; padding: 12px 14px; outline: none; }
  .table-bar input:focus { border-color: var(--accent); }
  .cat-tabs { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; margin-bottom: 14px; scrollbar-width: none; }
  .cat-tabs::-webkit-scrollbar { display: none; }
  .cat-tab { flex-shrink: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 20px; color: var(--muted); font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 500; padding: 7px 16px; cursor: pointer; transition: all 0.2s; }
  .cat-tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
  .search-wrap { position: relative; margin-bottom: 14px; }
  .search-wrap input { width: 100%; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; color: var(--text); font-family: 'DM Sans', sans-serif; font-size: 15px; padding: 11px 14px 11px 38px; outline: none; }
  .search-wrap input:focus { border-color: var(--accent); }
  .search-wrap .icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--muted); font-size: 16px; }
  .menu-grid { display: flex; flex-direction: column; gap: 8px; }
  .menu-item { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 13px 14px; display: flex; align-items: center; gap: 12px; transition: border-color 0.2s, transform 0.15s; cursor: pointer; }
  .menu-item:active { transform: scale(0.98); }
  .menu-item.in-cart { border-color: var(--accent); }
  .item-info { flex: 1; min-width: 0; }
  .item-name { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .item-cat { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .item-price { font-size: 15px; font-weight: 700; color: var(--accent2); white-space: nowrap; }
  .qty-ctrl { display: flex; align-items: center; gap: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; flex-shrink: 0; }
  .qty-ctrl button { background: none; border: none; color: var(--accent); font-size: 20px; width: 36px; height: 36px; cursor: pointer; font-weight: 700; display: flex; align-items: center; justify-content: center; transition: background 0.15s; -webkit-tap-highlight-color: transparent; }
  .qty-ctrl button:active { background: #2a2a2a; }
  .qty-ctrl span { min-width: 30px; text-align: center; font-size: 15px; font-weight: 600; }
  .qty-zero { display: none; } .qty-has { display: flex; }
  .cart-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--accent); padding: 0; transform: translateY(100%); transition: transform 0.3s cubic-bezier(.22,.61,.36,1); z-index: 200; max-width: 480px; margin: 0 auto; }
  .cart-bar.visible { transform: translateY(0); }
  .cart-bar-inner { display: flex; align-items: center; padding: 14px 20px; gap: 12px; cursor: pointer; }
  .cart-count { background: rgba(0,0,0,0.25); border-radius: 20px; padding: 4px 10px; font-size: 13px; font-weight: 700; color: #fff; }
  .cart-label { flex: 1; font-size: 15px; font-weight: 700; color: #fff; }
  .cart-total { font-size: 16px; font-weight: 800; color: #fff; }
  .sheet-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 300; }
  .sheet-overlay.open { display: block; }
  .sheet { position: fixed; bottom: 0; left: 0; right: 0; background: var(--surface); border-radius: 20px 20px 0 0; max-height: 80vh; overflow-y: auto; z-index: 400; transform: translateY(100%); transition: transform 0.35s cubic-bezier(.22,.61,.36,1); max-width: 480px; margin: 0 auto; }
  .sheet.open { transform: translateY(0); }
  .sheet-handle { width: 40px; height: 4px; background: var(--border); border-radius: 2px; margin: 12px auto 0; }
  .sheet-title { font-family: 'Playfair Display', serif; font-size: 20px; color: var(--accent); padding: 16px 20px 8px; border-bottom: 1px solid var(--border); }
  .cart-item { display: flex; align-items: center; gap: 12px; padding: 12px 20px; border-bottom: 1px solid var(--border); }
  .cart-item-name { flex: 1; font-size: 14px; font-weight: 500; }
  .cart-item-price { font-size: 13px; color: var(--muted); margin-top: 2px; }
  .cart-item-total { font-size: 14px; font-weight: 700; color: var(--accent2); }
  .sheet-footer { padding: 16px 20px; border-top: 1px solid var(--border); }
  .sheet-subtotal { display: flex; justify-content: space-between; font-size: 15px; font-weight: 600; margin-bottom: 14px; }
  .sheet-subtotal span:last-child { color: var(--accent2); }
  .btn-place { width: 100%; background: var(--accent); color: #fff; border: none; border-radius: 12px; font-family: 'DM Sans', sans-serif; font-size: 16px; font-weight: 700; padding: 15px; cursor: pointer; letter-spacing: 0.3px; transition: opacity 0.2s; }
  .btn-place:active { opacity: 0.85; } .btn-place:disabled { opacity: 0.5; cursor: not-allowed; }
  .note-field { width: 100%; background: var(--card); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: 'DM Sans', sans-serif; font-size: 14px; padding: 10px 12px; outline: none; margin-bottom: 12px; resize: none; }
  .note-field:focus { border-color: var(--accent); }
  .toast { position: fixed; top: 80px; left: 50%; transform: translateX(-50%) translateY(-20px); background: var(--green); color: #fff; border-radius: 10px; padding: 10px 20px; font-size: 14px; font-weight: 600; opacity: 0; transition: all 0.3s; z-index: 999; white-space: nowrap; }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  .toast.error { background: var(--red); }
  .empty-state { text-align: center; padding: 48px 20px; color: var(--muted); }
  .empty-state .icon { font-size: 40px; margin-bottom: 10px; }
  .empty-state p { font-size: 14px; }
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <img class="header-logo" src="data:image/jpeg;base64,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" alt="Krisc Logo">
    <div>
      <h1>RestoBill</h1>
      <p>Waiter Order Terminal</p>
    </div>
  </div>
  <button class="refresh-btn" onclick="loadMenu()">&#8635; Refresh Menu</button>
</header>
<div class="container">
  <div class="table-bar">
    <div>
      <label>Table Number</label>
      <input type="text" id="tableInput" placeholder="e.g. T01, T05 ..." inputmode="text" autocomplete="off" style="text-transform:uppercase">
    </div>
    <div>
      <label>Waiter Name</label>
      <input type="text" id="waiterInput" placeholder="Your name (optional)" autocomplete="off">
    </div>
  </div>
  <div class="cat-tabs" id="catTabs"><button class="cat-tab active" data-cat="All">All</button></div>
  <div class="search-wrap">
    <span class="icon">&#128269;</span>
    <input type="text" id="searchInput" placeholder="Search menu..." oninput="filterSearch()" autocomplete="off">
  </div>
  <div class="menu-grid" id="menuGrid">
    <div class="empty-state"><div class="icon">&#9203;</div><p>Loading menu...</p></div>
  </div>
</div>
<div class="cart-bar" id="cartBar" onclick="openSheet()">
  <div class="cart-bar-inner">
    <span class="cart-count" id="cartCount">0</span>
    <span class="cart-label">View Order</span>
    <span class="cart-total" id="cartTotal">Rs. 0</span>
  </div>
</div>
<div class="sheet-overlay" id="sheetOverlay" onclick="closeSheet()"></div>
<div class="sheet" id="cartSheet">
  <div class="sheet-handle"></div>
  <div class="sheet-title">Your Order</div>
  <div id="sheetItems"></div>
  <div class="sheet-footer">
    <div class="sheet-subtotal"><span>Total</span><span id="sheetTotal">Rs. 0</span></div>
    <textarea class="note-field" id="noteInput" placeholder="Add a note (optional)..." rows="2"></textarea>
    <button class="btn-place" id="placeBtn" onclick="placeOrder()">Place Order</button>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>var _MENU_DATA_ = __MENU_DATA__;</script>
<script>
var MENU=[],CURRENCY='Rs.',cart={},activeCat='All';
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function escAttr(s){return String(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function _initMenu(){try{var raw=(typeof _MENU_DATA_!=='undefined')?_MENU_DATA_:{};MENU=Array.isArray(raw.items)?raw.items:[];CURRENCY=raw.currency||'Rs.';}catch(e){MENU=[];}}
function loadMenu(){fetch('/menu').then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(function(data){MENU=Array.isArray(data.items)?data.items:[];CURRENCY=data.currency||'Rs.';buildCatTabs();renderMenu();showToast('Menu refreshed');}).catch(function(){showToast('Could not refresh menu',true);});}
function buildCatTabs(){var cats=[];for(var i=0;i<MENU.length;i++){var c=MENU[i].category;if(c&&cats.indexOf(c)===-1)cats.push(c);}cats.sort();var html='<button class="cat-tab active" data-cat="All">All</button>';for(var j=0;j<cats.length;j++)html+='<button class="cat-tab" data-cat="'+escAttr(cats[j])+'">'+escHtml(cats[j])+'</button>';var container=document.getElementById('catTabs');container.innerHTML=html;container.onclick=function(e){var btn=e.target.closest('.cat-tab');if(btn&&btn.dataset.cat)filterCat(btn.dataset.cat);};}
function renderMenu(){var q=document.getElementById('searchInput').value.trim().toLowerCase();var grid=document.getElementById('menuGrid');var items=[];for(var i=0;i<MENU.length;i++){var m=MENU[i];var catOk=(activeCat==='All')||(m.category===activeCat);var qOk=!q||m.name.toLowerCase().indexOf(q)!==-1;if(catOk&&qOk)items.push(m);}if(!items.length){grid.innerHTML='<div class="empty-state"><div class="icon">&#127374;</div><p>No items found</p></div>';return;}var html='';for(var k=0;k<items.length;k++){var m=items[k];var qty=cart[m.name]?cart[m.name].qty:0;var inCart=qty>0?'in-cart':'';var price=parseFloat(m.price);var cat=m.category||'';html+='<div class="menu-item '+inCart+'"><div class="item-info"><div class="item-name">'+escHtml(m.name)+'</div><div class="item-cat">'+escHtml(cat)+'</div></div><div class="item-price">'+CURRENCY+price.toFixed(0)+'</div>';if(qty>0){html+='<div class="qty-ctrl qty-has"><button ontouchstart="" data-name="'+escAttr(m.name)+'" data-price="'+price+'" data-cat="'+escAttr(cat)+'" data-delta="-1" onclick="handleQty(this)">&minus;</button><span>'+qty+'</span><button ontouchstart="" data-name="'+escAttr(m.name)+'" data-price="'+price+'" data-cat="'+escAttr(cat)+'" data-delta="1" onclick="handleQty(this)">+</button></div>';}else{html+='<button style="display:flex;width:36px;height:36px;border-radius:8px;background:var(--accent);border:none;color:#fff;font-size:22px;cursor:pointer;align-items:center;justify-content:center;flex-shrink:0;" ontouchstart="" data-name="'+escAttr(m.name)+'" data-price="'+price+'" data-cat="'+escAttr(cat)+'" data-delta="1" onclick="handleQty(this)">+</button>';}html+='</div>';}grid.innerHTML=html;}
function handleQty(btn){var name=btn.getAttribute('data-name');var price=parseFloat(btn.getAttribute('data-price'));var cat=btn.getAttribute('data-cat');var delta=parseInt(btn.getAttribute('data-delta'),10);if(!cart[name])cart[name]={qty:0,price:price,category:cat};cart[name].qty=Math.max(0,cart[name].qty+delta);if(cart[name].qty===0)delete cart[name];renderMenu();updateCartBar();}
function filterCat(cat){activeCat=cat;var tabs=document.querySelectorAll('.cat-tab');for(var i=0;i<tabs.length;i++)tabs[i].classList.toggle('active',tabs[i].textContent.trim()===cat);renderMenu();}
function filterSearch(){renderMenu();}
function updateCartBar(){var keys=Object.keys(cart);var count=0,total=0;for(var i=0;i<keys.length;i++){count+=cart[keys[i]].qty;total+=cart[keys[i]].qty*cart[keys[i]].price;}document.getElementById('cartCount').textContent=count;document.getElementById('cartTotal').textContent=CURRENCY+total.toFixed(0);document.getElementById('cartBar').classList.toggle('visible',count>0);}
function openSheet(){var keys=Object.keys(cart);var total=0;var html='';for(var i=0;i<keys.length;i++){var name=keys[i],v=cart[name];total+=v.qty*v.price;html+='<div class="cart-item"><div style="flex:1"><div class="cart-item-name">'+escHtml(name)+'</div><div class="cart-item-price">'+CURRENCY+v.price.toFixed(0)+' x '+v.qty+'</div></div><div><div class="cart-item-total">'+CURRENCY+(v.price*v.qty).toFixed(0)+'</div><div class="qty-ctrl qty-has" style="margin-top:6px"><button ontouchstart="" data-name="'+escAttr(name)+'" data-price="'+v.price+'" data-cat="'+escAttr(v.category)+'" data-delta="-1" onclick="handleQty(this)">&minus;</button><span>'+v.qty+'</span><button ontouchstart="" data-name="'+escAttr(name)+'" data-price="'+v.price+'" data-cat="'+escAttr(v.category)+'" data-delta="1" onclick="handleQty(this)">+</button></div></div></div>';}document.getElementById('sheetItems').innerHTML=html;document.getElementById('sheetTotal').textContent=CURRENCY+total.toFixed(0);document.getElementById('sheetOverlay').classList.add('open');document.getElementById('cartSheet').classList.add('open');}
function closeSheet(){document.getElementById('sheetOverlay').classList.remove('open');document.getElementById('cartSheet').classList.remove('open');updateCartBar();}
function placeOrder(){var table=document.getElementById('tableInput').value.trim().toUpperCase();var waiter=document.getElementById('waiterInput').value.trim();var note=document.getElementById('noteInput').value.trim();if(!table){showToast('Enter a table number first',true);closeSheet();return;}var keys=Object.keys(cart);if(!keys.length){showToast('Cart is empty',true);return;}var orderItems=[];var total=0;for(var i=0;i<keys.length;i++){var n=keys[i],v=cart[n];orderItems.push({name:n,qty:v.qty,price:v.price,category:v.category});total+=v.qty*v.price;}var payload={table:table,waiter:waiter,note:note,items:orderItems,total:total};document.getElementById('placeBtn').disabled=true;document.getElementById('placeBtn').textContent='Sending...';fetch('/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(function(r){return r.json();}).then(function(d){if(d.ok){cart={};closeSheet();renderMenu();updateCartBar();showToast('Order sent to kitchen!');}else{showToast(d.error||'Failed to send',true);}}).catch(function(){showToast('Network error - try again',true);}).finally(function(){document.getElementById('placeBtn').disabled=false;document.getElementById('placeBtn').textContent='Place Order';});}
function showToast(msg,isError){var t=document.getElementById('toast');t.textContent=msg;t.className='toast'+(isError?' error':'');t.classList.add('show');setTimeout(function(){t.classList.remove('show');},3000);}
_initMenu();buildCatTabs();renderMenu();
</script>
</body>
</html>"""

_HTML_SUCCESS = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Order Sent</title>
<style>
  body{background:#0d0d0d;color:#f0f0f0;font-family:sans-serif;
  display:flex;align-items:center;justify-content:center;
  min-height:100vh;text-align:center;padding:20px;}
  h2{color:#4CAF50;font-size:28px;margin-bottom:12px;}
  p{color:#888;font-size:15px;}
</style></head>
<body><div>
<div style="font-size:60px">&#9989;</div>
<h2>Order Received!</h2>
<p>The cashier has been notified.</p>
</div></body></html>"""


# ── HTTP request handler ─────────────────────────────────────
class _OrderHandler(BaseHTTPRequestHandler):
    on_order   = None
    db_path    = None
    vercel_url = None

    def log_message(self, fmt, *args):
        pass

    def _fetch_menu_from_db(self):
        import sqlite3, traceback
        db = self.db_path or ""
        if not db or not os.path.exists(db):
            candidates = []
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                candidates += [
                    os.path.join(base, ".RestoBillData", "restaurant_data.db"),
                    os.path.join(os.getcwd(), ".RestoBillData", "restaurant_data.db"),
                ]
            except Exception:
                pass
            for c in candidates:
                if os.path.exists(c):
                    db = c
                    break
        try:
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT name, price, category FROM menu_items "
                "WHERE available=1 ORDER BY category, name"
            ).fetchall()
            currency_row = conn.execute(
                "SELECT value FROM settings WHERE key='currency'"
            ).fetchone()
            currency = currency_row[0] if currency_row else "Rs."
            conn.close()
            return [{"name": r["name"], "price": r["price"], "category": r["category"]} for r in rows], currency
        except Exception:
            return [], "Rs."

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/debug":
            menu_list, currency = self._fetch_menu_from_db()
            lines = [
                f"db_path   : {self.db_path}",
                f"db_exists : {os.path.exists(self.db_path or '')}",
                f"currency  : {currency}",
                f"item_count: {len(menu_list)}", "",
            ] + [f"  {i['name']} | {i['category']} | {i['price']}" for i in menu_list[:20]]
            self._send(200, "text/plain; charset=utf-8", "\n".join(lines).encode("utf-8"))
        elif path == "/menu":
            menu_list, currency = self._fetch_menu_from_db()
            payload = json.dumps({"items": menu_list, "currency": currency}, ensure_ascii=True)
            self._send(200, "application/json; charset=utf-8", payload.encode("utf-8"))
        elif path in ("/", "/order"):
            if self.vercel_url:
                self.send_response(302)
                self.send_header("Location", self.vercel_url)
                self.end_headers()
                return
            menu_list, currency = self._fetch_menu_from_db()
            menu_json_safe = _safe_json_for_html({"items": menu_list, "currency": currency})
            html = _HTML_ORDER_FORM.replace("__MENU_DATA__", menu_json_safe)
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
        elif path == "/test":
            menu_list, currency = self._fetch_menu_from_db()
            menu_json_safe = _safe_json_for_html({"items": menu_list, "currency": currency})
            test_html = (
                "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>RestoBill Test</title></head>"
                "<body style='background:#111;color:#eee;font-family:monospace;padding:20px'>"
                "<h2 style='color:#FF6B35'>RestoBill JS Test</h2>"
                "<script>var _MENU_DATA_ = " + menu_json_safe + ";</scr" + "ipt>"
                "<script>"
                "document.write('<p>JS OK</p>');"
                "document.write('<p>Items: '+(_MENU_DATA_.items?_MENU_DATA_.items.length:'ERR')+'</p>');"
                "document.write('<p>Currency: '+(_MENU_DATA_.currency||'ERR')+'</p>');"
                "if(_MENU_DATA_.items){_MENU_DATA_.items.forEach(function(i){"
                "document.write('<p style=\"color:#4CAF50\">'+i.name+' - '+i.price+'</p>');});}"
                "</scr" + "ipt>"
                "<p><a href='/' style='color:#FF6B35'>Go to order page</a></p>"
                "</body></html>"
            )
            self._send(200, "text/html; charset=utf-8", test_html.encode("utf-8"))
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/order":
            self._send(404, "text/plain", b"Not found"); return
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        try:
            order = json.loads(body)
            if self.on_order:
                self.on_order(order)
            self._send(200, "application/json", json.dumps({"ok": True}).encode())
        except Exception as e:
            self._send(400, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

    def _send(self, code, ctype, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ── MobileOrderServer ────────────────────────────────────────
class MobileOrderServer:
    def __init__(self, db, on_order_callback, port: int = 5000):
        self._db       = db
        self._callback = on_order_callback
        self._port     = port
        self._server   = None
        self._thread   = None
        self._queue    = []
        self._lock     = threading.Lock()
        self._ip       = _get_lan_ip()
        self._qr_pil   = None
        self._qr_url   = None
        self.url       = f"http://{self._ip}:{port}"
        self._db_path  = self._resolve_db_path(db)
        print(f"[MobileServer] DB path resolved: {self._db_path!r}  exists={os.path.exists(self._db_path)}")

    def _resolve_db_path(self, db) -> str:
        candidates = []
        try:
            row = db.conn.execute("PRAGMA database_list").fetchone()
            p = row[2] if row and row[2] else ""
            if p and p != ":memory:":
                candidates.append(os.path.abspath(p))
        except Exception:
            pass
        for attr in ("connection", "_conn", "_connection", "db", "_db"):
            try:
                conn_obj = getattr(db, attr, None)
                if conn_obj is not None:
                    row = conn_obj.execute("PRAGMA database_list").fetchone()
                    p = row[2] if row and row[2] else ""
                    if p and p != ":memory:":
                        candidates.append(os.path.abspath(p)); break
            except Exception:
                pass
        try:
            base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
            candidates.append(os.path.join(base, ".RestoBillData", "restaurant_data.db"))
        except Exception:
            pass
        candidates.append(os.path.join(os.getcwd(), ".RestoBillData", "restaurant_data.db"))
        try:
            d = os.getcwd()
            for _ in range(4):
                candidates.append(os.path.join(d, ".RestoBillData", "restaurant_data.db"))
                d = os.path.dirname(d)
        except Exception:
            pass
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return candidates[1] if len(candidates) > 1 else candidates[0]

    def _generate_qr(self, url: str):
        if not QR_AVAILABLE:
            return
        try:
            qr = qrcode.QRCode(version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6, border=2)
            qr.add_data(url); qr.make(fit=True)
            self._qr_pil = qr.make_image(
                fill_color="#FF6B35", back_color="#0d0d0d"
            ).resize((220, 220), Image.LANCZOS)
            self._qr_url = url
            print(f"[MobileServer] QR generated for: {url}")
        except Exception as e:
            print(f"[MobileServer] QR generation failed: {e}")
            self._qr_pil = None

    def _make_handler_class(self):
        queue   = self._queue
        lock    = self._lock
        db_path = self._db_path

        def _on_post(order):
            with lock:
                queue.append(order)

        class Handler(_OrderHandler):
            pass

        Handler.db_path    = db_path
        Handler.on_order   = staticmethod(_on_post)
        Handler.vercel_url = self._db.get_setting("mobile_url_override", "").strip()
        self._handler_class = Handler
        return Handler

    def start(self):
        try:
            handler = self._make_handler_class()
            self._server = HTTPServer(("0.0.0.0", self._port), handler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            print(f"[MobileServer] HTTP server listening on port {self._port}")
        except OSError as e:
            print(f"[MobileServer] Could not start HTTP server: {e}"); return
        try:
            manual = self._db.get_setting("mobile_url_override", "").strip()
        except Exception:
            manual = ""
        self._qr_url = manual if manual else f"http://{self._ip}:{self._port}"
        self._generate_qr(self._qr_url)

    def stop(self):
        if self._server:
            self._server.shutdown()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def poll_orders(self, root, interval_ms: int = 1000):
        def _check():
            with self._lock:
                pending = list(self._queue)
                self._queue.clear()
            for order in pending:
                try:
                    self._callback(order)
                except Exception as e:
                    print(f"[MobileServer] callback error: {e}")
            root.after(interval_ms, _check)
        root.after(interval_ms, _check)

    # ── QR code window ────────────────────────────────────
    def show_qr_window(self, parent):
        """
        Open a Tk window showing the cached QR code and server status.

        Changes:
          - Title bar removed (overrideredirect + no OS chrome)
          - Print button placed next to Close button at the bottom
        """
        import tempfile, webbrowser

        C = {
            "bg":     "#0d0d0d",
            "card":   "#1a1a1a",
            "accent": "#FF6B35",
            "green":  "#4CAF50",
            "muted":  "#444",
            "text":   "#f0f0f0",
            "border": "#333",
        }

        win = tk.Toplevel(parent)
        win.overrideredirect(True)          # ← no OS title bar
        win.configure(bg=C["accent"])       # accent = 3-px border colour
        win.resizable(False, False)

        W, H = 400, 500
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        # Outer accent border frame
        border_frame = tk.Frame(win, bg=C["accent"], padx=3, pady=3)
        border_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Inner dark content area
        inner = tk.Frame(border_frame, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        # ── Top bar (replaces OS title bar): title + close ─
        top_bar = tk.Frame(inner, bg=C["accent"], pady=10)
        top_bar.pack(fill="x")
        tk.Label(top_bar, text="📱  Mobile Order Terminal",
                 font=("Georgia", 13, "bold"),
                 bg=C["accent"], fg="black").pack(side="left", padx=14)
        tk.Button(top_bar, text="✕", command=win.destroy,
                  bg=C["accent"], fg="black",
                  font=("Arial", 11, "bold"), bd=0, padx=10,
                  cursor="hand2", relief="flat").pack(side="right", padx=6)

        body = tk.Frame(inner, bg=C["bg"], pady=10)
        body.pack(fill="both", expand=True)

        if not self.is_running():
            tk.Label(body,
                     text="Server not running.\nCheck if port 5000 is available.",
                     font=("Arial", 12), bg=C["bg"], fg="#e53935",
                     justify="center").pack(expand=True)
            return

        local_url = self._qr_url or f"http://{self._ip}:{self._port}"

        tk.Label(body, text="Scan to Order  —  Fixed QR (never changes)",
                 font=("Arial", 9, "bold"),
                 bg=C["bg"], fg=C["muted"]).pack(pady=(4, 2))

        # URL row (no buttons inside, just the URL label)
        url_row = tk.Frame(body, bg=C["card"],
                           highlightbackground=C["border"], highlightthickness=1)
        url_row.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(url_row, text=local_url,
                 font=("Courier New", 10),
                 bg=C["card"], fg=C["accent"]).pack(
            side="left", fill="x", expand=True, padx=10, pady=8)

        # ── QR image ──────────────────────────────────────
        qr_frame = tk.Frame(body, bg=C["bg"])
        qr_frame.pack(pady=8)

        if QR_AVAILABLE and self._qr_pil is not None:
            photo = ImageTk.PhotoImage(self._qr_pil)
            qr_lbl = tk.Label(qr_frame, image=photo, bg=C["bg"])
            qr_lbl.image = photo
            qr_lbl.pack()
        else:
            tk.Label(qr_frame,
                     text="QR unavailable\nInstall: pip install qrcode[pil] pillow",
                     font=("Courier New", 10),
                     bg=C["bg"], fg=C["muted"],
                     justify="center").pack(padx=20, pady=20)

        tk.Label(body,
                 text="Menu updates reflect live — no need to reprint QR",
                 font=("Arial", 8),
                 bg=C["bg"], fg=C["muted"]).pack()

        # ── Print helper ───────────────────────────────────
        def print_qr():
            import base64, io as _io
            qr_img_tag = ""
            if QR_AVAILABLE and self._qr_pil is not None:
                try:
                    buf = _io.BytesIO()
                    self._qr_pil.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    qr_img_tag = (
                        f"<img src='data:image/png;base64,{b64}' "
                        f"style='width:220px;height:220px;margin:12px auto;display:block;' "
                        f"alt='QR Code'>"
                    )
                except Exception:
                    qr_img_tag = ""
            html = f"""<!DOCTYPE html>
<html><head><meta charset='UTF-8'><title>Mobile Order QR</title>
<style>
  body{{font-family:sans-serif;text-align:center;padding:30px;background:#fff;color:#111;}}
  h2{{font-size:20px;margin-bottom:6px;}}
  p{{font-size:13px;color:#555;margin-bottom:16px;}}
  .url{{font-family:monospace;font-size:14px;background:#f5f5f5;
        padding:8px 16px;border-radius:6px;display:inline-block;margin-bottom:20px;}}
  @media print{{body{{padding:10px;}}}}
</style></head>
<body>
<h2>&#127374; RestoBill — Mobile Order</h2>
<p>Waiters: scan or visit the URL below to place orders</p>
{qr_img_tag}
<div class='url'>{local_url}</div>
<p style='font-size:11px;color:#aaa;margin-top:24px'>Menu updates live — no need to reprint this page</p>
<script>window.onload=function(){{window.print();}}</script>
</body></html>"""
            tf = tempfile.NamedTemporaryFile(
                delete=False, suffix=".html", mode="w", encoding="utf-8")
            tf.write(html); tf.close()
            webbrowser.open(f"file://{tf.name}")

        # ── Bottom button row: Print  +  Close ────────────
        btn_row = tk.Frame(inner, bg=C["bg"])
        btn_row.pack(fill="x", padx=30, pady=10)

        tk.Button(btn_row, text="🖨 Print", command=print_qr,
                  bg="#2a2a2a", fg=C["text"],
                  font=("Arial", 11, "bold"), bd=0, pady=8,
                  cursor="hand2").pack(side="left", expand=True, fill="x", padx=(0, 6))

        tk.Button(btn_row, text="Close", command=win.destroy,
                  bg="#2a2a2a", fg="#ccc",
                  font=("Arial", 11, "bold"), bd=0, pady=8,
                  cursor="hand2").pack(side="left", expand=True, fill="x")

        win.bind("<Escape>", lambda e: win.destroy())


# ── Popup shown in main app when an order arrives ─────────────
def show_mobile_order_popup(parent, order: dict, on_accept, on_reject):
    """
    Shows a confirmation dialog in the main app when a waiter
    submits a mobile order.  Calls on_accept(order) or on_reject().
    """
    win = tk.Toplevel(parent)
    win.overrideredirect(True)
    win.configure(bg="#FFA500")
    W, H = 420, 540
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
    win.grab_set()
    win.lift()
    win.focus_force()

    border = tk.Frame(win, bg="#FFA500", padx=3, pady=3)
    border.place(relx=0, rely=0, relwidth=1, relheight=1)
    inner = tk.Frame(border, bg="#1e1e1e")
    inner.pack(fill="both", expand=True)

    hdr = tk.Frame(inner, bg="#FFA500", pady=12)
    hdr.pack(fill="x")
    tk.Label(hdr, text="📱  New Mobile Order",
             font=("Georgia", 14, "bold"),
             bg="#FFA500", fg="black").pack()

    waiter = order.get("waiter", "").strip()
    header_sub = f"Table  {order.get('table','?')}"
    if waiter:
        header_sub += f"   |   Waiter: {waiter}"
    tk.Label(hdr, text=header_sub,
             font=("Arial", 10),
             bg="#FFA500", fg="#330000").pack()

    list_frame = tk.Frame(inner, bg="#1e1e1e", padx=20, pady=12)
    list_frame.pack(fill="both", expand=True)

    tk.Label(list_frame, text="Items",
             font=("Arial", 9, "bold"),
             bg="#1e1e1e", fg="#666").pack(anchor="w", pady=(0, 6))

    curr = "Rs."
    for item in order.get("items", []):
        row = tk.Frame(list_frame, bg="#2a2a2a",
                       highlightbackground="#3a3a3a", highlightthickness=1)
        row.pack(fill="x", pady=2, ipady=4)
        tk.Label(row, text=f"  {item['qty']}×  {item['name']}",
                 font=("Courier New", 11),
                 bg="#2a2a2a", fg="#f0f0f0", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(row, text=f"  {curr}{item['qty']*item['price']:.0f}  ",
                 font=("Courier New", 11),
                 bg="#2a2a2a", fg="#FFA500").pack(side="right")

    note = order.get("note", "").strip()
    if note:
        note_frame = tk.Frame(list_frame, bg="#2a1a00", padx=10, pady=6)
        note_frame.pack(fill="x", pady=(8, 0))
        tk.Label(note_frame, text=f"📝  {note}",
                 font=("Arial", 10), bg="#2a1a00", fg="#FFA500",
                 wraplength=340, justify="left").pack(anchor="w")

    total_row = tk.Frame(inner, bg="#FFA500", padx=20, pady=8)
    total_row.pack(fill="x")
    tk.Label(total_row,
             text=f"Total:  Rs. {order.get('total', 0):.2f}",
             font=("Arial", 13, "bold"),
             bg="#FFA500", fg="black").pack(anchor="e")

    btn_row = tk.Frame(inner, bg="#1e1e1e", padx=20, pady=14)
    btn_row.pack(fill="x")

    def accept():
        win.destroy(); on_accept(order)

    def reject():
        win.destroy(); on_reject()

    tk.Button(btn_row, text="✔  Accept", command=accept,
              bg="#4CAF50", fg="white", font=("Arial", 13, "bold"),
              bd=0, pady=12, cursor="hand2").pack(
        side="left", expand=True, fill="x", padx=(0, 8))

    tk.Button(btn_row, text="✕  Reject", command=reject,
              bg="#e53935", fg="white", font=("Arial", 13, "bold"),
              bd=0, pady=12, cursor="hand2").pack(
        side="left", expand=True, fill="x")
