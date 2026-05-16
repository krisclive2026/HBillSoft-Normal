"""
═══════════════════════════════════════════════════════════════════════════
  KRISC BILLSOFT — DEVELOPER KEY GENERATOR  v8
  pip install cryptography
═══════════════════════════════════════════════════════════════════════════
"""

import base64
import tkinter as tk
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import padding as _padding
from cryptography.hazmat.primitives import hashes as _hashes, serialization as _serial

# ═══════════════════════════════════════════════════════════
#  PASTE YOUR PRIVATE KEY HERE
# ═══════════════════════════════════════════════════════════
_RSA_PRIVATE_KEY_PEM = """
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC3wf0XwKnH4b1V
t4wBRHhh8WZKkY5HCvoglJVym68xl65XDdetL4svDYKUkWHU3W7EtRJ/pWIXWSUh
6gSdA35X94MKbogNcBbDdGEn3IxF/ZPPez/JBfLhXktIOx4/xWrbnmwBt1nIS/TI
ob6fSCfMQQ3zhX+n/w2VTeiVidY5MnwZvBqDJikPNT4CAdUMoU4jNUcrMKab1t+E
iisoQglKsZaTa2MISY6zMB1lWt7EPiywyL98RqYV+CDw2eHVRrMiyV9MuVEnKXGA
z0eMEDVApprV+QAMxItO+cjHka9cxmBNwkhYf8Vlp6Y+IJZWAQRcvF2e/xVAWbly
HVB0WTCPAgMBAAECggEAFPlzApmOp46INnb/Z4uhtAhCVUOc+lXx6/MZxd2oVyBJ
mY0ub4msOOAxZfTcNlhaEuDaLjC57BFUUDUudp+V9cN+NRwdsm73YjLv/gVKC5kg
nH+kbbUcnoXNUP7SepP1mQDRsjZz7I1i8N2pbPPm+wT36zJzOkE+Eysz35G+noOH
VpmEaBUwAoLvxX+6bhQXLSLgbqOGbsBfhu8enPvqTc1tCysaZYekDIoU6TOQB2LV
Ut+PpBmT9CfaFSZ00xMn3iM17vKZUPghABE32OLUAKeXsLUTJNk1buSloU2r+7Yv
zSJW842HJvlbbfxdHiqh2zY1koYIBw+aLtQfqGnpvQKBgQDzoDBeh+Q4C/0GSby8
vIYEQouYNNhbffuUeTkzjCeg659SGlYCS7nBfsSliwU2KuIIkTL0H0Px6jT2f+pr
hHam2U+c+9HiLjSzzOAB1xUZGssM5HJkz75uMsIWI5KDSD98WJQM4KvYqQwiS4W9
tmL72HPOvDU/Ln3MgicgMJMDywKBgQDBF1mQbh8d+VBnNJl9WALhHYaAJUhCAQft
NpXa6Su7QBeg53rLIRJFfXIb56pD75Z3QmkH9yyxVvDCRLOkdqEHTDGQjSa8WMfG
IcfipZvspdzpW6yh6hL0XXWscrTQfPe0MIRrEzKlJMNElycesVGdM25UcX3t62fn
T2Wvbv6VzQKBgQCFGcZzTvDrgfk53z1DLAhX+XdEr9Joofq50kTjGbZo33IKrCLD
XFXfFgAfpUUyo9kb7yAUaaR4XYmUBqyvEw6z91Pco2O2m6HlfZAA0V5QeefnYkPx
OeKDWC3bZJHeMbGloMs6AeFBHJJphjNKQ4PurgIPN5orq53FBnKTzpXzYwKBgQCN
APIkqGYMy21NkHmtsMGZhqgbmB4mJP6W2U+hZrjKqskWdTOUdngTSsIzYn9R0Pn9
6P8uE/ANKMHz+5t7tC1vWNKxDoKE9Agexbhj6C/vJkgmGQ39xyNEU6OE5NbpkPiK
Gwv37TMEqc32nrKwlShWNaKSA7bEMS3VGoPVEqbS2QKBgAgMeAFHj61gauUW6TjS
Z5wlLr2fsvkZnVKrsO+jBC5oLys9onDN6oWqe3JUuYYrf+NQstxKu/vLNtWoefKO
/2way5Tlyjp/JAfG6GK6uJtp9ZP6PmC32j2/dtLu6KU1jfl9+7eSEZ5mTreZndHK
sqx0IhmwIES2kh3VtxS7K4vz
-----END PRIVATE KEY-----

"""

