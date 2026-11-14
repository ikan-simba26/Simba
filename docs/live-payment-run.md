# The real payment run — Readings, Rs 500 or less

*For Raham, written 2026-11-14. One run, with you at the keyboard. SIMBA does everything up to
the payment page; the payment itself is yours, on the real page.*

**Why Readings.** readings.com.pk (a Lahore bookshop): robots.txt `Allow: /`; its terms allow
"personal use"; it takes card, JazzCash, bank transfer and cash on delivery. Shipping is a flat
**Rs 150**, so a book of **Rs 350 or less** keeps the total at **Rs 500 or less**. Daraz and
foodpanda are out (their robots.txt disallow checkout).

## Before

1. **Make a Readings account yourself** (Register on the site, or "Log in with Google"). SIMBA
   does not create accounts.
2. Pick a book at Rs 350 or less, and note its title.
3. Pull `main`, then start SIMBA with the AI planner:

        $env:SIMBA_USE_HARDCODED_PLAN = "0"
        .\run.ps1

   (or the installed app, with your keys in `%APPDATA%\SIMBA\.env`).

## The run

Type, on the home screen: **"Buy the book <title> on readings.com.pk and pay online"** — or press
Readings → "Buy a book" and say the title when asked.

What should happen, and what you do:

| SIMBA | You |
|---|---|
| Searches, opens the book, adds it to the cart | watch; press "Pause" if anything looks wrong |
| **Final screen**: "I'll press Checkout …" | **Do it** |
| Sign-in page: asks for your email and password in its own field | type them in SIMBA's field (the AI never sees them) |
| Address, phone: asks for each in its own field | type them (never sent to the AI; blanked out of every prompt) |
| Chooses the payment method the page offers | if it asks which, say card or JazzCash |
| **Final screen**: "I'll press Place order …", with the amount the page states | check the total is ≤ Rs 500 → **Do it** |
| **Hands the payment page to you**: "Your turn: pay on the page below" | pay on the real page yourself, then press **I've finished** |
| Reads the page and says what it shows ("The website says: …") | check it, and the email Readings sends |

If SIMBA stops anywhere ("I'm stuck"), nothing after that point happened. Note where, and tell me.

## Afterwards

Write down for EVALUATION.md: the time, the total paid, the order number, how many steps and
which provider worked each one out (shown under each step), and anything that went wrong.
