# dictare.ro

Aplicație web pentru antrenarea **listening-ului în engleza britanică**.
Bucla principală: **ascultă → scrie → verifică → înțelege → repetă**.

Utilizatorul ascultă o frază britanică reală, scrie ce a auzit, primește un scor pe cuvinte, vede
transcrierea cu greșelile evidențiate și o explicație în română pentru fiecare fenomen de vorbire
naturală (forme slabe, linking, asimilare, eliziune, glottal t etc.). Greșelile alimentează un
profil de ascultare, iar exercițiile următoare sunt alese pe baza lui.

Nu este un curs general de engleză, un traducător sau un corector gramatical.

---

## Arhitectură

Python 3.11+, Django 5.2, PostgreSQL, Django Templates + HTMX, JavaScript vanilla (fără framework SPA).

```
config/            settings/{base,dev,prod,test}.py, urls, wsgi/asgi
apps/
  core/            homepage, pagini statice, Testimonial, /health/, robots, sitemap,
                   middleware (CSP, Permissions-Policy), rate limiter, template tags (icon, donut)
  accounts/        User pe email, Profile (fus orar, obiectiv zilnic, accent), signup/login/
                   reset parolă/verificare email, /account/
  listening/       conținut: Topic, Accent, SpeechPattern, ListeningPhrase, PhrasePattern,
                   AudioVariant + admin + seed_data.py (fraze și explicații)
  ai/              services/tts.py: abstracție TTS (mock, openai), cache pe hash, generate_audio
  scoring/         fără modele: normalize.py, align.py, services.py (score_answer)
  practice/        PracticeSession, SessionItem, ListeningAttempt, AttemptMistake;
                   services/{sessions,selection,personalization}.py; views HTMX
  progress/        DailyPractice, PatternMastery; services/{streak,mastery,stats,daily}.py;
                   /progress/, /mistakes/
  billing/         Plan, Subscription; services/entitlements.py (feature gating centralizat),
                   providers/ (interfață plăți, ManualProvider), services/subscriptions.py
templates/         layouts/, components/, partials/, pages/, icons/*.svg
static/            css/ (tokens, base, layout, components, app, marketing, pages), js/, images/
tests/             pytest (unit, services, views, permisiuni, admin) + tests/e2e (Playwright)
```

Principii:

- **Views subțiri**, logica în servicii: scoring, selecție exerciții, personalizare, mastery,
  streak, statistici, TTS, entitlements.
- **Transcrierea nu apare în HTML** până la verificare; fișierele audio au nume hash.
- **Nivelurile audio** (Engleză britanică / naturală / rapidă) sunt variante audio separate, cu
  instrucțiuni de stil diferite pentru TTS, nu doar viteză de redare. **Accentul** e un atribut
  separat de dificultate.
- **Free / Pro**: toate verificările trec prin `apps.billing.services.entitlements.get_entitlements`.
  Nu există plăți simulate: Pro se acordă din admin (`ManualProvider`), iar
  `apply_subscription_event()` e pregătit pentru webhook-uri Stripe.

### Scoring (`apps/scoring`)

1. Normalizare: majuscule, punctuație, apostrofuri curbe, spații, cifre mici → cuvinte,
   contracții scrise fără apostrof (`didnt`).
2. Aliniere pe cuvinte (Levenshtein ponderat, substituții mai ieftine pentru cuvinte apropiate).
3. Clasificare: corect, lipsă, greșit, în plus, altă ordine, formă contrasă (`I'll` / `I will`),
   ortografie UK/US (`realise` / `realize`).
4. Scor 0–100 ponderat: cuvintele funcționale (to, of, can…) cântăresc 0.6, cele de conținut 1.0;
   negațiile contează întotdeauna.

### Personalizare și mastery

- `PatternMastery` (0–100) per utilizator și tipar, recalculat la fiecare exercițiu din ultimele
  ~20 de expuneri: ponderare pe recență și dificultate, penalizare pentru transcriere văzută
  înainte de verificare și pentru multe reluări, scalare după încredere (număr de expuneri).
