# TheRecipe

TheRecipe is a simple Docker-based recipe library for saving structured recipes, importing recipes from URLs, and searching across titles, ingredients, steps, notes, and tags.

## Features

- Recipe cards and detailed recipe pages.
- Manual recipe creation and editing.
- URL import from pages that expose `schema.org/Recipe` data.
- Optional OpenAI or Claude cleanup for imported recipes.
- PostgreSQL full-text search.
- Minimal Chrome/Edge extension for sending the current page URL to the app.

## Quick Start

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Open `http://localhost:8000`.

Set `APP_PORT` in `.env` to change the host port, for example:

```env
APP_PORT=8010
APP_BASE_URL=http://localhost:8010
```

## OMV Auto Updates

The Compose file includes Watchtower. Watchtower checks every five minutes for a
new `ghcr.io/mschoettli/therecipe:latest` image and updates only containers that
have the Watchtower label enabled.

Old app images are removed automatically after a successful update because
Watchtower runs with `--cleanup`.

For OMV, use:

```bash
docker compose pull
docker compose up -d
```

The OMV stack uses the published image from GitHub Container Registry. The local
development override file is only needed when building on your workstation.

After that, every push to `main` builds and publishes a new image through GitHub
Actions. Watchtower pulls that image on the OMV host and restarts the app.

PostgreSQL is not labeled for Watchtower updates. Database containers should be
updated intentionally, not automatically.

## AI Import Configuration

Set one provider in `.env`:

```env
AI_PROVIDER=disabled
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

Allowed `AI_PROVIDER` values are `disabled`, `openai`, and `anthropic`.

The app works without API keys. If a provider is selected but the matching key is missing, imports are saved as editable drafts and the UI shows a warning.

## Browser Extension

1. Open Chrome or Edge extension management.
2. Enable developer mode.
3. Load the `browser-extension` folder as an unpacked extension.
4. Keep the app running at `http://localhost:8000`.
5. Click the extension button on a recipe page and save the detected recipe draft.
