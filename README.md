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

`TTS_PROVIDER=mock` (implicit) generează un WAV determinist (fără voce reală), astfel încât tot
flow-ul — player, waveform, cache, telemetrie — merge fără cheie API. În development,
`TTS_BROWSER_FALLBACK=True` face ca playerul să citească fraza cu vocea `en-GB` a browserului
(textul e cerut de la un endpoint separat doar la apăsarea Play).

Cu `TTS_PROVIDER=openai` și `OPENAI_API_KEY`, audio-ul se generează o singură dată per
combinație (text, accent, voce, nivel, viteză, provider, model, `TTS_ENGINE_VERSION`) și se
salvează în `MEDIA_ROOT/audio/`. Înregistrările umane încărcate din admin (`provider = human`)
au prioritate.

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
python manage.py seed_demo          # teme, accente, tipare, 73 de fraze, planuri, testimoniale,
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

### Audio real (OpenAI)

```bash
# în .env
TTS_PROVIDER=openai
OPENAI_API_KEY=sk-...
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=fable

python manage.py generate_audio                    # toate nivelurile, accentul implicit
python manage.py generate_audio --level natural --limit 10
```

Fișierele existente sunt refolosite; schimbarea vocii, modelului sau a `TTS_ENGINE_VERSION`
produce fișiere noi.

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
| `TTS_VOICE` | `fable` | |
| `TTS_BROWSER_FALLBACK` | `True` în dev, `False` în prod | vocea browserului pentru audio mock |
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
