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
    """
    Serialize data to JSON safe for embedding inside a <script> tag.
    - Uses ensure_ascii=True to avoid raw Unicode issues on mobile browsers.
    - Escapes </script> and <!-- sequences that would break the script block.
    - Escapes U+2028 / U+2029 which are line terminators in JS but not JSON.
    """
    raw = json.dumps(data, ensure_ascii=True)
    raw = raw.replace("</", "<\\/")          # prevent </script> breaking the block
    raw = raw.replace("<!--", "<\\!--")      # prevent HTML comment injection
    raw = raw.replace("\u2028", "\\u2028")   # JS line separator
    raw = raw.replace("\u2029", "\\u2029")   # JS paragraph separator
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
    --bg: #0d0d0d;
    --surface: #161616;
    --card: #1e1e1e;
    --border: #2a2a2a;
    --accent: #FF6B35;
    --accent2: #FFA500;
    --text: #f0f0f0;
    --muted: #666;
    --green: #4CAF50;
    --red: #e53935;
    --radius: 14px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    padding-bottom: 80px;
  }
  header {
    background: linear-gradient(135deg, #1a0800 0%, #0d0d0d 100%);
    padding: 20px 20px 16px;
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 100;
    backdrop-filter: blur(10px);
    position: relative;
  }
  header h1 {
    font-family: 'Playfair Display', serif;
    font-size: 22px;
    color: var(--accent);
    letter-spacing: 0.5px;
  }
  header p { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .refresh-btn {
    position: absolute; right: 16px; top: 16px;
    background: none;
    border: 1px solid var(--accent);
    color: var(--accent);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    cursor: pointer;
    font-family: 'DM Sans', sans-serif;
  }
  .container { max-width: 480px; margin: 0 auto; padding: 16px; }
 
  .table-bar {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    margin-bottom: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .table-bar label {
    font-size: 11px; font-weight: 600;
    color: var(--muted); text-transform: uppercase;
    letter-spacing: 1px; display: block; margin-bottom: 4px;
  }
  .table-bar input {
    width: 100%;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 16px;
    padding: 12px 14px;
    outline: none;
  }
  .table-bar input:focus { border-color: var(--accent); }
 
  .cat-tabs {
    display: flex; gap: 8px; overflow-x: auto;
    padding-bottom: 4px; margin-bottom: 14px;
    scrollbar-width: none;
  }
  .cat-tabs::-webkit-scrollbar { display: none; }
  .cat-tab {
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    color: var(--muted);
    font-family: 'DM Sans', sans-serif;
    font-size: 13px; font-weight: 500;
    padding: 7px 16px; cursor: pointer;
    transition: all 0.2s;
  }
  .cat-tab.active {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }
 
  .search-wrap {
    position: relative; margin-bottom: 14px;
  }
  .search-wrap input {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 15px;
    padding: 11px 14px 11px 38px;
    outline: none;
  }
  .search-wrap input:focus { border-color: var(--accent); }
  .search-wrap .icon {
    position: absolute; left: 12px; top: 50%;
    transform: translateY(-50%);
    color: var(--muted); font-size: 16px;
  }
 
  .menu-grid {
    display: flex; flex-direction: column; gap: 8px;
  }
  .menu-item {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 13px 14px;
    display: flex; align-items: center; gap: 12px;
    transition: border-color 0.2s, transform 0.15s;
    cursor: pointer;
  }
  .menu-item:active { transform: scale(0.98); }
  .menu-item.in-cart { border-color: var(--accent); }
  .item-info { flex: 1; min-width: 0; }
  .item-name {
    font-size: 15px; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .item-cat {
    font-size: 11px; color: var(--muted); margin-top: 2px;
  }
  .item-price {
    font-size: 15px; font-weight: 700; color: var(--accent2);
    white-space: nowrap;
  }
  .qty-ctrl {
    display: flex; align-items: center; gap: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden;
    flex-shrink: 0;
  }
  .qty-ctrl button {
    background: none; border: none;
    color: var(--accent); font-size: 20px;
    width: 36px; height: 36px;
    cursor: pointer; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.15s;
    -webkit-tap-highlight-color: transparent;
  }
  .qty-ctrl button:active { background: #2a2a2a; }
  .qty-ctrl span {
    min-width: 30px; text-align: center;
    font-size: 15px; font-weight: 600;
  }
  .qty-zero { display: none; }
  .qty-has { display: flex; }
 
  .cart-bar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: var(--accent);
    padding: 0;
    transform: translateY(100%);
    transition: transform 0.3s cubic-bezier(.22,.61,.36,1);
    z-index: 200;
    max-width: 480px;
    margin: 0 auto;
  }
  .cart-bar.visible { transform: translateY(0); }
  .cart-bar-inner {
    display: flex; align-items: center;
    padding: 14px 20px; gap: 12px; cursor: pointer;
  }
  .cart-count {
    background: rgba(0,0,0,0.25);
    border-radius: 20px;
    padding: 4px 10px;
    font-size: 13px; font-weight: 700; color: #fff;
  }
  .cart-label {
    flex: 1; font-size: 15px; font-weight: 700; color: #fff;
  }
  .cart-total {
    font-size: 16px; font-weight: 800; color: #fff;
  }
 
  .sheet-overlay {
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,0.7); z-index: 300;
  }
  .sheet-overlay.open { display: block; }
  .sheet {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: var(--surface);
    border-radius: 20px 20px 0 0;
    max-height: 80vh; overflow-y: auto;
    z-index: 400;
    transform: translateY(100%);
    transition: transform 0.35s cubic-bezier(.22,.61,.36,1);
    max-width: 480px; margin: 0 auto;
  }
  .sheet.open { transform: translateY(0); }
  .sheet-handle {
    width: 40px; height: 4px;
    background: var(--border);
    border-radius: 2px;
    margin: 12px auto 0;
  }
  .sheet-title {
    font-family: 'Playfair Display', serif;
    font-size: 20px; color: var(--accent);
    padding: 16px 20px 8px;
    border-bottom: 1px solid var(--border);
  }
  .cart-item {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
  }
  .cart-item-name { flex: 1; font-size: 14px; font-weight: 500; }
  .cart-item-price { font-size: 13px; color: var(--muted); margin-top: 2px; }
  .cart-item-total { font-size: 14px; font-weight: 700; color: var(--accent2); }
  .sheet-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--border);
  }
  .sheet-subtotal {
    display: flex; justify-content: space-between;
    font-size: 15px; font-weight: 600; margin-bottom: 14px;
  }
  .sheet-subtotal span:last-child { color: var(--accent2); }
  .btn-place {
    width: 100%;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 12px;
    font-family: 'DM Sans', sans-serif;
    font-size: 16px; font-weight: 700;
    padding: 15px;
    cursor: pointer;
    letter-spacing: 0.3px;
    transition: opacity 0.2s;
  }
  .btn-place:active { opacity: 0.85; }
  .btn-place:disabled { opacity: 0.5; cursor: not-allowed; }
 
  .note-field {
    width: 100%;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    padding: 10px 12px;
    outline: none;
    margin-bottom: 12px;
    resize: none;
  }
  .note-field:focus { border-color: var(--accent); }
 
  .toast {
    position: fixed; top: 80px; left: 50%; transform: translateX(-50%) translateY(-20px);
    background: var(--green); color: #fff;
    border-radius: 10px; padding: 10px 20px;
    font-size: 14px; font-weight: 600;
    opacity: 0; transition: all 0.3s; z-index: 999;
    white-space: nowrap;
  }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  .toast.error { background: var(--red); }
 
  .empty-state {
    text-align: center; padding: 48px 20px;
    color: var(--muted);
  }
  .empty-state .icon { font-size: 40px; margin-bottom: 10px; }
  .empty-state p { font-size: 14px; }
</style>
</head>
<body>
 
<header>
  <h1>&#127374; RestoBill</h1>
  <p>Waiter Order Terminal</p>
  <button class="refresh-btn" onclick="loadMenu()">&#8635; Refresh Menu</button>
</header>
 
<div class="container">
 
  <div class="table-bar">
    <div>
      <label>Table Number</label>
      <input type="text" id="tableInput" placeholder="e.g. T01, T05 ..."
             inputmode="text" autocomplete="off"
             style="text-transform:uppercase">
    </div>
    <div>
      <label>Waiter Name</label>
      <input type="text" id="waiterInput" placeholder="Your name (optional)"
             autocomplete="off">
    </div>
  </div>
 
  <div class="cat-tabs" id="catTabs">
    <button class="cat-tab active" data-cat="All">All</button>
  </div>
 
  <div class="search-wrap">
    <span class="icon">&#128269;</span>
    <input type="text" id="searchInput" placeholder="Search menu..."
           oninput="filterSearch()" autocomplete="off">
  </div>
 
  <div class="menu-grid" id="menuGrid">
    <div class="empty-state"><div class="icon">&#9203;</div><p>Loading menu...</p></div>
  </div>
 
</div>
 
<!-- Cart bar -->
<div class="cart-bar" id="cartBar" onclick="openSheet()">
  <div class="cart-bar-inner">
    <span class="cart-count" id="cartCount">0</span>
    <span class="cart-label">View Order</span>
    <span class="cart-total" id="cartTotal">Rs. 0</span>
  </div>
</div>
 
<!-- Sheet overlay -->
<div class="sheet-overlay" id="sheetOverlay" onclick="closeSheet()"></div>
 
<!-- Cart sheet -->
<div class="sheet" id="cartSheet">
  <div class="sheet-handle"></div>
  <div class="sheet-title">Your Order</div>
  <div id="sheetItems"></div>
  <div class="sheet-footer">
    <div class="sheet-subtotal">
      <span>Total</span>
      <span id="sheetTotal">Rs. 0</span>
    </div>
    <textarea class="note-field" id="noteInput"
              placeholder="Add a note (optional)..." rows="2"></textarea>
    <button class="btn-place" id="placeBtn" onclick="placeOrder()">
      Place Order
    </button>
  </div>
</div>
 
<!-- Toast -->
<div class="toast" id="toast"></div>
 
<!-- Menu data embedded directly as JS variable — reliable on all mobile browsers -->
<script>var _MENU_DATA_ = __MENU_DATA__;</script>
 
<script>
// ── Globals ───────────────────────────────────────────────
var MENU     = [];
var CURRENCY = 'Rs.';
var cart     = {};
var activeCat = 'All';
 
// ── Safe escaping helpers ─────────────────────────────────
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function escAttr(s) {
  return String(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
 
// ── Bootstrap menu from embedded JS variable ─────────────
function _initMenu() {
  try {
    var raw  = (typeof _MENU_DATA_ !== 'undefined') ? _MENU_DATA_ : {};
    MENU     = Array.isArray(raw.items) ? raw.items : [];
    CURRENCY = raw.currency || 'Rs.';
  } catch(e) {
    console.error('RestoBill: menu init error', e);
    MENU = [];
  }
}
 
// ── Refresh menu from server ──────────────────────────────
function loadMenu() {
  fetch('/menu')
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      MENU     = Array.isArray(data.items) ? data.items : [];
      CURRENCY = data.currency || 'Rs.';
      buildCatTabs();
      renderMenu();
      showToast('Menu refreshed');
    })
    .catch(function(err) {
      showToast('Could not refresh menu', true);
      console.error('Menu refresh error:', err);
    });
}
 
function buildCatTabs() {
  var cats = [];
  for (var i = 0; i < MENU.length; i++) {
    var c = MENU[i].category;
    if (c && cats.indexOf(c) === -1) cats.push(c);
  }
  cats.sort();
  var html = '<button class="cat-tab active" data-cat="All">All</button>';
  for (var j = 0; j < cats.length; j++) {
    html += '<button class="cat-tab" data-cat="' + escAttr(cats[j]) + '">'
          + escHtml(cats[j]) + '</button>';
  }
  var container = document.getElementById('catTabs');
  container.innerHTML = html;
  container.onclick = function(e) {
    var btn = e.target.closest('.cat-tab');
    if (btn && btn.dataset.cat) filterCat(btn.dataset.cat);
  };
}
 
// ── Render menu ───────────────────────────────────────────
function renderMenu() {
  var q    = document.getElementById('searchInput').value.trim().toLowerCase();
  var grid = document.getElementById('menuGrid');
  var items = [];
  for (var i = 0; i < MENU.length; i++) {
    var m = MENU[i];
    var catOk = (activeCat === 'All') || (m.category === activeCat);
    var qOk   = !q || m.name.toLowerCase().indexOf(q) !== -1;
    if (catOk && qOk) items.push(m);
  }
 
  if (!items.length) {
    grid.innerHTML = '<div class="empty-state"><div class="icon">&#127374;</div><p>No items found</p></div>';
    return;
  }
 
  var html = '';
  for (var k = 0; k < items.length; k++) {
    var m      = items[k];
    var qty    = cart[m.name] ? cart[m.name].qty : 0;
    var inCart = qty > 0 ? 'in-cart' : '';
    var price  = parseFloat(m.price);
    var cat    = m.category || '';
 
    html += '<div class="menu-item ' + inCart + '">'
          + '<div class="item-info">'
          + '<div class="item-name">'  + escHtml(m.name) + '</div>'
          + '<div class="item-cat">'   + escHtml(cat)    + '</div>'
          + '</div>'
          + '<div class="item-price">' + CURRENCY + price.toFixed(0) + '</div>';
 
    if (qty > 0) {
      html += '<div class="qty-ctrl qty-has">'
            + '<button ontouchstart="" data-name="' + escAttr(m.name) + '" data-price="' + price + '" data-cat="' + escAttr(cat) + '" data-delta="-1" onclick="handleQty(this)">&minus;</button>'
            + '<span>' + qty + '</span>'
            + '<button ontouchstart="" data-name="' + escAttr(m.name) + '" data-price="' + price + '" data-cat="' + escAttr(cat) + '" data-delta="1"  onclick="handleQty(this)">+</button>'
            + '</div>';
    } else {
      html += '<button style="display:flex;width:36px;height:36px;border-radius:8px;'
            + 'background:var(--accent);border:none;color:#fff;font-size:22px;'
            + 'cursor:pointer;align-items:center;justify-content:center;flex-shrink:0;"'
            + ' ontouchstart=""'
            + ' data-name="'  + escAttr(m.name) + '"'
            + ' data-price="' + price           + '"'
            + ' data-cat="'   + escAttr(cat)    + '"'
            + ' data-delta="1" onclick="handleQty(this)">+</button>';
    }
    html += '</div>';
  }
  grid.innerHTML = html;
}
 
function handleQty(btn) {
  var name  = btn.getAttribute('data-name');
  var price = parseFloat(btn.getAttribute('data-price'));
  var cat   = btn.getAttribute('data-cat');
  var delta = parseInt(btn.getAttribute('data-delta'), 10);
  if (!cart[name]) cart[name] = { qty: 0, price: price, category: cat };
  cart[name].qty = Math.max(0, cart[name].qty + delta);
  if (cart[name].qty === 0) delete cart[name];
  renderMenu();
  updateCartBar();
}
 
function filterCat(cat) {
  activeCat = cat;
  var tabs = document.querySelectorAll('.cat-tab');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].classList.toggle('active', tabs[i].textContent.trim() === cat);
  }
  renderMenu();
}
 
