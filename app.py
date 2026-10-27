import os
import sqlite3
import secrets
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string, flash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "merrygoround.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

PAGE_SIZE = 5

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            range_number INTEGER NOT NULL,
            chosen_amount INTEGER NOT NULL,
            entry_fee INTEGER NOT NULL,
            maintenance_fee INTEGER NOT NULL,
            entry_paid INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(phone, range_number),
            FOREIGN KEY(range_number) REFERENCES ranges(range_number)
        );
        CREATE TABLE IF NOT EXISTS ranges (
            range_number INTEGER PRIMARY KEY,
            low_amount INTEGER NOT NULL,
            high_amount INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            range_number INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            beneficiary_member_id INTEGER,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            UNIQUE(range_number, round_number),
            FOREIGN KEY(range_number) REFERENCES ranges(range_number),
            FOREIGN KEY(beneficiary_member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS contributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            maintenance_fee INTEGER NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'pending',
            mpesa_receipt TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(round_id, member_id),
            FOREIGN KEY(round_id) REFERENCES rounds(id),
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS beneficiary_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            range_number INTEGER NOT NULL,
            round_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            selected_at TEXT NOT NULL,
            UNIQUE(round_id),
            FOREIGN KEY(round_id) REFERENCES rounds(id),
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        """)
        # Seed the first ranges; further ranges are generated as needed.
        for n in range(1, 6):
            low = 10 if n == 1 else 21 + (n - 2) * 10
            high = 20 if n == 1 else low + 9
            con.execute(
                "INSERT OR IGNORE INTO ranges(range_number, low_amount, high_amount) VALUES (?, ?, ?)",
                (n, low, high)
            )

def ensure_range(con, n):
    if n < 1:
        raise ValueError("Range number must be positive.")
    low = 10 if n == 1 else 21 + (n - 2) * 10
    high = 20 if n == 1 else low + 9
    con.execute(
        "INSERT OR IGNORE INTO ranges(range_number, low_amount, high_amount) VALUES (?, ?, ?)",
        (n, low, high)
    )
    return low, high

def get_range_data(con, n):
    low, high = ensure_range(con, n)
    count = con.execute("SELECT COUNT(*) c FROM members WHERE range_number=?", (n,)).fetchone()["c"]
    return {"range_number": n, "low": low, "high": high, "occupied": count, "full": count >= 10}

TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Merry-Go-Round Range Selector</title>
<style>
:root{font-family:system-ui,-apple-system,Arial,sans-serif;color:#18212f;background:#f4f7fb}
*{box-sizing:border-box}body{margin:0}header{background:#123b63;color:white;padding:22px 16px}
main{max-width:920px;margin:20px auto;padding:0 14px}.panel{background:white;border:1px solid #dce4ee;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 3px 12px #0b25400a}
h1{font-size:1.45rem;margin:0 0 5px}h2{font-size:1.12rem;margin:0 0 12px}p{line-height:1.5}
button,.button{background:#145a91;color:white;border:0;border-radius:9px;padding:11px 14px;font-size:1rem;cursor:pointer;text-decoration:none;display:inline-block}
button.secondary,.button.secondary{background:#e7eef6;color:#173b5b}button:disabled{opacity:.45;cursor:not-allowed}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px}
.range{border:1px solid #dce4ee;border-radius:10px;padding:12px}.range strong{display:block;font-size:1.05rem}.muted{color:#5b6878;font-size:.9rem}
input,select{width:100%;padding:11px;border:1px solid #bac8d8;border-radius:8px;margin:5px 0 12px;font:inherit}
label{font-weight:600;font-size:.93rem}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.notice{background:#fff6d8;padding:12px;border-radius:9px;color:#624b00}.success{background:#e4f7eb;padding:12px;border-radius:9px;color:#14532d}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid #e2e8f0;font-size:.92rem}
footer{text-align:center;padding:22px;color:#5b6878;font-size:.85rem}
</style>
</head>
<body>
<header><h1>Merry-Go-Round Range Selector</h1><div>Browse ranges, join a circle, and track round status.</div></header>
<main>
{% with messages = get_flashed_messages() %}
{% if messages %}{% for message in messages %}<div class="panel success">{{message}}</div>{% endfor %}{% endif %}
{% endwith %}
<div class="panel">
<h2>1. Previously selected ranges</h2>
<p class="muted">Shows five ranges per page, including how many members have joined each range.</p>
<div class="grid">
{% for r in occupied %}
<div class="range"><strong>KSh {{r.low}}–{{r.high}}</strong><div class="muted">Range {{r.range_number}} · {{r.occupied}}/10 members</div>
<div class="muted">{% if r.full %}Full{% elif r.occupied %}Occupied{% else %}No members yet{% endif %}</div></div>
{% else %}<p>No ranges to show.</p>{% endfor %}
</div>
<div class="row" style="margin-top:12px">
<a class="button secondary" href="{{url_for('home', occupied_page=[occupied_page-1,0]|max, browse_page=browse_page)}}">Previous five</a>
<a class="button" href="{{url_for('home', occupied_page=occupied_page+1, browse_page=browse_page)}}">Next five</a>
</div>
</div>
<div class="panel">
<h2>2. Browse ranges to join</h2>
<p class="muted">Five ranges appear at a time. Continue pressing Next five to browse further ranges.</p>
<div class="grid">
{% for r in browse %}
<div class="range"><strong>KSh {{r.low}}–{{r.high}}</strong><div class="muted">Range {{r.range_number}} · {{r.occupied}}/10 members</div>
{% if r.full %}<button disabled>Full</button>{% else %}<a class="button" href="{{url_for('home', occupied_page=occupied_page, browse_page=browse_page, selected=r.range_number)}}">Select range</a>{% endif %}
</div>
{% endfor %}
</div>
<div class="row" style="margin-top:12px">
<a class="button secondary" href="{{url_for('home', occupied_page=occupied_page, browse_page=[browse_page-1,0]|max)}}">Previous five</a>
<a class="button" href="{{url_for('home', occupied_page=occupied_page, browse_page=browse_page+1)}}">Next five</a>
</div>
</div>
{% if selected %}
<div class="panel" id="join">
<h2>3. Join KSh {{selected.low}}–{{selected.high}} range</h2>
{% if selected.full %}<div class="notice">This range is full. Please select another range.</div>
{% else %}
<p>Maintenance fee: <strong>KSh {{selected.range_number * 8}}</strong> (KSh 8 × range number).</p>
<p>One-time circle entry fee: <strong>KSh {{selected.high * 10}}</strong> (highest amount × 10). This is not charged again in later rounds.</p>
<form method="post" action="{{url_for('join_range')}}">
<input type="hidden" name="range_number" value="{{selected.range_number}}">
<label>Full name</label><input name="full_name" required maxlength="100" placeholder="Enter your name">
<label>Phone number</label><input name="phone" required maxlength="20" placeholder="e.g. 07XXXXXXXX">
<label>Contribution amount (KSh {{selected.low}}–{{selected.high}})</label>
<select name="chosen_amount" required>
<option value="" selected disabled>-- Select your amount --</option>
{% for amount in range(selected.low, selected.high+1) %}
<option value="{{amount}}">KSh {{amount}}</option>
{% endfor %}
</select>
<div class="notice">Initial amount due = your chosen contribution + maintenance fee + one-time entry fee. This demo records payment as pending; it does not collect or confirm real M-PESA payments.</div>
<button type="submit">Register and calculate fees</button>
</form>
{% endif %}
{% endif %}
</div>
<div class="panel">
<h2>4. Recent registrations and round status</h2>
{% if recent %}
<div style="overflow-x:auto"><table><tr><th>Member</th><th>Range</th><th>Amount</th><th>Entry fee</th><th>Entry status</th></tr>
{% for m in recent %}<tr><td>{{m.full_name}}</td><td>KSh {{m.low_amount}}–{{m.high_amount}}</td><td>KSh {{m.chosen_amount}}</td><td>KSh {{m.entry_fee}}</td><td>{{'Paid' if m.entry_paid else 'Pending'}}</td></tr>{% endfor %}
</table></div>
{% else %}<p class="muted">No registrations yet.</p>{% endif %}
<p class="muted">A real beneficiary is selected only after the backend verifies all required payments for a complete group of ten. No payment confirmation or payout is simulated by this starter website.</p>
</div>
</main><footer>Demo starter · Use verified payment callbacks and secure deployment before handling real money.</footer>
</body></html>
"""

# Initialize the database when Flask/Gunicorn loads the app.
init_db()

@app.route("/")
def home():
    occupied_page = max(0, request.args.get("occupied_page", 0, type=int))
    browse_page = max(0, request.args.get("browse_page", 0, type=int))
    selected_n = request.args.get("selected", type=int)
    with db() as con:
        # Only ranges with registered members are listed in the "previously selected" view.
        occupied_nums = [r["range_number"] for r in con.execute(
            "SELECT range_number FROM members GROUP BY range_number ORDER BY range_number"
        ).fetchall()]
        occupied_slice = occupied_nums[occupied_page*PAGE_SIZE:(occupied_page+1)*PAGE_SIZE]
        occupied = [get_range_data(con, n) for n in occupied_slice]

        first_n = browse_page * PAGE_SIZE + 1
        browse = [get_range_data(con, n) for n in range(first_n, first_n + PAGE_SIZE)]
        selected = get_range_data(con, selected_n) if selected_n else None
        recent = con.execute("""
            SELECT m.*, r.low_amount, r.high_amount FROM members m
            JOIN ranges r ON r.range_number=m.range_number
            ORDER BY m.id DESC LIMIT 20
        """).fetchall()
    return render_template_string(TEMPLATE, occupied=occupied, browse=browse,
        selected=selected, recent=recent, occupied_page=occupied_page,
        browse_page=browse_page, range=range)

@app.route("/join", methods=["POST"])
def join_range():
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()

    try:
        n = int(request.form.get("range_number", "0"))
        amount = int(request.form.get("chosen_amount", "0"))
    except (ValueError, TypeError):
        flash("Select a valid range and contribution amount.")
        return redirect(url_for("home"))

    if not full_name or not phone or len(full_name) > 100 or len(phone) > 20:
        flash("Enter a valid name and phone number.")
        return redirect(url_for("home", selected=n))

    try:
        with db() as con:
            low, high = ensure_range(con, n)

            count = con.execute(
                "SELECT COUNT(*) AS c FROM members WHERE range_number=?",
                (n,)
            ).fetchone()["c"]

            if count >= 10:
                flash("That range is full. Each range allows at most ten members.")
                return redirect(url_for("home"))

            if not low <= amount <= high:
                flash("Your chosen contribution must be within the selected range.")
                return redirect(url_for("home", selected=n))

            # Calculate fees for this individual member.
            entry_fee = high * 10
            maintenance_fee = n * 8
            now = datetime.utcnow().isoformat()

            # Save the member. entry_paid remains 0 (unpaid).
            member_cursor = con.execute(
                """INSERT INTO members
                   (full_name, phone, range_number, chosen_amount,
                    entry_fee, maintenance_fee, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (full_name, phone, n, amount, entry_fee,
                 maintenance_fee, now)
            )
            member_id = member_cursor.lastrowid

            # Create round 1 if it does not already exist.
            con.execute(
                """INSERT OR IGNORE INTO rounds
                   (range_number, round_number, status, created_at)
                   VALUES (?, 1, 'open', ?)""",
                (n, now)
            )

            round_row = con.execute(
                """SELECT id FROM rounds
                   WHERE range_number=? AND round_number=1""",
                (n,)
            ).fetchone()

            # Record this member's first-round contribution.
            # It stays pending until payment is genuinely verified.
            con.execute(
                """INSERT INTO contributions
                   (round_id, member_id, amount, maintenance_fee,
                    payment_status, created_at)
                   VALUES (?, ?, ?, ?, 'pending', ?)""",
                (round_row["id"], member_id, amount,
                 maintenance_fee, now)
            )

            total = amount + maintenance_fee + entry_fee

        flash(
            f"Registration saved. Your initial amount is KSh {total}: "
            f"chosen contribution KSh {amount}, maintenance KSh "
            f"{maintenance_fee}, and one-time entry fee KSh {entry_fee}. "
            "Entry fee and round payment are still pending verification."
        )

    except sqlite3.IntegrityError:
        flash("This phone number is already registered in this range.")
    except ValueError as e:
        flash(str(e))

    return redirect(url_for("home"))


@app.route("/health")
def health():
    return {"status": "ok", "app": "Merry-Go-Round Range Selector"}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
