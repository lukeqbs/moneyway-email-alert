:import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# ================= KONFIGURACJA UŻYTKOWNIKA =================
GMAIL_USER = os.environ.get("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
ODBIORCA_EMAIL = os.environ.get("ODBIORCA_EMAIL", "").strip()

PROG_SKOKU = 1000.0        # Minimalny przyrost kwoty między sprawdzeniami
PROG_UDZIALU_PROC = 85.0   # Minimalny udział w rynku (%)

RYNKI_URL = {
    "1X2 Cały Mecz (Pre)": (
        "https://arbworld.net/moneyway/football/1x2",
        ["1", "X", "2"],
    ),
    "1X2 1. Połowa (Pre)": (
        "https://arbworld.net/moneyway/football/half-time",
        ["1 (1. połowa)", "X (1. połowa)", "2 (1. połowa)"],
    ),
    "Over/Under 1.5 (Pre)": (
        "https://arbworld.net/moneyway/football/over-under-1-5",
        ["Under 1.5", "Over 1.5"],
    ),
    "Over/Under 2.5 (Pre)": (
        "https://arbworld.net/moneyway/football/over-under-2-5",
        ["Under 2.5", "Over 2.5"],
    ),
    "Over/Under 3.5 (Pre)": (
        "https://arbworld.net/moneyway/football/over-under-3-5",
        ["Under 3.5", "Over 3.5"],
    ),
    "1X2 Cały Mecz (LIVE)": (
        "https://arbworld.net/moneyway-live/football/1x2",
        ["1 (LIVE)", "X (LIVE)", "2 (LIVE)"],
    ),
    "Over/Under 2.5 (LIVE)": (
        "https://arbworld.net/moneyway-live/football/over-under-2-5",
        ["Under 2.5 (LIVE)", "Over 2.5 (LIVE)"],
    ),
}

PLIK_STANU = "historia_kwot.json"

# ================= FILTROWANIE LIG =================
WYKLUCZONE_EUROPA_I_TOP = [
    "english",
    "england",
    "premier league",
    "championship",
    "league one",
    "league two",
    "national league",
    "fa cup",
    "efl",
    "wsl",
    "spanish",
    "spain",
    "la liga",
    "segunda",
    "primera federacion",
    "copa del rey",
    "italian",
    "italy",
    "serie a",
    "serie b",
    "serie c",
    "coppa italia",
    "german",
    "germany",
    "bundesliga",
    "2. bundesliga",
    "3. liga",
    "dfb",
    "french",
    "france",
    "ligue 1",
    "ligue 2",
    "national",
    "coupe de france",
    "portuguese",
    "portugal",
    "primeira",
    "liga portugal",
    "dutch",
    "netherlands",
    "eredivisie",
    "eerste",
    "belgian",
    "belgium",
    "jupiler",
    "challenger pro",
    "scottish",
    "scotland",
    "premiership",
    "turkish",
    "turkey",
    "super lig",
    "1. lig",
    "greek",
    "greece",
    "super league",
    "polish",
    "poland",
    "ekstraklasa",
    "i liga",
    "2 liga",
    "russian",
    "russia",
    "ukrainian",
    "ukraine",
    "austrian",
    "austria",
    "swiss",
    "switzerland",
    "danish",
    "denmark",
    "superliga",
    "swedish",
    "sweden",
    "allsvenskan",
    "superettan",
    "norwegian",
    "norway",
    "eliteserien",
    "obos",
    "finnish",
    "finland",
    "veikkausliiga",
    "czech",
    "slovak",
    "hungarian",
    "romanian",
    "bulgarian",
    "serbian",
    "croatian",
    "slovenian",
    "bosnian",
    "albanian",
    "macedonian",
    "montenegrin",
    "cypriot",
    "israeli",
    "kazakh",
    "azerbaijani",
    "georgian",
    "armenian",
    "estonian",
    "latvian",
    "lithuanian",
    "irish",
    "ireland",
    "welsh",
    "wales",
    "icelandic",
    "maltese",
    "luxembourg",
    "faroe",
    "gibraltar",
    "andorra",
    "san marino",
    "uefa",
    "champions league",
    "europa league",
    "conference league",
    "nations league",
    "euro ",
    "us mls",
    "major league soccer",
    "mexican liga mx",
    "saudi pro league",
    "j1 league",
    "a-league men",
    "k league 1",
    "chinese super league",
    "brasileiro serie a",
    "argentine primera division",
    "liga profesional",
    "world cup",
    "copa america",
    "asian cup",
    "africa cup",
    "copa libertadores",
    "afc champions",
    "caf champions",
]

DUZE_KRAJE_SPOZA_EU = [
    "argentin",
    "brazil",
    "australian",
    "australia",
    "japanese",
    "japan",
    "usa",
    "united states",
    "mexic",
    "korean",
    "korea",
    "saudi",
]

DOZWOLONE_NISZOWE_W_DUZYCH = [
    "b",
    "c",
    "d",
    "2",
    "3",
    "4",
    "primera nacional",
    "metropolitana",
    "federal",
    "usl",
    "mls next",
    "expansion",
    "paulista",
    "carioca",
    "gaucho",
    "mineiro",
    "copinha",
    "npl",
    "state",
    "j2",
    "j3",
    "k league 2",
    "division 1",
    "cup",
    "copa",
    "trophy",
    "friendly",
    "friendlies",
    "towarzyskie",
    "women",
    "(w)",
    "femenina",
    "u20",
    "u21",
    "u23",
    "u19",
    "reserves",
]


def czy_liga_niszowa(tekst_meczu: str) -> bool:
  t = tekst_meczu.lower()
  if any(kraj in t for kraj in DUZE_KRAJE_SPOZA_EU):
    if any(
        top in t
        for top in [
            "us mls",
            "major league soccer",
            "liga mx",
            "saudi pro league",
            "j1 league",
            "a-league men",
            "k league 1",
            "brasileiro serie a",
        ]
    ):
      return False
    return any(dozw in t for dozw in DOZWOLONE_NISZOWE_W_DUZYCH)
  if any(wykl in t for wykl in WYKLUCZONE_EUROPA_I_TOP):
    return False
  return True


def wyslij_gmail(temat: str, tresc: str):
  if not GMAIL_USER or not GMAIL_APP_PASSWORD or not ODBIORCA_EMAIL:
    print("[BŁĄD] Brak konfiguracji e-mail w sekretach GitHub!")
    return
  msg = MIMEText(tresc, "plain", "utf-8")
  msg["Subject"] = temat
  msg["From"] = GMAIL_USER
  msg["To"] = ODBIORCA_EMAIL
  try:
    host = ".".join(["smtp", "gmail", "com"])
    with smtplib.SMTP_SSL(host, 465) as server:
      server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
      server.sendmail(GMAIL_USER, ODBIORCA_EMAIL, msg.as_string())
    print(f"[EMAIL WYSŁANY] {temat}")
  except Exception as e:
    print(f"[BŁĄD EMAIL] {e}")


def wczytaj_stan():
  if os.path.exists(PLIK_STANU):
    try:
      with open(PLIK_STANU, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {}


def zapisz_stan(stan):
  with open(PLIK_STANU, "w", encoding="utf-8") as f:
    json.dump(stan, f, indent=2, ensure_ascii=False)


def parsuj_komorke(tekst: str):
  procent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", tekst)
  kwota_match = re.search(r"[$£€]\s*([\d,]+(?:\.\d+)?)", tekst)
  kurs_match = re.search(r"\b(\d+\.\d{1,2})\b", tekst)

  if procent_match and kwota_match:
    procent = float(procent_match.group(1))
    kwota = float(kwota_match.group(1).replace(",", ""))
    kurs = kurs_match.group(1) if kurs_match else "?"
    return kurs, procent, kwota
  return None, 0.0, 0.0


def sprawdz_rynki():
  stan = wczytaj_stan()
  nowy_stan = stan.copy()
  znalezione_alerty = []

  with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True, args=["--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
    )
    page = context.new_page()

    for nazwa_rynku, (url, opcje) in RYNKI_URL.items():
      try:
        print(f"--- Otwieranie: {nazwa_rynku} ({url}) ---")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        # POPRAWKA: state="attached" omija ukryte wiersze nagłówka, które powodowały Timeout
        page.wait_for_selector("table tr", state="attached", timeout=15000)
        page.wait_for_timeout(2000)

        wiersze = page.query_selector_all("table tr")
        print(f"Znaleziono wierszy w tabeli: {len(wiersze)}")

        zapisane_w_rynku = 0
        for row in wiersze:
          kolumny = row.query_selector_all("td")
          if len(kolumny) < len(opcje) + 1:
            continue

          teksty_kolumn = [
              k.inner_text().strip().replace("\n", " ") for k in kolumny
          ]

          start_idx = next(
              (i for i, t in enumerate(teksty_kolumn) if "%" in t), None
          )
          if start_idx is None or start_idx == 0:
            continue

          info_meczu = " | ".join(teksty_kolumn[:start_idx]).strip()
          if not info_meczu or not czy_liga_niszowa(info_meczu):
            continue

          for idx, nazwa_opcji in enumerate(opcje):
            col_idx = start_idx + idx
            if col_idx >= len(teksty_kolumn):
              break

            kurs, procent, kwota = parsuj_komorke(teksty_kolumn[col_idx])
            if kurs is None:
              continue

            klucz = f"{nazwa_rynku} :: {info_meczu} :: {nazwa_opcji}"
            poprzednia_kwota = stan.get(klucz, 0.0)
            przyrost = kwota - poprzednia_kwota

            nowy_stan[klucz] = kwota
            zapisane_w_rynku += 1

            if (
                procent >= PROG_UDZIALU_PROC
                and przyrost >= PROG_SKOKU
                and poprzednia_kwota > 0
            ):
              alert = (
                  f"Rynek: {nazwa_rynku}\nMecz: {info_meczu}\nTyp:"
                  f" {nazwa_opcji} (Kurs: {kurs})\nUdział: {procent}% | Kwota:"
                  f" {kwota:,.0f} (+{przyrost:,.0f})"
              )
              znalezione_alerty.append(alert)
              print(f"[ALERT] {info_meczu} -> {nazwa_opcji} (+{przyrost})")

        print(f"Przetworzono pozycji niszowych: {zapisane_w_rynku}")

      except Exception as e:
        print(f"[BŁĄD POBIERANIA {nazwa_rynku}] {e}")

    browser.close()

  zapisz_stan(nowy_stan)

  if znalezione_alerty:
    temat = f"🚨 Moneyway Alert: wykryto {len(znalezione_alerty)} skok(ów)!"
    tresc = "\n\n" + ("=" * 40 + "\n\n").join(znalezione_alerty)
    wyslij_gmail(temat, tresc)
  else: 
      print("Brak nowych skoków spełniających kryteria w tym cyklu.")

  if len(nowy_stan) > 2500:
    klucze = list(nowy_stan.keys())[-2500:]
    nowy_stan = {k: nowy_stan[k] for k in klucze}

  zapisz_stan(nowy_stan)


if __name__ == "__main__":
  sprawdz_rynki()