function filterSearch() { renderMenu(); }
 
// ── Cart bar ──────────────────────────────────────────────
function updateCartBar() {
  var keys  = Object.keys(cart);
  var count = 0, total = 0;
  for (var i = 0; i < keys.length; i++) {
    count += cart[keys[i]].qty;
    total += cart[keys[i]].qty * cart[keys[i]].price;
  }
  document.getElementById('cartCount').textContent = count;
  document.getElementById('cartTotal').textContent = CURRENCY + total.toFixed(0);
  document.getElementById('cartBar').classList.toggle('visible', count > 0);
}
 
// ── Sheet ─────────────────────────────────────────────────
function openSheet() {
  var keys  = Object.keys(cart);
  var total = 0;
  var html  = '';
  for (var i = 0; i < keys.length; i++) {
    var name = keys[i], v = cart[name];
    total += v.qty * v.price;
    html += '<div class="cart-item">'
          + '<div style="flex:1">'
          + '<div class="cart-item-name">'  + escHtml(name) + '</div>'
          + '<div class="cart-item-price">' + CURRENCY + v.price.toFixed(0) + ' x ' + v.qty + '</div>'
          + '</div>'
          + '<div>'
          + '<div class="cart-item-total">' + CURRENCY + (v.price * v.qty).toFixed(0) + '</div>'
          + '<div class="qty-ctrl qty-has" style="margin-top:6px">'
          + '<button ontouchstart="" data-name="' + escAttr(name) + '" data-price="' + v.price + '" data-cat="' + escAttr(v.category) + '" data-delta="-1" onclick="handleQty(this)">&minus;</button>'
          + '<span>' + v.qty + '</span>'
          + '<button ontouchstart="" data-name="' + escAttr(name) + '" data-price="' + v.price + '" data-cat="' + escAttr(v.category) + '" data-delta="1"  onclick="handleQty(this)">+</button>'
          + '</div></div></div>';
  }
  document.getElementById('sheetItems').innerHTML = html;
  document.getElementById('sheetTotal').textContent = CURRENCY + total.toFixed(0);
  document.getElementById('sheetOverlay').classList.add('open');
  document.getElementById('cartSheet').classList.add('open');
}
 
