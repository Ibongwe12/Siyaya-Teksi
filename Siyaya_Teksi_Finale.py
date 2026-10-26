import flet as ft
import datetime
import json
import os
import ssl
import time
import urllib.request
import uuid
from urllib.parse import quote

# =====================================================
# ONLINE DATABASE (optional)
# Paste your Firebase Realtime Database address between the quotes to share trips
# between phones, for example:
#   DATABASE_URL = "https://siyaya-teksi-default-rtdb.europe-west1.firebasedatabase.app"

# =====================================================
DATABASE_URL = ""

# Trips older than this (hours since they were posted) are hidden from passengers
TRIP_LIFETIME_HOURS = 12

# =====================================================
# LOOK AND FEEL: change a colour here and the whole app updates.
# Navy and taxi gold, with warm clay and teal from township wall art.
# =====================================================
COLOR_BG = "#F4EFE6"          # page background (warm sand)
COLOR_CARD = "#FFFFFF"        # cards and pop-ups
COLOR_BORDER = "#DDD3C2"      # thin outlines
COLOR_PRIMARY = "#17324D"     # navy: top bar, main buttons, titles
COLOR_ACCENT = "#F2A900"      # taxi gold: highlights, second buttons
COLOR_CLAY = "#C4572F"        # warm clay (colour strip)
COLOR_TEAL = "#0E7C7B"        # teal (colour strip)
COLOR_TEXT = "#1E2A36"        # main text
COLOR_TEXT_MUTED = "#6B6558"  # softer text
COLOR_PILL = "#FCEBB6"        # status label background (light gold)
COLOR_LATER = "#C9C1B2"       # stages not reached yet
COLOR_GOOD = "#1F7A4D"        # seats available / stage done
COLOR_FULL = "#B3261E"        # taxi full
COLOR_SOS = "#C62828"         # SOS and emergency call buttons

# Fonts: download Poppins (free, from fonts.google.com) and put the two files below in
# assets/fonts. If the files are missing, the app simply uses the normal font.
FONT_REGULAR = "Poppins"
FONT_BOLD = "Poppins SemiBold"

# Starting trips, used in "this phone only" mode before any trips.json file exists
DEFAULT_TAXIS = [
    {"id": 1, "driver": "Sipho M.", "route": "Soweto to Johannesburg CBD", "time": "06:30", "seats": 4, "status": "Loading at Rank"},
    {"id": 2, "driver": "Thabo K.", "route": "Soweto to Johannesburg CBD", "time": "07:15", "seats": 15, "status": "En Route"},
    {"id": 3, "driver": "Nkosana Z.", "route": "Khayelitsha to Cape Town CBD", "time": "06:45", "seats": 7, "status": "Loading at Rank"},
    {"id": 4, "driver": "Jabu S.", "route": "Umlazi to Durban CBD", "time": "07:00", "seats": 2, "status": "En Route"}
]

# The stages a trip moves through. A taxi's "status" should match one of these.
STATUS_STEPS = ["Loading at Rank", "Departed Rank", "En Route", "Arrived"]

# Placeholder for real driver sign-up (a full version would check licence or association)
DRIVER_CODE = "TAXI2026"

# Real South African emergency numbers
SAPS_NUMBER = "10111"
GBV_NUMBER = "0800428428"  # GBV Command Centre (free, 24 hours)

# Secure internet connections need a list of trusted certificates. "certifi" provides
# one, which phones need. If it isn't installed, we use the computer's own list.
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CONTEXT = None


def fix_full_taxi_status(taxi):
    """A full taxi can't still be loading, so move it on to 'Departed Rank'.
    Returns True if the status was changed."""
    if taxi["seats"] == 0 and taxi["status"] == "Loading at Rank":
        taxi["status"] = "Departed Rank"
        return True
    return False


def is_recent(taxi):
    """True if the trip was posted within the last TRIP_LIFETIME_HOURS (or has no post time)."""
    posted = taxi.get("posted_at")
    return posted is None or (time.time() - posted) < TRIP_LIFETIME_HOURS * 3600


# Files are saved in Flet's writable data folder when it exists (needed on a phone,
# where the app's own folder is read-only). Otherwise they go next to main.py.
DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA") or os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, "trips.json")
CONTACT_FILE = os.path.join(DATA_DIR, "contact.json")
PROFILE_FILE = os.path.join(DATA_DIR, "profile.json")

# Every trip must have all of these fields
REQUIRED_FIELDS = {"id", "driver", "route", "time", "seats", "status"}


def load_taxis():
    """Load the trips saved on this phone. If there are none (or the file is damaged),
    start with the sample trips, or with an empty list when an online database is used."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(
            isinstance(t, dict) and REQUIRED_FIELDS.issubset(t) for t in data
        ):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    if DATABASE_URL:
        return []
    return [dict(t) for t in DEFAULT_TAXIS]  # fresh copies of the starting trips


def save_taxis():
    """Write all trips to trips.json on this phone (also used as a copy for offline use)."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)  # make sure the folder exists
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(taxis, f, indent=2, ensure_ascii=False)
    except OSError:
        print("Could not save trips to", DATA_FILE)