_ACTIVATION_SALT = b"KRISC_ACT_2026"

# ── Palette ─────────────────────────────────────────────────
BG       = "#0a0d13"
SURFACE  = "#111827"
CARD     = "#161d2e"
BORDER   = "#1f2d45"
HL       = "#2a3f60"
CYAN     = "#22d3ee"
CYAN_DIM = "#0e4a5a"
GREEN    = "#4ade80"
GREEN_DIM= "#0f3320"
AMBER    = "#fbbf24"
RED      = "#f87171"
TEXT     = "#e2e8f0"
SUB      = "#64748b"
GHOST    = "#1e293b"

# ── Crypto ───────────────────────────────────────────────────
def _load_private_key():
    import textwrap, re
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    raw = textwrap.dedent(_RSA_PRIVATE_KEY_PEM).strip()
    if not raw:
        return None, "No private key set."
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    clean = "\n".join(lines) + "\n"
    try:
        return load_pem_private_key(clean.encode(), password=None), None
    except TypeError:
        return None, "Key is password-protected."
    except Exception:
        pass
    try:
        b64 = re.sub(r"-----[^-]+-----|\s+", "", raw)
        wrapped = "\n".join(b64[i:i+64] for i in range(0, len(b64), 64))
        hdr = "RSA PRIVATE KEY" if "RSA" in raw.upper() else "PRIVATE KEY"
        rebuilt = f"-----BEGIN {hdr}-----\n{wrapped}\n-----END {hdr}-----\n"
        return load_pem_private_key(rebuilt.encode(), password=None), None
    except Exception as e:
        return None, f"Could not load key: {e}"

def _sign(payload):
    key, err = _load_private_key()
    if err: return None, err
    try:
        sig = key.sign(payload.encode(),
                       _padding.PSS(mgf=_padding.MGF1(_hashes.SHA256()),
                                    salt_length=_padding.PSS.MAX_LENGTH),
                       _hashes.SHA256())
        return base64.b64encode(sig).decode(), None
    except Exception as e:
        return None, str(e)

def decode_activation_secret_key(sk):
    try:
        salted = base64.b64decode(sk.strip())
        raw = bytes(salted[i] ^ _ACTIVATION_SALT[i % len(_ACTIVATION_SALT)] for i in range(len(salted)))
        return raw.decode(), None
    except:
        return None, "Invalid secret key."

def decode_renewal_secret_key(sk):
    try:
        parts = base64.b64decode(sk.strip()).decode().split(":")
        if len(parts) != 2: raise ValueError()
        return (parts[0].strip(), parts[1].strip()), None
    except:
        return None, "Invalid secret key."

def generate_activation_key(machine_id, expiry):
    sig, err = _sign(f"{machine_id.upper()}|{expiry}")
    return (f"{expiry}:{sig}", None) if not err else (None, err)

def generate_renewal_key(serial, machine_id, expiry):
    sig, err = _sign(f"{serial.upper()}|{machine_id.upper()}|{expiry}")
    return (sig, None) if not err else (None, err)

def valid_date(s):
    try: datetime.strptime(s.strip(), "%Y-%m-%d"); return True
    except: return False