function closeSheet() {
  document.getElementById('sheetOverlay').classList.remove('open');
  document.getElementById('cartSheet').classList.remove('open');
  updateCartBar();
}
 
// ── Place order ───────────────────────────────────────────
function placeOrder() {
  var table  = document.getElementById('tableInput').value.trim().toUpperCase();
  var waiter = document.getElementById('waiterInput').value.trim();
  var note   = document.getElementById('noteInput').value.trim();
  if (!table) { showToast('Enter a table number first', true); closeSheet(); return; }
  var keys = Object.keys(cart);
  if (!keys.length) { showToast('Cart is empty', true); return; }
 
  var orderItems = [];
  var total = 0;
  for (var i = 0; i < keys.length; i++) {
    var n = keys[i], v = cart[n];
    orderItems.push({ name: n, qty: v.qty, price: v.price, category: v.category });
    total += v.qty * v.price;
  }
 
  var payload = { table: table, waiter: waiter, note: note, items: orderItems, total: total };
  document.getElementById('placeBtn').disabled = true;
  document.getElementById('placeBtn').textContent = 'Sending...';
 
  fetch('/order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) {
        cart = {};
        closeSheet();
        renderMenu();
        updateCartBar();
        showToast('Order sent to kitchen!');
      } else {
        showToast(d.error || 'Failed to send', true);
      }
    }).catch(function() {
      showToast('Network error - try again', true);
    }).finally(function() {
      document.getElementById('placeBtn').disabled = false;
      document.getElementById('placeBtn').textContent = 'Place Order';
    });
}
 