taxis = load_taxis()


# -----------------------------------------------------
# Online database (Firebase Realtime Database over plain web requests)
# -----------------------------------------------------
def db_request(method, path, data=None, timeout=6):
    """Send one request to the online database and return its reply (or None).
    Raises OSError if the internet or the database can't be reached."""
    url = DATABASE_URL.rstrip("/") + "/" + path + ".json"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        url, data=body, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        text = response.read().decode("utf-8")
    return json.loads(text) if text else None


def fetch_trips():
    """Download every trip from the online database."""
    data = db_request("GET", "trips")
    if data is None:
        return []
    items = data.values() if isinstance(data, dict) else data
    return [t for t in items if isinstance(t, dict) and REQUIRED_FIELDS.issubset(t)]


def push_pending():
    """Try again to send trips that could not be sent earlier. Returns False if still offline."""
    for trip in taxis:
        if trip.get("unsynced"):
            clean = {k: v for k, v in trip.items() if k != "unsynced"}
            try:
                db_request("PUT", "trips/" + str(trip["id"]), clean)
            except (OSError, ValueError):
                return False
            del trip["unsynced"]
    return True


def refresh_taxis():
    """Get the latest trips from the online database.
    Returns "local" (no database set), "live" (updated) or "offline" (can't reach it)."""
    if not DATABASE_URL:
        return "local"
    try:
        push_pending()
        fresh = fetch_trips()
    except (OSError, ValueError):
        return "offline"
    fresh_ids = {str(t["id"]) for t in fresh}
    waiting = [t for t in taxis if t.get("unsynced") and str(t["id"]) not in fresh_ids]
    taxis[:] = fresh + waiting  # change the list in place so the whole app sees it
    save_taxis()
    return "live"


def publish_trip(trip):
    """Save a trip on this phone and, if an online database is set, send it there too.
    Returns "local" (no database set), "online" (sent) or "pending" (no internet; will retry)."""
    trip.pop("unsynced", None)
    if not DATABASE_URL:
        save_taxis()
        return "local"
    try:
        db_request("PUT", "trips/" + str(trip["id"]), trip)
        save_taxis()
        return "online"
    except (OSError, ValueError):
        trip["unsynced"] = True
        save_taxis()
        return "pending"


# -----------------------------------------------------
# Phone numbers, emergency contact and account (all saved on this phone only)
# -----------------------------------------------------
def normalize_phone(raw):
    """Turn a South African number like '082 123 4567' or '+27 82 123 4567' into
    '27821234567' (the format WhatsApp and SMS links need). Returns None if invalid."""
    raw = raw or ""
    if any(ch not in "0123456789 +-()" for ch in raw):
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        return "27" + digits[1:]
    if len(digits) == 11 and digits.startswith("27"):
        return digits
    return None


def load_contact():
    """Load the saved emergency contact, or None if there isn't one."""
    try:
        with open(CONTACT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("name") and normalize_phone(data.get("phone")):
            return {"name": data["name"], "phone": normalize_phone(data["phone"])}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def save_contact(contact):
    """Save the emergency contact, or delete the saved one when contact is None."""
    try:
        if contact is None:
            if os.path.exists(CONTACT_FILE):
                os.remove(CONTACT_FILE)
        else:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(CONTACT_FILE, "w", encoding="utf-8") as f:
                json.dump(contact, f, ensure_ascii=False)
    except OSError:
        print("Could not save the emergency contact")


def load_profile():
    """Load the saved account (role, name, phone, id), or None if nobody is signed in."""
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if (
            isinstance(data, dict)
            and data.get("role") in ("passenger", "driver")
            and (data.get("name") or "").strip()
            and normalize_phone(data.get("phone"))
        ):
            profile = {
                "role": data["role"],
                "name": data["name"].strip(),
                "phone": normalize_phone(data["phone"]),
                "uid": data.get("uid") or uuid.uuid4().hex,
            }
            if not data.get("uid"):
                save_profile(profile)  # older accounts get an id the first time
            return profile
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def save_profile(profile):
    """Save the account so the app remembers it, or delete it (sign out) when profile is None."""
    try:
        if profile is None:
            if os.path.exists(PROFILE_FILE):
                os.remove(PROFILE_FILE)
        else:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False)
    except OSError:
        print("Could not save the account")


# -----------------------------------------------------
# Building blocks for the look of the app
# -----------------------------------------------------
BUTTON_COLORS = {
    "primary": (COLOR_PRIMARY, "#FFFFFF"),   # navy with white text
    "accent": (COLOR_ACCENT, COLOR_PRIMARY),  # gold with navy text
    "danger": (COLOR_SOS, "#FFFFFF"),         # red with white text
}


