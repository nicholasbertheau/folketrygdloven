# Folketrygdloven – søk og rettskilder

En enkel, statisk søkeside for **lov om folketrygd (ftrl.)** og tilhørende rundskriv. Data hentes automatisk fra [Lovdata](https://lovdata.no) sitt åpne API (NLOD 2.0) og oppdateres ukentlig via GitHub Actions.

🌐 **Live:** https://nicholasbertheau.github.io/folketrygdloven/

> ⚠️ Dette er **ikke** en offisiell Lovdata-tjeneste. Bruk [lovdata.no](https://lovdata.no) som autoritativ kilde.

## Funksjoner

- 🔎 **Søk** i alle paragrafer (Fuse.js, fuzzy match på tittel og tekst)
- 📑 **Innholdsfortegnelse** med kapittel-navigasjon
- 🏦 **Pensjons-modus** med kodemapping mot kapittel 20
- 📝 **Endringslogg** – auto-generert diff hver uke
- 🕒 **Versjonshistorikk** – se hvordan rettskildene så ut på et gitt tidspunkt
- 🌙 Lys/mørk modus
- 📱 Mobilvennlig

## Versjonsvelger

Klokke-knappen (🕒) i headeren lar deg velge en historisk versjon av både `folketrygdloven.json` og `rundskriv_kap20.json`. Versjonene er repoets egne git-snapshots (én per ukentlig auto-commit), hentet via GitHub commits-API. Valgt versjon lagres i URL (`#v=<sha>`) så lenker kan deles.

## Datakilder

| Fil | Beskrivelse | Kilde |
|---|---|---|
| `folketrygdloven.json` | Hele lovteksten, strukturert som deler → kapitler → paragrafer | `api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2` |
| `rundskriv_kap20.json` | NAVs rundskriv til kap. 20 (alderspensjon) | `lovdata.no/nav/rundskriv/r20-00` |
| `changelog.json` | Endringer mellom oppdateringer | Auto-generert |

Alt dataarbeid skjer i GitHub Actions – repoet inneholder ingen kode som må kjøres lokalt for å bruke siden.

## Arkitektur

Ett enkelt statisk frontend-prosjekt:

```
folketrygdloven/
├── index.html              # Hele frontend (CSS + JS i én fil)
├── folketrygdloven.json    # Lovteksten
├── rundskriv_kap20.json    # Rundskriv kap. 20
├── changelog.json          # Endringslogg
├── scripts/
│   ├── update_data.py      # Henter og parser folketrygdloven fra Lovdata
│   └── parse_rundskriv.py  # Henter og parser rundskriv kap. 20
└── .github/workflows/
    └── update.yml          # Kjører hver mandag kl. 06:00 UTC
```

Ingen byggesteg, ingen avhengigheter i frontend utenom [Fuse.js](https://fusejs.io/) (CDN).

## Kjør lokalt

```bash
git clone https://github.com/nicholasbertheau/folketrygdloven.git
cd folketrygdloven
python3 -m http.server 8000
# Åpne http://localhost:8000
```

## Oppdater data manuelt

```bash
pip install beautifulsoup4
python scripts/update_data.py
python scripts/parse_rundskriv.py
```

Eller trigg workflowen via GitHub UI: **Actions → Oppdater folketrygdloven → Run workflow**.

## Lisens

Lovteksten er offentlig informasjon publisert av Lovdata under [NLOD 2.0](https://data.norge.no/nlod/no/2.0). Koden i dette repoet kan brukes fritt.
