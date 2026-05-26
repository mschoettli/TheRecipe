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
docker compose up --build
```

Open `http://localhost:8000`.

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
