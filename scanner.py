import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from curl_cffi import requests

# ================= KONFIGURACJA UŻYTKOWNIKA =================
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ODBIORCA_EMAIL = os.environ.get("ODBIORCA_EMAIL", "")

PROG_SKOKU = 1000.0        # Minimalny przyrost kwoty między sprawdzeniami
PROG_UDZIALU_PROC = 85.0   # Minimalny udział w rynku (%)

RYNKI = {
    "1X2 Cały Mecz (Pre)": (
        "https://arbworld.net",
        ["1", "X", "2"],
    ),
    "1X2 1. Połowa (Pre)": (
        "https://arbworld.net",
        ["1 (1. połowa)", "X (1. połowa)", "2 (1. połowa)"],
    ),
    "Over/Under 2.5 (Pre)": (
        "https://arbworld.net",
        ["Under 2.5", "Over 2.5"],
    ),
    "1X2 Cały Mecz (LIVE)": (
        "https://arbworld.net",
        ["1 (LIVE)", "X (LIVE)", "2 (LIVE)"],
    ),
    "Over/Under 2.5 (LIVE)": (
        "https://arbworld.net",
        ["Under 2.5 (LIVE)", "Over 2.5 (LIVE)"],
    ),
}

PLIK_STANU = "historia_kwot.json"

# ================= FILTROWANIE LIG =================
# Odrzucamy Europę oraz topowe rozgrywki światowe
WYKLUCZONE_EUROPA_I_TOP = [
    # Europa - kraje i ligi
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
    # Top 25 lig spoza Europy (najwyższe klasy rozgrywkowe)
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
]

# Duże kraje spoza Europy, z których interesują nas TYLKO niższe ligi, puchary, rezerwy lub kobiety
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

  # 1. Jeśli to duży kraj spoza Europy, przepuść tylko niższe ligi / puchary / rezerwy / kobiety
  if any(kraj in t for kraj in DUZE_KRAJE_SPOZA_EU):
    # Upewnij się, że nie jest to najwyższa liga mimo dopasowania słowa
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

  # 2. Odrzuć Europę i rozgrywki z czarnej listy
  if any(wykl in t for wykl in WYKLUCZONE_EUROPA_I_TOP):
    return False

  # 3. Pozostałe ligi ze świata (Azja, Afryka, Ameryka Płd./Środkowa, Oceania) przepuszczamy
  return True


def wyslij_gmail(temat: str, tresc: str):
  if not GMAIL_USER or not GMAIL_APP_PASSWORD or not ODBIORCA_EMAIL:
    print(
        "[BŁĄD] Brak konfiguracji e-mail w sekretach GitHub (GMAIL_USER /"
        " GMAIL_APP_PASSWORD / ODBIORCA_EMAIL)!"
    )
    return

  msg = MIMEText(tresc, "plain", "utf-8")
  msg["Subject"] = temat
  msg["From"] = GMAIL_USER
  msg["To"] = ODBIORCA_EMAIL

  try:
    with smtplib.SMTP_SSL("://gmail.com", 465) as server:
      server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
      server.sendmail(GMAIL_USER, ODBIORCA_EMAIL, msg.as_string())
    print(f"[EMAIL WYSŁANY] {temat}")
  except Exception as e:
    print(f"[BŁĄD EMAIL] {e}")


def wczytaj_stan():
  if os.path.exists(PLIK_STANU):
    with open(PLIK_STANU, "r", encoding="utf-8") as f:
      return json.load(f)
  return {}


def zapisz_stan(stan):
  with open(PLIK_STANU, "w", encoding="utf-8") as f:
    json.dump(stan, f, indent=2, ensure_ascii=False)


def parsuj_komorke(tekst: str):
  procent_match = re.search(r"(\d+(?:\.\d+)?)%", tekst)
  # Obsługuje zarówno symbol $, jak i £ w zależności od wersji strony
  kwota_match = re.search(r"[$£]([\d,]+)", tekst)
  kurs_match = re.match(r"^\s*(\d+(?:\.\d+)?)", tekst)

  if procent_match and kwota_match:
    procent = float(procent_match.group(1))
    kwota = float(kwota_match.group(1).replace(",", ""))
    kurs = kurs_match.group(1) if kurs_match else "?"
    return kurs, procent, kwota
  return None, 0.0, 0.0


def sprawdz_rynki():
  stan = wczytaj_stan()
  nowy_stan = stan.copy()  # Zachowuje historię nawet przy chwilowym błędzie jednego rynku
  znalezione_alerty = []

  for nazwa_rynku, (url, opcje) in RYNKI.items():
    try:
      resp = requests.get(url, impersonate="chrome120", timeout=25)
      soup = BeautifulSoup(resp.text, "html.parser")
      wiersze = soup.select("table tr")

      for row in wiersze:
        kolumny = row.find_all("td")
        if len(kolumny) < len(opcje) + 1:
          continue

        info_meczu = kolumny.get_text(" ", strip=True)
        if not czy_liga_niszowa(info_meczu):
          continue

        for idx, typ in enumerate(opcje):
          komorka = kolumny[idx + 1].get_text(" ", strip=True)
          kurs, procent, kwota = parsuj_komorke(komorka)

          if kwota == 0:
            continue

          klucz_id = f"{nazwa_rynku} | {info_meczu} | Typ: {typ}"
          poprzednia_kwota = stan.get(klucz_id, 0.0)
          skok = kwota - poprzednia_kwota

          nowy_stan[klucz_id] = kwota

          # Sprawdzamy czy pozycja była już wcześniej widziana, czy skok >= 1000 i udział >= 85%
          if (
              klucz_id in stan
              and skok >= PROG_SKOKU
              and procent >= PROG_UDZIALU_PROC
          ):
            znalezione_alerty.append(
                f"Mecz / Liga: {info_meczu}\n"
                f"Rynek: {nazwa_rynku}\n"
                f"Pozycja: {typ} (kurs: {kurs})\n"
                f"Skok kwoty: +{skok:,.0f} (z {poprzednia_kwota:,.0f} na"
                f" {kwota:,.0f})\n"
                f"Udział w rynku: {procent}%\n"
                f"Źródło: {url}"
            )

    except Exception as e:
      print(f"[BŁĄD POBIERANIA {nazwa_rynku}] {e}")

  # Wysyłamy jeden zbiorczy e-mail, jeśli wykryto jeden lub więcej skoków w tym cyklu
  if znalezione_alerty:
    temat = (
        f"🚨 Moneyway Alert: Wykryto {len(znalezione_alerty)} skok(i) na"
        " niszowych rynkach!"
    )
    tresc = (
        "Wykryto gwałtowny napływ kapitału na Betfair spełniający Twoje"
        " kryteria:\n\n"
        + ("\n" + "=" * 45 + "\n\n").join(znalezione_alerty)
    )
    wyslij_gmail(temat, tresc)
  else:
    print("Brak nowych skoków spełniających kryteria w tym cyklu.")

  # Ograniczamy rozmiar pliku stanu do ostatnich 2000 wpisów, aby nie rósł w nieskończoność
  if len(nowy_stan) > 2000:
    klucze = list(nowy_stan.keys())[-2000:]
    nowy_stan = {k: nowy_stan[k] for k in klucze}

  zapisz_stan(nowy_stan)


if __name__ == "__main__":
  sprawdz_rynki()
