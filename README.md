# Siyaya-Teksi


**A simple schedule for South African minibus taxis.**

Taxis have no timetable. Passengers wait at the roadside, often alone, never sure when the next taxi is coming or whether it will have space. Many can't afford e-hailing, so waiting is the only option.

Siyaya Teksi lets drivers post their trips and lets passengers see which taxis are coming, how many seats are left, and where each trip is. Less guessing means less time waiting alone, which is where safety starts.

Built for a hackathon on **safer communities and gender-based violence (GBV) in South Africa**, using Python and the [Flet](https://flet.dev) framework.

## Features

**For passengers**
- Register once; the app remembers you on your phone
- Search for your route and see taxis sorted by departure time
- See seats left and trip status: *Loading at Rank → Departed Rank → En Route → Arrived*
- Full taxis are hidden by default, with a switch to show them
- Share your ride details with family over WhatsApp
- Set an **emergency contact**. The **SOS** button opens a WhatsApp or SMS message to them, ready to send, and has one-tap call buttons for the police (10111) and the GBV Command Centre (0800 428 428)

**For drivers**
- Register once with a driver access code; the app remembers you, so there's no code at every sign-in
- Post a trip: route, departure time, seats
- Update the status and seats left of **your own** trips
- A full taxi automatically moves on from "Loading at Rank"

## Run it on a computer

1. Install Python 3.10 or newer
2. `pip install flet certifi`
3. `python main.py` (or `flet run`)

The demo driver access code is `TAXI2026`. It is set at the top of `main.py` (`DRIVER_CODE`) and is a stand-in for real driver verification.

### Fonts (optional)

The app is designed for the free font Poppins. Download it from Google Fonts and put `Poppins-Regular.ttf` and `Poppins-SemiBold.ttf` in `assets/fonts`. Without them the app uses the normal font.

## Two modes

**This phone only (default).** Leave `DATABASE_URL` empty in `main.py`. Trips are saved on the device, and four sample trips are included.

**Shared online.** Paste a [Firebase Realtime Database](https://firebase.google.com/docs/database) address into `DATABASE_URL`. Drivers' trips then appear on passengers' phones:
- Passengers see the latest trips when they open the app and when they tap refresh
- A driver can only change their own trips
- Phone numbers are never sent to the database
- If there is no internet, a driver's trip is kept on the phone and sent when they are back online
- Trips older than 12 hours are hidden from passengers

## Build the Android app (APK)

1. Install `flet` and the Android build tools (see the [Flet Android guide](https://docs.flet.dev/publish/android))
2. In this folder, run `flet build apk`
3. Your APK appears in the `build/apk` folder. Copy it to an Android phone and install it (you may need to allow installs from unknown sources)

## Where data is stored

On the device: `trips.json`, `profile.json` and `contact.json`. In shared mode, trips are also stored in the online database. The account and emergency contact never leave the phone.

## Honest limits of this prototype

- **Accounts are local and unverified.** Registering saves a name and number on the phone. Nothing verifies phone numbers or drivers' licences.
- **The online database is open.** In Firebase's test mode, anyone with the address can read and change trips. A real launch needs sign-in checks and proper security rules.
- **Tracking is not GPS.** Drivers update a trip's status by hand.
- **SOS doesn't send automatically.** It opens a message for the passenger to send. It doesn't share location yet and doesn't alert other app users.
- **Lists refresh on opening and on tap**, not continuously.

## Roadmap

- Driver verification (licence or taxi association membership) and phone number checks
- Proper security rules and sign-in for the database
- Automatic refresh and push notifications
- Location sharing in SOS, and opt-in alerts to nearby trusted users
- GPS-based tracking and predictions of how quickly taxis on a route fill up
- Low-data and SMS options

## Helplines

- **GBV Command Centre:** 0800 428 428 (free, 24 hours)
- **Police (SAPS):** 10111h African taxi application focused on transport information and commuter safety, built with Python and Flet.