- `WeaknessRecommender` crește probabilitatea frazelor care conțin tiparele slabe; interfața
  `Recommender` permite înlocuirea cu un model AI mai târziu.
- Serie zilnică (streak) calculată pe data locală din `Profile.timezone`.

### Audio

Generarea (comenzi, admin) e separată de selecție (request-urile cursanților):

- `apps/ai/services/tts.py`: provideri (`mock`, `openai`), prompturi per nivel, cache key,
  erori tipizate, `generate_variant()`.
- `apps/listening/services/audio.py`: `get_audio_variant()` — doar interogări în baza de date,
  fără rețea.
- `apps/listening/services/patterns.py`: ce tipare se pot explica pentru o anumită
  înregistrare.
- `apps/listening/services/qa.py`: aprobare / respingere.

Nivelurile diferă în primul rând prin **modul de rostire** (instrucțiuni distincte), nu doar prin
viteză: Clear (puțin mai lent, articulat, dar natural), Natural (conversațional, connected
speech, forme slabe), Fast (fluent, reduceri realiste doar unde apar natural). Vitezele sunt
moderate (0.95 / 1.0 / 1.08).

`TTS_PROVIDER=mock` generează un WAV-placeholder (fără voce) pentru development și teste; în
development playerul îl poate citi cu vocea en-GB a browserului. Audio mock nu poate fi aprobat
și nu e servit în producție.

---

## Cerințe

- Python 3.11+
- PostgreSQL 14+ (sau Docker)
- Opțional: Node nu e necesar; Chromium pentru testele e2e se instalează prin Playwright.

## Instalare locală

```bash
git clone <repo> dictare && cd dictare
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

pip install -r requirements/dev.txt
cp .env.example .env            # Windows: copy .env.example .env
```

### PostgreSQL

Cu Docker (recomandat, container dedicat pe portul 5435):

```bash
docker compose up -d db
```

Sau pe un PostgreSQL existent:

```sql
CREATE USER dictare WITH PASSWORD 'dictare' CREATEDB;
CREATE DATABASE dictare OWNER dictare;
```

și setează `DATABASE_URL` în `.env`, de ex. `postgres://dictare:dictare@127.0.0.1:5432/dictare`.
(`CREATEDB` e necesar pentru ca testele să-și poată crea baza de test.)

### Migrații, date demo, server

```bash
python manage.py migrate
python manage.py seed_demo          # teme, accente, tipare, 75 de fraze, planuri, testimoniale,
                                    # audio mock și 2 utilizatori demo cu 3 săptămâni de istoric
python manage.py createsuperuser    # pentru /admin/
python manage.py runserver
```

Deschide http://localhost:8000. Conturi demo (doar pentru development):

| Email | Plan | Parolă |
|---|---|---|
| demo@dictare.ro | Pro (serie de 12 zile) | `dictare-demo-2026` |
| free@dictare.ro | Gratuit | `dictare-demo-2026` |

`seed_demo` este idempotent. Opțiuni: `--no-audio`, `--no-demo-user`.

### Audio real (OpenAI) și QA

**Audio-ul este conținutul educațional.** Un MP3 generat nu ajunge automat la cursanți: fiecare
variantă începe ca `pending`, e ascultată, aprobată sau respinsă, iar tiparele de vorbire sunt
verificate pe *acea* înregistrare.

Configurare (`.env`, git-ignored — cheia se citește doar din environment):

```bash
TTS_PROVIDER=openai
OPENAI_API_KEY=...
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=fable            # nu e definitivă până la audiția vocilor
TTS_ENGINE_VERSION=2
TTS_REQUIRE_APPROVAL=False # True în producție
```

**1. Alege vocea** (fișiere de comparat, nu intră în baza de date):

```bash
python manage.py audition_voices --dry-run
python manage.py audition_voices --voices marin cedar fable
```

Rezultat în `media/qa/tts-audition/`: `<voce>/<nivel>/NN-fraza.mp3`, `manifest.json`
(frază, voce, model, nivel, accent, instrucțiuni, viteză, fișier, timestamp) și `index.html`
cu toate vocile și nivelurile una lângă alta. 11 fraze × 3 voci × 3 niveluri = 99 fișiere.