def app_button(text, on_click=None, icon=None, url=None, width=None, height=48, kind="primary"):
    """A flat, square-cornered button in one of the app's colours."""
    background, foreground = BUTTON_COLORS[kind]
    return ft.ElevatedButton(
        text=text, icon=icon, on_click=on_click, url=url,
        width=width, height=height,
        style=ft.ButtonStyle(
            bgcolor=background,
            color=foreground,
            elevation=0,
            shape=ft.RoundedRectangleBorder(radius=8),
            text_style=ft.TextStyle(font_family=FONT_BOLD, size=14),
        ),
    )


def app_field(**kwargs):
    """A text box with the app's look."""
    return ft.TextField(
        border_radius=8, border_color=COLOR_BORDER, focused_border_color=COLOR_PRIMARY,
        filled=True, bgcolor=COLOR_CARD, text_size=14, **kwargs
    )


def app_dropdown(**kwargs):
    """A dropdown with the app's look."""
    return ft.Dropdown(
        border_radius=8, border_color=COLOR_BORDER, focused_border_color=COLOR_PRIMARY,
        filled=True, bgcolor=COLOR_CARD, text_size=14, **kwargs
    )


def card(content, width=None):
    """A white card with a thin outline."""
    return ft.Container(
        content=content, bgcolor=COLOR_CARD, border=ft.border.all(1, COLOR_BORDER),
        border_radius=12, padding=16, width=width, data="card"
    )


def heading(text, size=20, color=COLOR_PRIMARY):
    """A bold title."""
    return ft.Text(text, size=size, color=color, font_family=FONT_BOLD, weight=ft.FontWeight.W_600)


def pattern_band():
    """A thin strip of township-style colour blocks, shown under the top bar."""
    colors = [COLOR_PRIMARY, COLOR_ACCENT, COLOR_CLAY, COLOR_TEAL] * 6
    return ft.Row([ft.Container(expand=1, height=6, bgcolor=c) for c in colors], spacing=0)


