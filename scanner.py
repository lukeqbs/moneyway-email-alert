import json, os, re, smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

GMAIL_USER = os.environ.get("GMAIL_USER", "").strip()
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
ODBIORCA = os.environ.get("ODBIORCA_EMAIL", "").strip()

PROG_SKOKU, PROG_PROC = 1000.0, 85.0
PROG_PROC_WYSOKI_KURS, PROG_KURS, PROG_SKOKU_WYSOKI_KURS = 75.0, 4.5, 250.0

RYNKI = {
    "1X2 (Pre)": ("https://arbworld.net", ["1", "X", "2"]),
    "1X2 HT (Pre)": ("https://arbworld.net", ["1 HT", "X HT", "2 HT"]),
    "O/U 1.5 (Pre)": ("https://arbworld.net", ["U 1.5", "O 1.5"]),
    "O/U 2.5 (Pre)": ("https://arbworld.net", ["U 2.5", "O 2.5"]),
    "O/U 3.5 (Pre)": ("https://arbworld.net", ["U 3.5", "O 3.5"]),
    "1X2 (LIVE)": ("https://arbworld.net", ["1 LIVE", "X LIVE", "2 LIVE"]),
    "O/U 2.5 (LIVE)": ("https://arbworld.net", ["U 2.5 LIVE", "O 2.5 LIVE"]),
}

WYKLUCZONE = [
    "english", "england", "premier league", "championship", "league one", "league two", "national league", "fa cup", "efl", "wsl",
    "spanish", "spain", "la liga", "segunda", "primera federacion", "copa del rey",
    "italian", "italy", "serie a", "serie b", "serie c", "coppa italia",
    "german", "germany", "bundesliga", "2. bundesliga", "3. liga", "dfb",
    "french", "france", "ligue 1", "ligue 2", "national", "coupe de france",
    "portuguese", "portugal", "primeira", "liga portugal",
    "dutch", "netherlands", "eredivisie", "eerste",
    "belgian", "belgium", "jupiler", "challenger pro",
    "scottish", "scotland", "premiership",
    "turkish", "turkey", "super lig", "1. lig",
    "greek", "greece", "super league",
    "polish", "poland", "ekstraklasa", "i liga", "2 liga",
    "russian", "russia", "ukrainian", "ukraine",
    "austrian", "austria", "swiss", "switzerland",
    "danish", "denmark", "superliga",
    "swedish", "sweden", "allsvenskan", "superettan",
    "norwegian", "norway", "eliteserien", "obos",
    "finnish", "finland", "veikkausliiga",
    "czech", "slovak", "hungarian", "romanian", "bulgarian", "serbian", "croatian", "slovenian", "bosnian", "albanian", "macedonian", "montenegrin",
    "cypriot", "israeli", "kazakh", "azerbaijani", "georgian", "armenian", "estonian", "latvian", "lithuanian",
    "irish", "ireland", "welsh", "wales", "icelandic", "maltese", "luxembourg", "faroe", "gibraltar", "andorra", "san marino",
    "uefa", "champions league", "europa league", "conference league", "nations league", "euro ",
    "us mls", "major league soccer", "mexican liga mx", "saudi pro league", "j1 league", "a-league men", "k league 1", "chinese super league",
    "brasileiro serie a", "argentine primera division", "liga profesional",
    "world cup", "copa america", "asian cup", "africa cup", "copa libertadores", "afc champions", "caf champions"
]

DUZE_SPOZA = ["argentin", "brazil", "australian", "australia", "japanese", "japan", "usa", "united states", "mexic", "korean", "korea", "saudi"]
NISZOWE_OK = ["b", "c", "d", "2", "3", "4", "primera nacional", "metropolitana", "federal", "usl", "mls next", "expansion", "paulista", "carioca", "gaucho", "mineiro", "copinha", "npl", "state", "j2", "j3", "k league 2", "division 1", "cup", "copa", "trophy", "friendly", "friendlies", "towarzyskie", "women", "(w)", "femenina", "u20", "u21", "u23", "u19", "reserves"]

def czy_niszowa(txt):
    t = txt.lower()
    if any(k in t for k in DUZE_SPOZA):
        if any(x in t for x in ["us mls", "major league soccer", "liga mx", "saudi pro league", "j1 league", "a-league men", "k league 1", "brasileiro serie a"]):
            return False
        return any(d in t for d in NISZOWE_OK)
    return not any(w in t for w in WYKLUCZONE)