**2. Generează corpusul pilot** (28 de fraze care acoperă forme slabe, would/could/did you,
linking, contracții, eliziune, schwa, glottal T, întrebări, fraze scurte și lungi):

```bash
python manage.py generate_audio --pilot --voice marin --dry-run   # 28 × 3 = 84, fără API
python manage.py generate_audio --pilot --voice marin --real-api
python manage.py generate_audio --pilot --voice marin --real-api --level natural --limit 5
```

Comanda afișează numărul de generări înainte de a începe, sare peste fișierele deja generate
cu aceleași setări (o rulare întreruptă se reia pur și simplu) și raportează fiecare eroare
(frază, nivel, voce, tip: authentication / rate_limit / timeout / unavailable / bad_response).

**3. Ascultă și aprobă** în `/admin/listening/audiovariant/review/`: Clear / Natural / Fast
pentru fiecare frază, cu butoane Aprobă / Respinge și notă QA. Din lista de variante audio există
și acțiunile „Aprobă / Respinge variantele selectate”. Audio mock nu poate fi aprobat.

**4. Verifică tiparele pe înregistrare**: în pagina unei variante audio, pentru fiecare tipar
marchează `prezent` / `absent` și, opțional, cum se aude (`/ɡɒʔ ə/`) și o explicație specifică.
Pentru cursant:

- `prezent` → apare la „În această înregistrare”;
- `neverificat` dar așteptat la nivelul respectiv → apare doar ca „Tendință frecventă în
  vorbirea naturală”, fără să pretindă că se aude;
- `absent` sau neașteptat la acel nivel → nu apare.

Greșelile și nivelul de stăpânire (mastery) se atribuie tot numai tiparelor valabile pentru
înregistrarea ascultată.

**5. Producție**: cu `TTS_REQUIRE_APPROVAL=True` se servesc doar înregistrări aprobate
(prioritate: înregistrare umană aprobată → TTS aprobat), iar sesiunile aleg doar fraze care au
audio aprobat. Request-urile cursanților nu generează niciodată audio și nu apelează OpenAI;
dacă lipsește audio-ul, pagina afișează „Audio indisponibil”.

**6. Generarea completă** (toate frazele) se face abia după alegerea vocii și validarea
setărilor pe pilot: `python manage.py generate_audio --voice VOCEA_ALEASĂ --real-api`.

Cache: fișierul e identificat prin hash-ul textului, providerului, modelului, vocii, accentului,
instrucțiunilor complete, nivelului, vitezei și `TTS_ENGINE_VERSION`. Orice schimbare a
prompturilor generează fișiere noi. **Schimbarea `TTS_ENGINE_VERSION` = regenerare audio**;
variantele vechi își păstrează statusul QA până sunt înlocuite de cele noi, aprobate.

Înregistrări umane: încarcă fișierul în admin (varianta audio, `provider = human`). O
înregistrare umană aprobată are prioritate față de TTS pentru aceeași frază, nivel și accent.
Accentele regionale (Londra, Nord, Scoția, Țara Galilor) sunt pregătite doar pentru înregistrări
umane; sinteza vocală nu le redă fiabil.

## Variabile de mediu