# ══════════════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KRISC · Key Generator")
        self.configure(bg=BG)
        self.resizable(False, False)
        W, H = 620, 680
        self.geometry(f"{W}x{H}")
        self.update_idletasks()
        self.geometry(f"{W}x{H}+{(self.winfo_screenwidth()-W)//2}+{(self.winfo_screenheight()-H)//2}")
        self._build()

    # ─────────────────────────────────────────────────────
    def _build(self):
        # ── Header ──
        hdr = tk.Frame(self, bg="#07090f", height=52)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Frame(hdr, bg=CYAN, width=3).pack(side=tk.LEFT, fill="y")
        lf = tk.Frame(hdr, bg="#07090f"); lf.pack(side=tk.LEFT, padx=14)
        lf.place(relx=0, rely=0.5, anchor="w", x=3)
        tk.Label(lf, text="◈  KRISC BILLSOFT", font=("Courier", 12, "bold"),
                 bg="#07090f", fg=TEXT).pack(side=tk.LEFT)
        tk.Label(lf, text="  KEY GENERATOR", font=("Courier", 10),
                 bg="#07090f", fg=SUB).pack(side=tk.LEFT)
        tk.Label(hdr, text="v8", font=("Courier", 8),
                 bg="#07090f", fg=SUB).place(relx=1, rely=0.5, anchor="e", x=-16)

        tk.Frame(self, bg=CYAN, height=1).pack(fill="x")

        # ── Tabs ──
        tab_bar = tk.Frame(self, bg=SURFACE, height=38)
        tab_bar.pack(fill="x"); tab_bar.pack_propagate(False)
        self._tab_btns = {}
        self._active_tab = "activation"
        for k, lbl, icon in [("activation", "ACTIVATION KEY", "⊞"),
                              ("renewal",    "RENEWAL KEY",   "↻")]:
            b = tk.Label(tab_bar, text=f" {icon} {lbl} ",
                         font=("Courier", 9, "bold"),
                         bg=SURFACE, fg=SUB, pady=10, cursor="hand2")
            b.pack(side=tk.LEFT, padx=(8, 0))
            b.bind("<Button-1>", lambda e, k=k: self._switch(k))
            self._tab_btns[k] = b

        self._tab_line = tk.Frame(self, bg=BORDER, height=1)
        self._tab_line.pack(fill="x")

        # ── Pages ──
        self._body = tk.Frame(self, bg=BG)
        self._body.pack(fill="both", expand=True)
        self._pages = {
            "activation": self._page_activation(self._body),
            "renewal":    self._page_renewal(self._body),
        }
        self._switch("activation")

        # ── Footer ──
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        tk.Label(self, text="KRISC Systems © 2026  ·  Keep private key confidential",
                 font=("Courier", 7), bg=BG, fg=SUB).pack(pady=6)

    def _switch(self, key):
        self._active_tab = key
        for k, b in self._tab_btns.items():
            b.config(fg=CYAN if k == key else SUB,
                     bg="#0d1525" if k == key else SURFACE)
        for k, p in self._pages.items():
            (p.pack if k == key else p.pack_forget)(fill="both", expand=True) if k == key else p.pack_forget()

    # ─── Widget helpers ──────────────────────────────────
    def _lbl(self, p, t, fg=SUB, size=8, bold=False, bg=BG):
        return tk.Label(p, text=t, font=("Courier", size, "bold" if bold else "normal"),
                        bg=bg, fg=fg, anchor="w")

    def _entry(self, parent, var, hint=""):
        e = tk.Entry(parent, textvariable=var, font=("Courier", 10),
                     bg=GHOST, fg=TEXT, insertbackground=CYAN,
                     relief="flat", bd=0,
                     highlightthickness=1,
                     highlightbackground=BORDER,
                     highlightcolor=CYAN)
        e.pack(fill="x", ipady=9, pady=(3, 0))
        if hint:
            var.set(hint); e.config(fg=SUB)
            e.bind("<FocusIn>",  lambda ev: (var.set(""),   e.config(fg=TEXT))  if var.get() == hint else None)
            e.bind("<FocusOut>", lambda ev: (var.set(hint), e.config(fg=SUB))   if not var.get()     else None)
        return e

    def _card(self, parent, title, accent=BORDER):
        wrap = tk.Frame(parent, bg=accent, padx=1, pady=1)
        wrap.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(wrap, bg=CARD, padx=14, pady=12)
        inner.pack(fill="x")
        tk.Label(inner, text=title, font=("Courier", 7, "bold"),
                 bg=CARD, fg=SUB).pack(anchor="w", pady=(0, 8))
        return inner

    def _pill_row(self, parent, var):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=(0, 8))
        for days, lbl in [(30,"30d"),(90,"90d"),(180,"6m"),(365,"1yr"),(730,"2yr")]:
            d = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            b = tk.Label(row, text=lbl, font=("Courier", 8, "bold"),
                         bg=GHOST, fg=CYAN, padx=8, pady=4,
                         cursor="hand2",
                         highlightthickness=1, highlightbackground=HL)
            b.pack(side=tk.LEFT, padx=(0, 5))
            b.bind("<Enter>", lambda e, b=b: b.config(bg=CYAN_DIM, highlightbackground=CYAN))
            b.bind("<Leave>", lambda e, b=b: b.config(bg=GHOST,    highlightbackground=HL))
            b.bind("<Button-1>", lambda e, d=d: var.set(d))

    def _gen_btn(self, parent, text, cmd):
        wrap = tk.Frame(parent, bg=CYAN, padx=1, pady=1)
        wrap.pack(fill="x", pady=(4, 0))
        inner = tk.Frame(wrap, bg=CYAN_DIM)
        inner.pack(fill="x")
        b = tk.Label(inner, text=text, font=("Courier", 11, "bold"),
                     bg=CYAN_DIM, fg=CYAN, pady=11, cursor="hand2")
        b.pack(fill="x")
        b.bind("<Enter>",    lambda e: (b.config(bg=CYAN, fg="#000d14"),    inner.config(bg=CYAN)))
        b.bind("<Leave>",    lambda e: (b.config(bg=CYAN_DIM, fg=CYAN),     inner.config(bg=CYAN_DIM)))
        b.bind("<Button-1>", lambda e: cmd())
        inner.bind("<Button-1>", lambda e: cmd())

    def _output_area(self, parent):
        """Output box + copy button in one compact block."""
        wrap = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        wrap.pack(fill="x", pady=(12, 0))
        inner = tk.Frame(wrap, bg="#08111e", padx=14, pady=12)
        inner.pack(fill="x")

        # Label row
        top = tk.Frame(inner, bg="#08111e")
        top.pack(fill="x", pady=(0, 6))
        tk.Label(top, text="GENERATED KEY", font=("Courier", 7, "bold"),
                 bg="#08111e", fg=GREEN).pack(side=tk.LEFT)

        # ── COPY BUTTON  (top-right, always visible) ──
        copy_btn = tk.Label(top,
                            text=" ⊕ COPY ",
                            font=("Courier", 8, "bold"),
                            bg=GREEN_DIM, fg=GREEN,
                            padx=10, pady=3,
                            cursor="hand2",
                            relief="flat",
                            highlightthickness=1,
                            highlightbackground=GREEN)
        copy_btn.pack(side=tk.RIGHT)

        # Text output
        txt = tk.Text(inner, font=("Courier", 9),
                      bg="#08111e", fg=GREEN,
                      relief="flat", bd=0, height=4,
                      wrap="word", state="disabled",
                      cursor="arrow",
                      selectbackground="#0f3a22",
                      selectforeground=GREEN)
        txt.pack(fill="x")

        def do_copy():
            val = txt.get("1.0", "end").strip()
            if not val: return
            self.clipboard_clear()
            self.clipboard_append(val)
            copy_btn.config(text=" ✓ COPIED ", bg="#0a3a22",
                            highlightbackground=GREEN)
            self.after(2000, lambda: copy_btn.config(
                text=" ⊕ COPY ", bg=GREEN_DIM,
                highlightbackground=GREEN))

        copy_btn.bind("<Button-1>", lambda e: do_copy())
        copy_btn.bind("<Enter>",    lambda e: copy_btn.config(bg="#0a3a22"))
        copy_btn.bind("<Leave>",    lambda e: copy_btn.config(bg=GREEN_DIM))

        return txt

    def _status(self, parent):
        lbl = tk.Label(parent, text="", font=("Courier", 8),
                       bg=BG, fg=RED, wraplength=580, justify="left")
        lbl.pack(anchor="w", pady=(6, 0))
        return lbl

    # ─── Activation page ─────────────────────────────────
    def _page_activation(self, parent):
        pg = tk.Frame(parent, bg=BG)
        f  = tk.Frame(pg, bg=BG, padx=20, pady=16)
        f.pack(fill="both", expand=True)

        self._lbl(f, "① PASTE CUSTOMER SECRET KEY", TEXT, 8, True).pack(anchor="w", pady=(0, 4))
        c1 = self._card(f, "SECRET KEY", CYAN_DIM)
        self._ask_var = tk.StringVar()
        self._entry(c1, self._ask_var, "Paste secret key here…")
        self._a_decoded = tk.Label(c1, text="", font=("Courier", 8),
                                   bg=CARD, fg=AMBER, anchor="w")
        self._a_decoded.pack(anchor="w", pady=(4, 0))
        self._ask_var.trace("w", self._on_ask_change)

        self._lbl(f, "② SET EXPIRY & GENERATE", TEXT, 8, True).pack(anchor="w", pady=(10, 4))
        c2 = self._card(f, "EXPIRY DATE", CYAN_DIM)
        self._a_exp = tk.StringVar()
        default = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        self._pill_row(c2, self._a_exp)
        self._entry(c2, self._a_exp)
        self._a_exp.set(default)

        self._a_status = self._status(f)
        self._gen_btn(f, "  ⚡  GENERATE ACTIVATION KEY", self._do_activation)

        self._a_out = self._output_area(f)
        return pg

    def _on_ask_change(self, *_):
        v = self._ask_var.get().strip()
        if not v or v == "Paste secret key here…":
            self._a_decoded.config(text=""); return
        mid, err = decode_activation_secret_key(v)
        self._a_decoded.config(text=f"⚠ {err}" if err else f"✓ Machine: {mid}",
                               fg=RED if err else AMBER)

    def _do_activation(self):
        self._a_status.config(text="", fg=RED)
        sk, exp = self._ask_var.get().strip(), self._a_exp.get().strip()
        if not sk or sk == "Paste secret key here…":
            self._a_status.config(text="⚠ Paste the customer secret key."); return
        mid, err = decode_activation_secret_key(sk)
        if err: self._a_status.config(text=f"⚠ {err}"); return
        if not valid_date(exp):
            self._a_status.config(text="⚠ Enter valid date (YYYY-MM-DD)."); return
        key, err = generate_activation_key(mid, exp)
        if err: self._a_status.config(text=f"✗ {err}"); return
        self._set_out(self._a_out, key)
        self._a_status.config(text=f"✓ Generated  ·  {exp}  ·  {mid}", fg=GREEN)

    # ─── Renewal page ─────────────────────────────────────
    def _page_renewal(self, parent):
        pg = tk.Frame(parent, bg=BG)
        f  = tk.Frame(pg, bg=BG, padx=20, pady=16)
        f.pack(fill="both", expand=True)

        self._lbl(f, "① PASTE CUSTOMER SECRET KEY", TEXT, 8, True).pack(anchor="w", pady=(0, 4))
        c1 = self._card(f, "SECRET KEY", HL)
        self._rsk_var = tk.StringVar()
        self._entry(c1, self._rsk_var, "Paste secret key here…")
        self._r_decoded = tk.Label(c1, text="", font=("Courier", 8),
                                   bg=CARD, fg=AMBER, anchor="w", wraplength=560)
        self._r_decoded.pack(anchor="w", pady=(4, 0))
        self._rsk_var.trace("w", self._on_rsk_change)

        self._lbl(f, "② SET NEW EXPIRY & GENERATE", TEXT, 8, True).pack(anchor="w", pady=(10, 4))
        c2 = self._card(f, "NEW EXPIRY DATE", HL)
        self._r_exp = tk.StringVar()
        default = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        self._pill_row(c2, self._r_exp)
        self._entry(c2, self._r_exp)
        self._r_exp.set(default)

        self._r_status = self._status(f)
        self._gen_btn(f, "  ⚡  GENERATE RENEWAL KEY", self._do_renewal)

        self._r_out = self._output_area(f)
        return pg

    def _on_rsk_change(self, *_):
        v = self._rsk_var.get().strip()
        if not v or v == "Paste secret key here…":
            self._r_decoded.config(text=""); return
        res, err = decode_renewal_secret_key(v)
        if err:
            self._r_decoded.config(text=f"⚠ {err}", fg=RED)
        else:
            self._r_decoded.config(text=f"✓ Serial: {res[0]}  ·  Machine: {res[1]}", fg=AMBER)

    def _do_renewal(self):
        self._r_status.config(text="", fg=RED)
        sk, exp = self._rsk_var.get().strip(), self._r_exp.get().strip()
        if not sk or sk == "Paste secret key here…":
            self._r_status.config(text="⚠ Paste the customer secret key."); return
        res, err = decode_renewal_secret_key(sk)
        if err: self._r_status.config(text=f"⚠ {err}"); return
        serial, mid = res
        if not valid_date(exp):
            self._r_status.config(text="⚠ Enter valid date (YYYY-MM-DD)."); return
        key, err = generate_renewal_key(serial, mid, exp)
        if err: self._r_status.config(text=f"✗ {err}"); return
        self._set_out(self._r_out, key)
        self._r_status.config(text=f"✓ Generated  ·  {exp}  ·  {serial[:10]}…", fg=GREEN)

    # ─── Helpers ──────────────────────────────────────────
    def _set_out(self, widget, text):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")


if __name__ == "__main__":
    App().mainloop()