def wyslij_mail(temat, tresc):
    if not (GMAIL_USER and GMAIL_PASS and ODBIORCA):
        return
    msg = MIMEText(tresc, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = temat, GMAIL_USER, ODBIORCA
    try:
        with smtplib.SMTP_SSL("://gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(GMAIL_USER, ODBIORCA, msg.as_string())
        print("[EMAIL OK]")
    except Exception as e:
        print(f"[EMAIL ERR] {e}")

def main():
    stan = json.load(open("historia_kwot.json", encoding="utf-8")) if os.path.exists("historia_kwot.json") else {}
    nowy_stan, app_lista, mail_lista = {}, [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36").new_page()

        for rynek, (url, opcje) in RYNKI.items():
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_selector("table tr", state="attached", timeout=15000)
                page.wait_for_timeout(1500)
                wiersze = page.query_selector_all("table tr")
            except Exception as e:
                print(f"[ERR {rynek}] {e}")
                continue

            for row in wiersze:
                cols = [k.inner_text().strip().replace("\n", " ") for k in row.query_selector_all("td")]
                idx0 = next((i for i, t in enumerate(cols) if "%" in t), None)
                if not idx0 or len(cols) < len(opcje) + 1:
                    continue

                mecz = " | ".join(cols[:idx0]).strip()
                if not mecz or not czy_niszowa(mecz):
                    continue

                for i, opcja in enumerate(opcje):
                    if idx0 + i >= len(cols):
                        break
                    txt = cols[idx0 + i]
                    pm = re.search(r"(\d+(?:\.\d+)?)\s*%", txt)
                    km = re.search(r"[$£€]\s*([\d,]+(?:\.\d+)?)", txt)
                    cm = re.search(r"\b(\d+\.\d{1,2})\b", txt)

                    if not (pm and km):
                        continue

                    proc = float(pm.group(1))
                    kwota = float(km.group(1).replace(",", ""))
                    kurs = cm.group(1) if cm else "?"
                    kurs_val = float(kurs) if cm else 0.0

                    if kwota <= 0:
                        continue

                    klucz = f"{rynek} :: {mecz} :: {opcja}"
                    prev = stan.get(klucz, 0.0)
                    skok = kwota - prev
                    nowy_stan[klucz] = kwota

                    warunek_skok = (proc >= PROG_PROC and skok >= PROG_SKOKU)
                    warunek_kurs = (proc > PROG_PROC_WYSOKI_KURS and kurs_val > PROG_KURS and skok > PROG_SKOKU_WYSOKI_KURS)
                    alert = warunek_skok or warunek_kurs

                    if proc >= 50.0:
                        app_lista.append({
                            "rynek": rynek,
                            "mecz": mecz,
                            "typ": opcja,
                            "kurs": kurs,
                            "procent": proc,
                            "kwota": kwota,
                            "przyrost": skok,
                            "alert": alert
                        })

                    if alert:
                        nowy_tag = " [NOWY]" if prev == 0.0 else ""
                        powod = "🔥 WYSOKI KURS + SKOK" if (warunek_kurs and not warunek_skok) else "💰 DUŻY SKOK KWOTY"
                        mail_lista.append(f"[{powod}{nowy_tag}]\nRynek: {rynek}\nMecz: {mecz}\nTyp: {opcja} (Kurs: {kurs})\nUdział: {proc}% | Kwota: £{kwota:,.0f} (+£{skok:,.0f})")

        browser.close()

    app_lista.sort(key=lambda x: (x["alert"], x["procent"], x["kwota"]), reverse=True)
    json.dump(nowy_stan, open("historia_kwot.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump({
        "aktualizacja_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "liczba_zdarzen": len(app_lista),
        "zdarzenia": app_lista
    }, open("dane.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"Zapisano {len(app_lista)} zdarzeń.")
    if mail_lista:
        tresc = "\n\n" + ("=" * 30 + "\n\n").join(mail_lista) + "\n\nAplikacja: https://github.io"
        wyslij_mail(f"🚨 Moneyway Alert: {len(mail_lista)} zdarzeń!", tresc)

if __name__ == "__main__":
    main()