| Variabilă | Implicit | Descriere |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` (manage.py), `config.settings.prod` (wsgi) | |
| `SECRET_KEY` | — | obligatoriu în producție (≥ 40 caractere) |
| `DEBUG` | `True` în dev | |
| `DATABASE_URL` | `postgres://dictare:dictare@127.0.0.1:5435/dictare` | |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | listă separată prin virgulă |
| `CSRF_TRUSTED_ORIGINS` | — | ex. `https://dictare.ro` |
| `SITE_URL` | `http://localhost:8000` | pentru canonical, OpenGraph, emailuri |
| `TTS_PROVIDER` | `mock` | `mock` sau `openai` |
| `OPENAI_API_KEY` | — | |
| `TTS_MODEL` | `gpt-4o-mini-tts` | |
| `TTS_VOICE` | `fable` | vocea pentru `generate_audio` (de ales după audiție) |
| `TTS_AUDITION_VOICES` | `marin,cedar,fable` | vocile pentru `audition_voices` |
| `TTS_ENGINE_VERSION` | `2` | schimbarea lui forțează regenerarea audio |
| `TTS_REQUIRE_APPROVAL` | `False` (dev), `True` (prod) | servește doar audio aprobat |
| `TTS_GENERATE_ON_REQUEST` | `True` (dev), `False` (prod) | doar placeholder mock, niciodată OpenAI |
| `TTS_BROWSER_FALLBACK` | `True` în dev, mereu `False` în prod | vocea browserului pentru audio mock, doar cu `DEBUG` |
| `EMAIL_URL` | `consolemail://` | ex. `smtp+tls://user:pass@smtp.host:587` |
| `DEFAULT_FROM_EMAIL` | `dictare.ro <salut@dictare.ro>` | |
| `CACHE_URL` | `locmemcache://` | folosește Redis în producție: `redis://host:6379/1` |
| `CSP_ENFORCE` | `False` | `False` = Content-Security-Policy-Report-Only |
| `SERVE_MEDIA` | `True` | servește `/media/` din Django (vezi mai jos) |
| `MEDIA_ROOT` | `./media` | |
| `SOCIAL_YOUTUBE_URL`, `SOCIAL_INSTAGRAM_URL`, `SOCIAL_X_URL` | gol | gol = iconiță „în curând” |
| `LOG_LEVEL` | `INFO` | |

## Teste

```bash
python -m playwright install chromium   # o singură dată, pentru testele e2e
pytest                                  # toate testele (unit + views + e2e)
pytest -m "not e2e"                     # fără browser
pytest -m e2e                           # doar testele responsive
```

Testele e2e verifică homepage-ul, sesiunea de exerciții și navigarea la 320, 375, 390, 430, 768,
1024, 1280 și 1440 px: fără scroll orizontal, navigația potrivită (hamburger / bottom nav),
butoanele principale în ecran și suficient de mari pentru touch.

Calitate cod:

```bash
ruff check . && ruff format --check .
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Producție

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod
python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi                 # configurat în gunicorn.conf.py
```

- `config.settings.prod`: `DEBUG=False`, HSTS, redirect HTTPS (în afară de `/health/`),
  cookie-uri `Secure`, `X-Frame-Options: DENY`, Referrer-Policy, COOP.
- Fișiere statice: WhiteNoise cu `CompressedManifestStaticFilesStorage` (hash + gzip/brotli).
- Audio (`/media/audio/`): numele fișierelor sunt hash-uri, servite cu
  `Cache-Control: immutable`. Pe un singur server, `SERVE_MEDIA=True` e suficient; la scară,
  pune `MEDIA_ROOT` în spatele nginx sau într-un object storage și setează `SERVE_MEDIA=False`.
- Rate limiting: folosește cache-ul Django — în producție cu mai mulți workeri setează
  `CACHE_URL` către Redis.
- CSP: politica e în `CSP_POLICY` (`config/settings/base.py`); nu există scripturi inline, deci
  poate fi aplicată cu `CSP_ENFORCE=True` după verificarea rapoartelor.
- Health check: `GET /health/` → `{"status": "ok", "database": true}` (503 dacă DB e căzut).
- Loguri: stdout, nivel din `LOG_LEVEL`. Erorile 404/500 au pagini proprii, fără stack trace.
- Plăți: nu sunt integrate. Pentru Stripe, implementează un `PaymentProvider` în
  `apps/billing/providers` și transformă webhook-urile în `SubscriptionEvent` pentru
  `apply_subscription_event()`.

## Administrare conținut

`/admin/` permite gestionarea frazelor (cu tipare și variante audio inline, acțiune „Generează
audio”, preview audio), temelor, accentelor, tiparelor de vorbire, planurilor, abonamentelor,
testimonialelor și utilizatorilor. Încercările și greșelile sunt read-only, pentru diagnostic.

Pentru un tipar într-o frază se introduce doar **fragmentul** exact (ex. `would you`); poziția în
frază se calculează automat.
