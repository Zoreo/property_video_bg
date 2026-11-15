# Property videos

Brokers order a cinematic video of a listing: fill in the details, upload up to
10 photos, optionally add virtual staging, pay, and get the video by email.

- **Web app**: FastAPI, server-rendered pages (Jinja) and a little plain JS.
  Responsive, so it works on phones, tablets and desktops with no app to install.
- **Worker**: renders one paid order at a time through the video pipeline.
- **Pipeline**: each step (shot planning, staging, clips, assembly) sits behind an
  interface in `app/pipeline/base.py`. Fake versions run everything locally with
  no AI; real providers (fal.ai, Claude, Nano Banana) plug in through config.

See the backend plan for the reasoning behind the structure.

## Run it locally

Needs Python 3.11+ and ffmpeg (`brew install ffmpeg` on macOS).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

uvicorn app.main:app --reload     # the site, on http://localhost:8000
python -m app.worker              # in a second terminal: renders paid orders
```

With `PAYMENTS_MODE=fake`, "Continue to payment" marks the order paid at once,
and emails are printed in the terminal. Review rendered videos at
http://localhost:8000/admin (user and password from `.env`).

## Tests

```bash
pytest
```

## Layout

```
app/
  main.py            app setup
  config.py          settings from environment variables
  models.py          Order, Photo, Job
  pricing.py         15 EUR, +5 EUR staging
  routes/            pages, photo API, Stripe webhook, admin
  services/          storage, payments, email, queue, image intake
  pipeline/          step interfaces, fake steps, ffmpeg assembler, fal.ai stub
  worker.py          background render loop
  templates/, static/
tests/
```

## Order flow

1. `/order`: template, property, agent (saved in the browser for next time), format
2. `/order/{id}/photos`: upload up to 10, drag or arrow to reorder, staging and style
3. Stripe Checkout (or fake pay locally), then `/order/{id}/thanks`
4. Worker renders; you approve in `/admin`; the broker gets an email with `/v/{id}`

## Deploying

One Docker image, run twice: the web app (default command) and the worker
(`python -m app.worker`). Set `DATABASE_URL` to Postgres, `PAYMENTS_MODE=stripe`
with the Stripe keys, and point the Stripe webhook at `/webhooks/stripe` for the
`checkout.session.completed` event.
