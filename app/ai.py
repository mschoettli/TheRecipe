"""Optional AI cleanup for imported recipes."""

import json
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from app.config import Settings


class AiCleanupError(Exception):
    """
    Signal that AI cleanup could not run.

    Args:
    -----
        message (str):
            Error message.

    Returns:
    --------
        AiCleanupError:
            Exception instance.
    """


def clean_imported_recipe(
    recipe_data: dict[str, Any],
    settings: Settings,
) -> tuple[dict[str, Any], str]:
    """
    Clean imported recipe data with the configured AI provider.

    Args:
    -----
        recipe_data (dict[str, Any]):
            Recipe data extracted from a source page.
        settings (Settings):
            Application settings.

    Returns:
    --------
        tuple[dict[str, Any], str]:
            Cleaned recipe data and an optional warning.
    """

    provider = settings.ai_provider.lower().strip()
    if provider == "disabled":
        return recipe_data, ""
    if provider == "openai":
        if not settings.openai_api_key:
            return recipe_data, "OpenAI is selected, but OPENAI_API_KEY is missing."
        return _clean_with_openai(recipe_data, settings.openai_api_key), ""
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return recipe_data, "Claude is selected, but ANTHROPIC_API_KEY is missing."
        return _clean_with_anthropic(recipe_data, settings.anthropic_api_key), ""
    return recipe_data, f"Unknown AI_PROVIDER '{settings.ai_provider}'."


def _cleanup_prompt(recipe_data: dict[str, Any]) -> str:
    return (
        "Normalize this imported recipe JSON. Return JSON only with these keys: "
        "title, description, source_url, source_name, image_url, servings, "
        "prep_time, cook_time, total_time, ingredients, steps, tags, notes. "
        "ingredients must be strings. steps must be strings. tags must be short "
        "lowercase labels. Preserve source_url. Do not invent ingredients.\n\n"
        f"{json.dumps(recipe_data, ensure_ascii=False)}"
    )


def _clean_with_openai(recipe_data: dict[str, Any], api_key: str) -> dict[str, Any]:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You clean recipe imports and return strict JSON only.",
            },
            {"role": "user", "content": _cleanup_prompt(recipe_data)},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    content = response.choices[0].message.content or "{}"
    return _merge_recipe_data(recipe_data, json.loads(content))


def _clean_with_anthropic(recipe_data: dict[str, Any], api_key: str) -> dict[str, Any]:
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=2000,
        temperature=0.1,
        system="You clean recipe imports and return strict JSON only.",
        messages=[{"role": "user", "content": _cleanup_prompt(recipe_data)}],
    )
    content = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    return _merge_recipe_data(recipe_data, json.loads(content or "{}"))


def _merge_recipe_data(
    original: dict[str, Any],
    cleaned: dict[str, Any],
) -> dict[str, Any]:
    merged = original.copy()
    for key, value in cleaned.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged
