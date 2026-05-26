"""Recipe import helpers."""

import json
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


class RecipeImportError(Exception):
    """
    Signal that a recipe URL could not be imported.

    Args:
    -----
        message (str):
            Error message.

    Returns:
    --------
        RecipeImportError:
            Exception instance.
    """


async def import_recipe_from_url(url: str) -> tuple[dict[str, Any], str]:
    """
    Import recipe data from a URL.

    Args:
    -----
        url (str):
            Source URL to fetch and parse.

    Returns:
    --------
        tuple[dict[str, Any], str]:
            Imported recipe data and optional warning.

    Raises:
    -------
        RecipeImportError:
            Raised when the URL cannot be fetched.
    """

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RecipeImportError("Only http and https URLs can be imported.")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20,
            headers={"User-Agent": "TheRecipe/1.0"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RecipeImportError(f"Could not fetch recipe URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    recipe_data = _extract_schema_recipe(soup)
    if recipe_data:
        recipe_data["source_url"] = url
        recipe_data.setdefault("source_name", parsed.netloc)
        return recipe_data, ""

    title = soup.find("title")
    return (
        {
            "title": title.get_text(strip=True) if title else parsed.netloc,
            "source_url": url,
            "source_name": parsed.netloc,
            "description": "",
            "image_url": "",
            "ingredients": [],
            "steps": [],
            "tags": [],
            "notes": "",
        },
        "No structured recipe data was found. The recipe was saved as a draft.",
    )


def _extract_schema_recipe(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        for item in _jsonld_items(raw):
            recipe = _find_recipe_item(item)
            if recipe:
                return _normalize_schema_recipe(recipe)
    return None


def _jsonld_items(raw: str) -> list[Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _find_recipe_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    item_type = item.get("@type")
    if item_type == "Recipe" or (
        isinstance(item_type, list) and "Recipe" in item_type
    ):
        return item
    graph = item.get("@graph")
    if isinstance(graph, list):
        for graph_item in graph:
            recipe = _find_recipe_item(graph_item)
            if recipe:
                return recipe
    return None


def _normalize_schema_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    instructions = recipe.get("recipeInstructions", [])
    return {
        "title": _text_value(recipe.get("name")),
        "description": _text_value(recipe.get("description")),
        "source_url": _text_value(recipe.get("url")),
        "source_name": _text_value(recipe.get("author")),
        "image_url": _image_value(recipe.get("image")),
        "servings": _text_value(recipe.get("recipeYield")),
        "prep_time": _text_value(recipe.get("prepTime")),
        "cook_time": _text_value(recipe.get("cookTime")),
        "total_time": _text_value(recipe.get("totalTime")),
        "ingredients": [
            _text_value(value) for value in recipe.get("recipeIngredient", [])
        ],
        "steps": _instruction_values(instructions),
        "tags": _keywords(recipe.get("keywords")),
        "notes": "",
    }


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ", ".join(_text_value(item) for item in value if _text_value(item))
    if isinstance(value, dict):
        return _text_value(value.get("name") or value.get("text") or value.get("@id"))
    return str(value).strip()


def _image_value(value: Any) -> str:
    if isinstance(value, list) and value:
        return _image_value(value[0])
    if isinstance(value, dict):
        return _text_value(value.get("url") or value.get("contentUrl"))
    return _text_value(value)


def _instruction_values(instructions: Any) -> list[str]:
    if isinstance(instructions, str):
        return [instructions]
    if not isinstance(instructions, list):
        return []
    values = []
    for item in instructions:
        if isinstance(item, dict) and item.get("@type") == "HowToSection":
            values.extend(_instruction_values(item.get("itemListElement", [])))
        else:
            text = _text_value(item)
            if text:
                values.append(text)
    return values


def _keywords(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [_text_value(item).lower() for item in value if _text_value(item)]
    return []