function showToast(msg, isError) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (isError ? ' error' : '');
  t.classList.add('show');
  setTimeout(function() { t.classList.remove('show'); }, 3000);
}
 
// ── Boot ──────────────────────────────────────────────────
_initMenu();
buildCatTabs();
renderMenu();
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
    """Minimal HTTP handler — serves form and accepts JSON orders."""
 
    on_order = None   # callable(order_dict)
    db_path  = None
 
    def log_message(self, fmt, *args):
        pass   # suppress access logs
 
    def _fetch_menu_from_db(self):
        """Read menu from DB. Returns (menu_list, currency)."""
        import sqlite3, os, traceback
        db = self.db_path or ""
        if not db or not os.path.exists(db):
            print(f"[MobileServer] DB not found: {db!r}")
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
                    print(f"[MobileServer] Found DB at: {db}")
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
            menu_list = [
                {"name": r["name"], "price": r["price"], "category": r["category"]}
                for r in rows
            ]
            print(f"[MobileServer] DB OK — {len(menu_list)} items from {db}")
            return menu_list, currency
        except Exception as e:
            print(f"[MobileServer] DB error ({db}): {e}")
            traceback.print_exc()
            return [], "Rs."
 
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/debug":
            menu_list, currency = self._fetch_menu_from_db()
            lines = [
                f"db_path   : {self.db_path}",
                f"db_exists : {__import__('os').path.exists(self.db_path or '')}",
                f"currency  : {currency}",
                f"item_count: {len(menu_list)}",
                "",
            ] + [f"  {i['name']} | {i['category']} | {i['price']}" for i in menu_list[:20]]
            body = "\n".join(lines).encode("utf-8")
            self._send(200, "text/plain; charset=utf-8", body)
        elif path == "/menu":
            menu_list, currency = self._fetch_menu_from_db()
            payload = json.dumps({"items": menu_list, "currency": currency},
                                 ensure_ascii=True)
            self._send(200, "application/json; charset=utf-8",
                       payload.encode("utf-8"))
        elif path in ("/", "/order"):
            # If a Vercel URL is set, redirect to it instead of serving local HTML
            if self.vercel_url:
                self.send_response(302)
                self.send_header("Location", self.vercel_url)
                self.end_headers()
                print(f"[MobileServer] Redirecting to Vercel: {self.vercel_url}")
                return

            menu_list, currency = self._fetch_menu_from_db()
            print(f"[MobileServer] Serving page — {len(menu_list)} items, db={self.db_path}")
            menu_json_safe = _safe_json_for_html(
                {"items": menu_list, "currency": currency}
            )
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
                "document.write('<p>Items: ' + (_MENU_DATA_.items ? _MENU_DATA_.items.length : 'ERR') + '</p>');"
                "document.write('<p>Currency: ' + (_MENU_DATA_.currency || 'ERR') + '</p>');"
                "if(_MENU_DATA_.items){ _MENU_DATA_.items.forEach(function(i){"
                "  document.write('<p style=\"color:#4CAF50\">' + i.name + ' - ' + i.price + '</p>');"
                "}); }"
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
            resp = json.dumps({"ok": True}).encode()
            self._send(200, "application/json", resp)
        except Exception as e:
            resp = json.dumps({"ok": False, "error": str(e)}).encode()
            self._send(400, "application/json", resp)
 
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
        """Handle CORS pre-flight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
 
 
 
# ── MobileOrderServer ────────────────────────────────────────
class MobileOrderServer:
    """
    Lightweight LAN HTTP server that serves a mobile order form.
 
    QR code is generated ONCE at start() from the fixed LAN IP (or
    mobile_url_override setting).  show_qr_window() always displays
    the cached image — no regeneration on each open.
 
    Menu data is fetched live from SQLite every time a waiter loads
    the page, so menu changes appear immediately without touching the QR.
    """
 
    def __init__(self, db, on_order_callback, port: int = 5000):
        self._db        = db
        self._callback  = on_order_callback
        self._port      = port
        self._server    = None
        self._thread    = None
        self._queue     = []
        self._lock      = threading.Lock()
        self._ip        = _get_lan_ip()

        # QR cache — generated once in start()
        self._qr_pil    = None   # PIL Image object
        self._qr_url    = None   # URL encoded in the QR

        # Displayed URL
        self.url        = f"http://{self._ip}:{port}"

        self._db_path = self._resolve_db_path(db)
        print(f"[MobileServer] DB path resolved: {self._db_path!r}  exists={os.path.exists(self._db_path)}")
 
    def _resolve_db_path(self, db) -> str:
        import sys
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
                        candidates.append(os.path.abspath(p))
                        break
            except Exception:
                pass
 
        try:
            if getattr(sys, "frozen", False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            candidates.append(os.path.join(base, ".RestoBillData", "restaurant_data.db"))
        except Exception:
            pass
 
        candidates.append(os.path.join(os.getcwd(), ".RestoBillData", "restaurant_data.db"))
 
        try:
            d = os.getcwd()
            for _ in range(4):
                p = os.path.join(d, ".RestoBillData", "restaurant_data.db")
                candidates.append(p)
                d = os.path.dirname(d)
        except Exception:
            pass
 
        for p in candidates:
            if p and os.path.exists(p):
                print(f"[MobileServer] Using DB candidate: {p!r}")
                return p
 
        best = candidates[1] if len(candidates) > 1 else candidates[0]
        print(f"[MobileServer] No DB found; best guess: {best!r}")
        return best
 
    # ── QR generation (called once at start) ──────────────
    def _generate_qr(self, url: str):
        """
        Build and cache the QR PIL image from the given URL.
        Called exactly once during start().  Subsequent calls to
        show_qr_window() use self._qr_pil directly.
        """
        if not QR_AVAILABLE:
            print("[MobileServer] QR skipped — qrcode / pillow not installed.")
            return
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            self._qr_pil = qr.make_image(
                fill_color="#FF6B35", back_color="#0d0d0d"
            ).resize((220, 220), Image.LANCZOS)
            self._qr_url = url
            print(f"[MobileServer] QR generated once for: {url}")
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
 
        Handler.db_path  = db_path
        Handler.on_order = staticmethod(_on_post)
        Handler.vercel_url = self._db.get_setting("mobile_url_override", "").strip()
        self._handler_class = Handler
        return Handler
 
    # ── Start / stop ──────────────────────────────────────
    def start(self):
        # 1. Start HTTP server
        try:
            handler = self._make_handler_class()
            self._server = HTTPServer(("0.0.0.0", self._port), handler)
            self._thread = threading.Thread(target=self._server.serve_forever,
                                            daemon=True)
            self._thread.start()
            print(f"[MobileServer] HTTP server listening on port {self._port}")
        except OSError as e:
            print(f"[MobileServer] Could not start HTTP server: {e}")
            return
 
        # 2. Determine QR URL — prefer mobile_url_override setting if set
        try:
            manual = self._db.get_setting("mobile_url_override", "").strip()
        except Exception:
            manual = ""
        self._qr_url = manual if manual else f"http://{self._ip}:{self._port}"

        # 3. Generate QR from the chosen URL
        self._generate_qr(self._qr_url)
 
    def stop(self):
        if self._server:
            self._server.shutdown()
 
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
 
    # ── Poll for incoming orders (call from Tk main loop) ─
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
        QR is displayed from self._qr_pil (generated once at start).
        No QR regeneration happens here.
        """
        win = tk.Toplevel(parent)
        win.title("Mobile Order — QR Code")
        win.configure(bg="#0d0d0d")
        win.resizable(False, False)
 
        W, H = 400, 530
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
 
        # Header
        hdr = tk.Frame(win, bg="#FF6B35", pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Mobile Order Terminal",
                 font=("Georgia", 14, "bold"),
                 bg="#FF6B35", fg="white").pack()
        tk.Label(hdr, text="Waiters scan this QR to place orders",
                 font=("Arial", 9),
                 bg="#FF6B35", fg="#330000").pack(pady=(2, 0))
 
        body = tk.Frame(win, bg="#0d0d0d", pady=10)
        body.pack(fill="both", expand=True)
 
        if not self.is_running():
            tk.Label(body,
                     text="Server not running.\nCheck if port 5000 is available.",
                     font=("Arial", 12),
                     bg="#0d0d0d", fg="#e53935",
                     justify="center").pack(expand=True)
            return
 
        # Fixed local URL (this is what the QR encodes)
        local_url = self._qr_url or f"http://{self._ip}:{self._port}"
 
        tk.Label(body, text="Scan to Order  —  Fixed QR (never changes)",
                 font=("Arial", 9, "bold"),
                 bg="#0d0d0d", fg="#666").pack(pady=(6, 2))
 
        # URL display + copy button
        url_row = tk.Frame(body, bg="#1a1a1a",
                           highlightbackground="#333", highlightthickness=1)
        url_row.pack(fill="x", padx=30, pady=(0, 8))
        url_val_lbl = tk.Label(url_row, text=local_url,
                 font=("Courier New", 10),
                 bg="#1a1a1a", fg="#FFA500")
        url_val_lbl.pack(side="left", fill="x", expand=True, padx=10, pady=8)
 
        def copy_url():
            win.clipboard_clear()
            win.clipboard_append(local_url)
            btn_copy.config(text="Copied!")
            win.after(1500, lambda: btn_copy.config(text="Copy"))
 
        btn_copy = tk.Button(url_row, text="Copy", command=copy_url,
                             bg="#4CAF50", fg="white",
                             font=("Arial", 9, "bold"), bd=0, padx=10,
                             cursor="hand2")
        btn_copy.pack(side="right", padx=4, pady=4)
 
        # QR code — show cached image (no regeneration)
        qr_frame = tk.Frame(body, bg="#0d0d0d")
        qr_frame.pack(pady=10)
 
        if QR_AVAILABLE and self._qr_pil is not None:
            photo = ImageTk.PhotoImage(self._qr_pil)
            qr_lbl = tk.Label(qr_frame, image=photo, bg="#0d0d0d")
            qr_lbl.image = photo   # prevent GC
            qr_lbl.pack()
        else:
            tk.Label(qr_frame,
                     text="QR unavailable\nInstall: pip install qrcode[pil] pillow",
                     font=("Courier New", 10),
                     bg="#0d0d0d", fg="#666",
                     justify="center").pack(padx=20, pady=20)
 
        tk.Label(body,
                 text="Menu updates reflect live — no need to reprint QR",
                 font=("Arial", 8),
                 bg="#0d0d0d", fg="#444").pack()
 
        tk.Button(win, text="Close", command=win.destroy,
                  bg="#2a2a2a", fg="#ccc",
                  font=("Arial", 11, "bold"), bd=0, pady=8,
                  cursor="hand2").pack(fill="x", padx=40, pady=12)
 
 
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
                       highlightbackground="#3a3a3a",
                       highlightthickness=1)
        row.pack(fill="x", pady=2, ipady=4)
        tk.Label(row, text=f"  {item['qty']}×  {item['name']}",
                 font=("Courier New", 11),
                 bg="#2a2a2a", fg="#f0f0f0",
                 anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(row, text=f"  {curr}{item['qty']*item['price']:.0f}  ",
                 font=("Courier New", 11),
                 bg="#2a2a2a", fg="#FFA500").pack(side="right")
 
    note = order.get("note", "").strip()
    if note:
        note_frame = tk.Frame(list_frame, bg="#2a1a00", padx=10, pady=6)
        note_frame.pack(fill="x", pady=(8, 0))
        tk.Label(note_frame, text=f"📝  {note}",
                 font=("Arial", 10),
                 bg="#2a1a00", fg="#FFA500",
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
        win.destroy()
        on_accept(order)
 
    def reject():
        win.destroy()
        on_reject()
 
    tk.Button(btn_row, text="✔  Accept",
              command=accept,
              bg="#4CAF50", fg="white",
              font=("Arial", 13, "bold"),
              bd=0, pady=12, cursor="hand2").pack(
        side="left", expand=True, fill="x", padx=(0, 8))
 
    tk.Button(btn_row, text="✕  Reject",
              command=reject,
              bg="#e53935", fg="white",
              font=("Arial", 13, "bold"),
              bd=0, pady=12, cursor="hand2").pack(
        side="left", expand=True, fill="x")