def main(page: ft.Page):
    page.title = "Siyaya Teksi"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.fonts = {
        FONT_REGULAR: "/fonts/Poppins-Regular.ttf",
        FONT_BOLD: "/fonts/Poppins-SemiBold.ttf",
    }
    page.theme = ft.Theme(font_family=FONT_REGULAR, color_scheme_seed=COLOR_PRIMARY)
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.scroll = "adaptive"

    # --- Top bar ---
    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.LOCAL_TAXI, color=COLOR_ACCENT),
        leading_width=48,
        title=ft.Text("SIYAYA TEKSI", size=18, color=ft.Colors.WHITE,
                      font_family=FONT_BOLD, weight=ft.FontWeight.W_600),
        center_title=False,
        bgcolor=COLOR_PRIMARY,
        actions=[]  # the sign-out button is added once someone is signed in
    )

    # Who is signed in on this phone (None if nobody). It is remembered between sessions.
    account = {"profile": load_profile()}

    # The passenger's emergency contact, and the last ride they shared
    emergency = {"contact": load_contact()}
    rider = {"taxi": None}

    # Shown in the top bar while someone is signed in
    signout_button = ft.IconButton(
        ft.Icons.LOGOUT, icon_color=ft.Colors.WHITE, tooltip="Sign out",
        on_click=lambda e: open_signout_dialog()
    )

    def content_width():
        """Width of the main column: up to 450, but never wider than the screen."""
        try:
            w = int(page.width or 0)
        except (TypeError, ValueError):
            w = 0
        return max(280, min(450, w - 32)) if w > 0 else 450

    def dialog_width():
        return min(340, content_width())

    def show(*controls):
        """Replace what is on screen with the colour strip and a centred column of controls."""
        page.clean()
        page.add(
            pattern_band(),
            ft.Container(
                content=ft.Column(
                    list(controls),
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    width=content_width()
                ),
                alignment=ft.alignment.top_center,
                padding=ft.padding.only(top=18, bottom=28),
                expand=True
            )
        )

    def notify(text):
        page.open(ft.SnackBar(ft.Text(text, color=ft.Colors.WHITE), bgcolor=COLOR_PRIMARY))

    # =====================================================
    # POP-UPS
    # =====================================================

    # --- Share Ride Status ---
    def close_share_dialog(e):
        share_dialog.open = False
        page.update()

    share_dialog = ft.AlertDialog(
        title=heading("Share your ride", size=18),
        bgcolor=COLOR_CARD,
        actions=[ft.TextButton("Close", on_click=close_share_dialog)]
    )
    page.overlay.append(share_dialog)

    def share_ride_status(taxi_data):
        rider["taxi"] = taxi_data  # remembered so the SOS message can mention it

        whatsapp_text = (
            f"*Siyaya Teksi - Safety Share*\n\n"
            f"I am boarding a taxi:\n"
            f"*Route:* {taxi_data['route']}\n"
            f"*Scheduled Time:* {taxi_data['time']}\n"
            f"*Driver:* {taxi_data['driver']}\n"
            f"*Status:* {taxi_data['status']}\n\n"
            f"Keeping you updated for my safety!"
        )

        share_dialog.content = ft.Column([
            ft.Text("Send this text message to your family or WhatsApp group:", size=14, color=COLOR_TEXT_MUTED),
            ft.Container(
                content=ft.Text(whatsapp_text, size=13, color=COLOR_TEXT),
                bgcolor=COLOR_PILL,
                padding=14,
                border_radius=8
            )
        ], tight=True, width=dialog_width())

        share_dialog.open = True
        page.update()

    # --- Track a Taxi (status timeline) ---
    def close_track_dialog(e):
        track_dialog.open = False
        page.update()

    track_dialog = ft.AlertDialog(
        bgcolor=COLOR_CARD,
        actions=[ft.TextButton("Close", on_click=close_track_dialog)]
    )
    page.overlay.append(track_dialog)

    def track_taxi(taxi_data):
        # Find which stage the taxi is at (default to the first stage if unknown)
        if taxi_data["status"] in STATUS_STEPS:
            current_step = STATUS_STEPS.index(taxi_data["status"])
        else:
            current_step = 0

        # One row per stage: done = green tick, now = taxi, later = faded circle
        step_rows = []
        for i, step in enumerate(STATUS_STEPS):
            if i < current_step:
                icon, color = ft.Icons.CHECK_CIRCLE, COLOR_GOOD
            elif i == current_step:
                icon, color = ft.Icons.LOCAL_TAXI, COLOR_PRIMARY
            else:
                icon, color = ft.Icons.RADIO_BUTTON_UNCHECKED, COLOR_LATER

            step_rows.append(
                ft.Row([
                    ft.Icon(icon, color=color, size=22),
                    ft.Text(
                        step,
                        color=color,
                        weight=ft.FontWeight.W_600 if i == current_step else ft.FontWeight.NORMAL
                    ),
                ])
            )

        seat_text = f"{taxi_data['seats']} seats available" if taxi_data["seats"] > 0 else "Taxi Full"

        track_dialog.title = heading("Tracking taxi", size=18)
        track_dialog.content = ft.Column([
            ft.Text(taxi_data["route"], size=16, weight=ft.FontWeight.W_600, color=COLOR_PRIMARY),
            ft.Text(f"Driver: {taxi_data['driver']}", size=13, color=COLOR_TEXT_MUTED),
            ft.Text(f"Departure: {taxi_data['time']}  |  {seat_text}", size=13, color=COLOR_TEXT_MUTED),
            ft.Divider(height=10, color=COLOR_BORDER),
            *step_rows,
            ft.Divider(height=10, color=COLOR_BORDER),
            ft.Text("The driver updates this status.", size=11, italic=True, color=COLOR_TEXT_MUTED),
        ], tight=True, width=dialog_width(), spacing=8)

        track_dialog.open = True
        page.update()

    # --- Emergency contact: set, change or remove ---
    def close_contact_dialog(e=None):
        contact_dialog.open = False
        page.update()

    contact_dialog = ft.AlertDialog(
        title=heading("Emergency contact", size=18),
        bgcolor=COLOR_CARD
    )
    page.overlay.append(contact_dialog)

    def open_contact_dialog(on_saved=None):
        existing = emergency["contact"]
        w = dialog_width()

        name_field = app_field(
            label="Contact name",
            value=existing["name"] if existing else "",
            width=w
        )
        phone_field = app_field(
            label="Cell number",
            hint_text="e.g., 082 123 4567",
            value=("+" + existing["phone"]) if existing else "",
            keyboard_type=ft.KeyboardType.PHONE,
            width=w
        )

        def save_click(e):
            name_field.error_text = None
            phone_field.error_text = None
            valid = True

            if not (name_field.value or "").strip():
                name_field.error_text = "Enter a name"
                valid = False

            phone = normalize_phone(phone_field.value)
            if phone is None:
                phone_field.error_text = "Enter a SA number, e.g. 082 123 4567"
                valid = False

            if not valid:
                page.update()
                return

            emergency["contact"] = {"name": name_field.value.strip(), "phone": phone}
            save_contact(emergency["contact"])
            contact_dialog.open = False
            page.update()
            if on_saved:
                on_saved()
            notify("Emergency contact saved.")

        def remove_click(e):
            emergency["contact"] = None
            save_contact(None)
            contact_dialog.open = False
            page.update()
            if on_saved:
                on_saved()
            notify("Emergency contact removed.")

        actions = [ft.TextButton("Cancel", on_click=close_contact_dialog)]
        if existing:
            actions.append(ft.TextButton("Remove", on_click=remove_click))
        actions.append(app_button("Save", on_click=save_click, height=40))

        contact_dialog.content = ft.Column([
            ft.Text("Who should we help you message if you need help?", size=13, color=COLOR_TEXT_MUTED),
            name_field,
            phone_field,
        ], tight=True, width=w, spacing=12)
        contact_dialog.actions = actions
        contact_dialog.open = True
        page.update()

    # --- SOS: message your contact or call for help ---
    def close_sos_dialog(e=None):
        sos_dialog.open = False
        page.update()

    sos_dialog = ft.AlertDialog(
        title=heading("🚨 Get help now", size=18, color=COLOR_SOS),
        bgcolor=COLOR_CARD,
        actions=[ft.TextButton("Close", on_click=close_sos_dialog)]
    )
    page.overlay.append(sos_dialog)

    def build_sos_message():
        profile = account["profile"]
        who = profile["name"] if profile else "a Siyaya Teksi user"
        lines = [f"🚨 This is {who}. I need help. Please call me now."]
        taxi = rider["taxi"]
        if taxi:
            lines += [
                "",
                "The last ride I shared with you:",
                f"Route: {taxi['route']}",
                f"Driver: {taxi['driver']}",
                f"Departure: {taxi['time']}",
            ]
        lines += ["", "Sent from Siyaya Teksi."]
        return "\n".join(lines)

    def open_sos_dialog(on_contact_saved=None):
        contact = emergency["contact"]
        w = dialog_width()
        items = []

        if contact:
            message = quote(build_sos_message())
            items += [
                ft.Text(f"Message {contact['name']}:", weight=ft.FontWeight.W_600, color=COLOR_TEXT),
                ft.Row([
                    app_button("WhatsApp", icon=ft.Icons.CHAT, height=44,
                               url=f"https://wa.me/{contact['phone']}?text={message}"),
                    app_button("SMS", icon=ft.Icons.SMS, height=44,
                               url=f"sms:+{contact['phone']}?body={message}"),
                ]),
                ft.Text("Your phone opens the message ready to go. Tap Send to send it.",
                        size=12, color=COLOR_TEXT_MUTED),
            ]
        else:
            def set_contact_first(e):
                sos_dialog.open = False
                page.update()
                open_contact_dialog(on_saved=on_contact_saved)

            items += [
                ft.Text("You haven't set an emergency contact yet.", color=COLOR_TEXT),
                app_button("Set emergency contact", icon=ft.Icons.CONTACT_PHONE, height=44,
                           on_click=set_contact_first),
            ]

        items += [
            ft.Divider(height=10, color=COLOR_BORDER),
            ft.Text("Or call now:", weight=ft.FontWeight.W_600, color=COLOR_TEXT),
            app_button(f"Police (SAPS) {SAPS_NUMBER}", icon=ft.Icons.CALL, width=w, height=44,
                       url=f"tel:{SAPS_NUMBER}", kind="danger"),
            app_button("GBV Command Centre 0800 428 428", icon=ft.Icons.CALL, width=w, height=44,
                       url=f"tel:{GBV_NUMBER}", kind="danger"),
        ]

        sos_dialog.content = ft.Column(items, tight=True, width=w, spacing=10)
        sos_dialog.open = True
        page.update()

    # --- Sign out ---
    def close_signout_dialog(e=None):
        signout_dialog.open = False
        page.update()

    def do_sign_out(e):
        signout_dialog.open = False
        account["profile"] = None
        save_profile(None)
        emergency["contact"] = None
        save_contact(None)
        rider["taxi"] = None
        show_welcome()

    signout_dialog = ft.AlertDialog(
        title=heading("Sign out?", size=18),
        content=ft.Text(
            "This removes your account details and emergency contact from this phone. "
            "You can register again at any time.",
            color=COLOR_TEXT_MUTED
        ),
        bgcolor=COLOR_CARD,
        actions=[
            ft.TextButton("Cancel", on_click=close_signout_dialog),
            app_button("Sign out", on_click=do_sign_out, height=40),
        ]
    )
    page.overlay.append(signout_dialog)

    def open_signout_dialog():
        signout_dialog.open = True
        page.update()

    # =====================================================
    # PAGE 1: WELCOME + REGISTER (shown only when nobody is signed in)
    # =====================================================
    def show_welcome():
        page.appbar.actions = []
        w = content_width()
        show(
            heading("Welcome to Siyaya Teksi", size=24),
            ft.Text("Know which taxis are coming, and when they leave.",
                    size=15, color=COLOR_TEXT_MUTED, text_align=ft.TextAlign.CENTER),
            ft.Container(height=6),
            app_button("I'm a Passenger", icon=ft.Icons.PERSON, width=w, height=56,
                       on_click=lambda e: show_register("passenger")),
            app_button("I'm a Driver", icon=ft.Icons.LOCAL_TAXI, width=w, height=56, kind="accent",
                       on_click=lambda e: show_register("driver")),
            ft.Text("You only do this once. The app remembers you on this phone.",
                    size=12, color=COLOR_TEXT_MUTED, text_align=ft.TextAlign.CENTER),
        )

    def show_register(role):
        page.appbar.actions = []
        w = content_width()

        name_field = app_field(label="Your name", width=w)
        phone_field = app_field(
            label="Cell number",
            hint_text="e.g., 082 123 4567",
            keyboard_type=ft.KeyboardType.PHONE,
            width=w
        )
        code_field = app_field(
            label="Driver access code",
            password=True,
            can_reveal_password=True,
            width=w
        )

        def create_account(e):
            name_field.error_text = None
            phone_field.error_text = None
            code_field.error_text = None
            valid = True

            if not (name_field.value or "").strip():
                name_field.error_text = "Enter your name"
                valid = False

            phone = normalize_phone(phone_field.value)
            if phone is None:
                phone_field.error_text = "Enter a SA number, e.g. 082 123 4567"
                valid = False

            # Drivers need the access code, but only this one time
            if role == "driver" and (code_field.value or "").strip() != DRIVER_CODE:
                code_field.error_text = "Wrong code. Only drivers can register as drivers."
                valid = False

            if not valid:
                page.update()
                return

            account["profile"] = {
                "role": role,
                "name": name_field.value.strip(),
                "phone": phone,
                "uid": uuid.uuid4().hex,  # a private random id, used to mark a driver's own trips
            }
            save_profile(account["profile"])
            notify(f"Welcome, {account['profile']['name']}!")
            start()

        fields = [name_field, phone_field]
        if role == "driver":
            fields.append(code_field)

        show(
            heading("Create your driver account" if role == "driver" else "Create your passenger account"),
            card(ft.Column(fields, spacing=12), width=w),
            app_button("Create account", icon=ft.Icons.CHECK, width=w, on_click=create_account),
            ft.TextButton(text="Back", on_click=lambda e: show_welcome()),
        )

    def start():
        """Go straight to the right page if someone is already signed in."""
        profile = account["profile"]
        if profile is None:
            show_welcome()
        elif profile["role"] == "driver":
            show_driver_page()
        else:
            show_passenger_page()

    # =====================================================
    # PAGE 2: PASSENGER PAGE (find taxis, track, share, SOS)
    # =====================================================
    def show_passenger_page():
        page.appbar.actions = [signout_button]
        w = content_width()

        # Container to hold our dynamic taxi cards
        taxi_card_container = ft.Column(spacing=14, width=w)
        sync_note = ft.Text("", size=12, color=COLOR_TEXT_MUTED)

        def build_taxi_list(filter_text=""):
            # The search bar's value can be empty (None) until someone types, so guard against that
            filter_text = (filter_text or "").lower()
            taxi_card_container.controls.clear()
            hidden_full = 0  # counts full taxis we skipped, so we can hint about the switch

            # Taxis with seats come first, full ones last; each group sorted by departure time
            for taxi in sorted(taxis, key=lambda t: (t["seats"] == 0, t["time"])):
                if filter_text not in taxi["route"].lower():
                    continue

                # Old trips and trips that have arrived are finished, so passengers no longer see them
                if taxi["status"] == "Arrived" or not is_recent(taxi):
                    continue

                # Skip full taxis unless the passenger turned the switch on
                if taxi["seats"] == 0 and not show_full_switch.value:
                    hidden_full += 1
                    continue

                seat_color = COLOR_GOOD if taxi["seats"] > 0 else COLOR_FULL
                seat_text = f"{taxi['seats']} seats available" if taxi["seats"] > 0 else "Taxi Full!"

                # Snapshot of the current taxi, so each button uses its own taxi
                current_taxi = taxi

                status_pill = ft.Container(
                    content=ft.Text(taxi["status"], size=12, weight=ft.FontWeight.W_600, color=COLOR_PRIMARY),
                    bgcolor=COLOR_PILL,
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border_radius=20
                )

                taxi_card_container.controls.append(card(
                    ft.Column([
                        heading(taxi["route"], size=16),

                        ft.Row([
                            ft.Icon(ft.Icons.PERSON, color=COLOR_TEXT_MUTED, size=16),
                            ft.Text(taxi["driver"], size=12, color=COLOR_TEXT_MUTED)
                        ]),

                        ft.Divider(height=10, thickness=1, color=COLOR_BORDER),

                        ft.Row([
                            ft.Text(f"Departs {taxi['time']}", weight=ft.FontWeight.W_600, color=COLOR_TEXT),
                            status_pill,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                        ft.Row([
                            ft.Text(seat_text, color=seat_color, weight=ft.FontWeight.W_600, size=14),
                            ft.Row([
                                ft.IconButton(
                                    ft.Icons.SHARE,
                                    icon_color=COLOR_PRIMARY,
                                    tooltip="Share Ride Status",
                                    on_click=lambda e, t=current_taxi: share_ride_status(t)
                                ),
                                app_button("Track", height=40, on_click=lambda e, t=current_taxi: track_taxi(t))
                            ])
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=8),
                    width=w
                ))

            # If nothing matched, say so instead of showing a blank screen
            if not taxi_card_container.controls:
                if hidden_full > 0:
                    message = "No taxis with seats right now. Turn on 'Show full taxis' to see the full ones."
                else:
                    message = "No taxis found for that route yet."
                taxi_card_container.controls.append(ft.Text(message, color=COLOR_TEXT_MUTED))
            page.update()

        def refresh_trips(e=None):
            """Get the latest trips (from the online database, if one is set) and redraw the list."""
            state = refresh_taxis()
            if state == "live":
                sync_note.value = "Live trips. Updated " + datetime.datetime.now().strftime("%H:%M")
            elif state == "offline":
                sync_note.value = "Can't reach the online database. Showing the last saved trips."
            else:
                sync_note.value = "Trips on this phone only (no online database set up)."
            build_taxi_list(search_bar.value)

        search_bar = app_field(
            label="Search your route (e.g., Soweto, Umlazi...)",
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: build_taxi_list(search_bar.value),
            width=w - 34  # leaves room for the card's padding
        )

        # Off by default: passengers only see taxis with seats unless they turn this on
        show_full_switch = ft.Switch(
            label="Show full taxis",
            value=False,
            active_color=COLOR_PRIMARY,
            on_change=lambda e: build_taxi_list(search_bar.value)
        )

        # --- Emergency contact summary (under the SOS button) ---
        contact_text = ft.Text("", size=12, color=COLOR_TEXT_MUTED)
        contact_button = ft.TextButton(
            text="Set contact",
            on_click=lambda e: open_contact_dialog(on_saved=update_contact_row)
        )

        def update_contact_row():
            contact = emergency["contact"]
            if contact:
                contact_text.value = f"Emergency contact: {contact['name']}"
                contact_button.text = "Change"
            else:
                contact_text.value = "No emergency contact set"
                contact_button.text = "Set contact"
            page.update()

        header_items = [
            ft.Column([
                heading(f"Hi, {account['profile']['name']}"),
                ft.Text("Find a taxi on your route", size=13, color=COLOR_TEXT_MUTED),
            ], spacing=0)
        ]
        if DATABASE_URL:
            header_items.append(ft.IconButton(
                ft.Icons.REFRESH, icon_color=COLOR_PRIMARY, tooltip="Refresh trips", on_click=refresh_trips
            ))

        show(
            ft.Row(header_items, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=w),
            app_button("🚨 SOS: Get help now", kind="danger", width=w, height=52,
                       on_click=lambda e: open_sos_dialog(on_contact_saved=update_contact_row)),
            ft.Row([contact_text, contact_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=w),
            card(ft.Column([search_bar, show_full_switch], spacing=8), width=w),
            ft.Row([heading("Taxis on your route", size=16), sync_note],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=w, wrap=True),
            taxi_card_container,
        )

        build_taxi_list()   # show the saved trips straight away
        update_contact_row()
        refresh_trips()     # then fetch the latest

    # =====================================================
    # PAGE 3: DRIVER PAGE (post trips, update status & seats)
    # =====================================================
    def show_driver_page():
        # Only a signed-in driver can see this page
        profile = account["profile"]
        if not profile or profile["role"] != "driver":
            show_welcome()
            return

        page.appbar.actions = [signout_button]
        w = content_width()
        half = (w - 32 - 16) // 2  # two fields side by side inside a card

        # --- Fields: post a new trip ---
        driver_name = app_field(label="Driver name", value=profile["name"], width=w - 32)
        route_field = app_field(
            label="Route",
            hint_text="e.g., Soweto to Johannesburg CBD",
            width=w - 32
        )
        time_field = app_field(label="Departure (HH:MM)", hint_text="07:30", width=half)
        seats_field = app_field(
            label="Seats available",
            hint_text="0 to 15",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=half
        )

        # --- Fields: update one of your trips ---
        trip_select = app_dropdown(label="Choose your trip", width=w - 32)
        status_select = app_dropdown(
            label="New status (optional)",
            options=[ft.dropdown.Option(s) for s in STATUS_STEPS],
            width=w - 32
        )
        seats_update = app_field(
            label="Seats left (optional)",
            hint_text="0 to 15",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=w - 32
        )

        def refresh_trip_options():
            # Only this driver's own trips can be changed (key = the trip's id)
            mine = [t for t in taxis if t.get("owner") == profile["uid"]]
            trip_select.options = [
                ft.dropdown.Option(
                    key=str(t["id"]),
                    text=f"{t['time']} | {t['route']}"
                )
                for t in sorted(mine, key=lambda t: t["time"])
            ]

        def sent_message(result, text):
            """Say what happened, including when there was no internet."""
            if result == "pending":
                return "Saved on this phone, but the online database can't be reached. It will be sent when you're back online."
            return text

        def add_trip(e):
            # Clear any old error messages first
            for field in (driver_name, route_field, time_field, seats_field):
                field.error_text = None

            valid = True

            if not driver_name.value or not driver_name.value.strip():
                driver_name.error_text = "Enter your name"
                valid = False

            if not route_field.value or not route_field.value.strip():
                route_field.error_text = "Enter the route"
                valid = False

            # Check the time is a real HH:MM time (e.g. 07:30 or 7:30)
            try:
                parsed_time = datetime.datetime.strptime((time_field.value or "").strip(), "%H:%M")
            except ValueError:
                time_field.error_text = "Use HH:MM, e.g. 07:30"
                valid = False

            # Check seats is a whole number from 0 to 15
            try:
                seats = int(seats_field.value)
                if not 0 <= seats <= 15:
                    raise ValueError
            except (TypeError, ValueError):
                seats_field.error_text = "Enter a number from 0 to 15"
                valid = False

            # If anything is wrong, show the errors and stop
            if not valid:
                page.update()
                return

            new_trip = {
                "id": uuid.uuid4().hex[:10],       # unique, even if many drivers post at once
                "owner": profile["uid"],          # marks this as the driver's own trip
                "driver": driver_name.value.strip(),
                "route": route_field.value.strip(),
                "time": parsed_time.strftime("%H:%M"),  # keeps times like 07:30 consistent
                "seats": seats,
                "status": "Loading at Rank",
                "posted_at": int(time.time()),
            }
            taxis.append(new_trip)

            # A trip posted with 0 seats is already full, so it can't be "Loading at Rank"
            auto_changed = fix_full_taxi_status(new_trip)
            result = publish_trip(new_trip)  # saves here, and online if a database is set

            # Empty the form for the next trip
            driver_name.value = profile["name"]
            route_field.value = ""
            time_field.value = ""
            seats_field.value = ""

            refresh_trip_options()  # so the new trip appears in the update dropdown
            page.update()
            if auto_changed:
                notify(sent_message(result, "Trip posted. It has 0 seats, so its status was set to Departed Rank."))
            elif result == "local":
                notify("Trip saved on this phone.")
            else:
                notify(sent_message(result, "Trip posted! Passengers can now see it."))

        def update_trip(e):
            trip_select.error_text = None
            status_select.error_text = None
            seats_update.error_text = None

            valid = True

            if not trip_select.value:
                trip_select.error_text = "Choose a trip"
                valid = False

            # Seats is optional, but if something is typed it must be 0 to 15
            seats_text = (seats_update.value or "").strip()
            new_seats = None
            if seats_text:
                try:
                    new_seats = int(seats_text)
                    if not 0 <= new_seats <= 15:
                        raise ValueError
                except ValueError:
                    seats_update.error_text = "Enter a number from 0 to 15"
                    valid = False

            # The driver must change at least one thing
            if not status_select.value and not seats_text:
                status_select.error_text = "Choose a status or enter seats left"
                valid = False

            if not valid:
                page.update()
                return

            # Find the chosen trip by its id (only the driver's own trips can be chosen)
            auto_changed = False
            result = "local"
            for t in taxis:
                if str(t["id"]) == trip_select.value and t.get("owner") == profile["uid"]:
                    if status_select.value:
                        t["status"] = status_select.value
                    if new_seats is not None:
                        t["seats"] = new_seats
                    # A full taxi can't still be loading, so move it on automatically
                    auto_changed = fix_full_taxi_status(t)
                    result = publish_trip(t)  # saves here, and online if a database is set
                    break

            # Reset the update fields for next time
            status_select.value = None
            seats_update.value = ""

            page.update()
            if auto_changed:
                notify(sent_message(result, "Taxi is full, so its status was changed to Departed Rank."))
            elif result == "local":
                notify("Trip updated on this phone.")
            else:
                notify(sent_message(result, "Trip updated! Passengers will see the changes."))

        post_form = card(
            ft.Column([
                heading("Post your trip", size=16),
                driver_name,
                route_field,
                ft.Row([time_field, seats_field], spacing=16),
                app_button("Post trip", icon=ft.Icons.ADD_ROAD, width=w - 32, on_click=add_trip),
            ], spacing=12),
            width=w
        )

        update_form = card(
            ft.Column([
                heading("Update a trip", size=16),
                trip_select,
                status_select,
                seats_update,
                app_button("Update trip", icon=ft.Icons.UPDATE, width=w - 32, on_click=update_trip),
            ], spacing=12),
            width=w
        )

        where_note = (
            "Trips you post are shared online with passengers."
            if DATABASE_URL else
            "Trips are saved on this phone only (no online database set up)."
        )

        show(
            heading(f"Driver: {profile['name']}"),
            ft.Text("Post your trip, then keep its status and seats up to date.", size=14, color=COLOR_TEXT_MUTED),
            ft.Text(where_note, size=12, color=COLOR_TEXT_MUTED),
            post_form,
            update_form,
        )

        refresh_trip_options()
        page.update()
        # Send any trips that couldn't be sent earlier, and refresh from the online database
        if refresh_taxis() == "live":
            refresh_trip_options()
            page.update()

    # If someone is already signed in, go straight to their page
    start()

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
assets = "assets" if os.path.isdir(ASSETS_DIR) else None

if hasattr(ft, "run"):
    ft.run(main, assets_dir=assets)            # newer Flet versions
else:
    ft.app(target=main, assets_dir=assets)     # older Flet versions

  
