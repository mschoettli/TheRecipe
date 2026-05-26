"""FastAPI application for TheRecipe."""

from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, literal_column, or_, select
from sqlalchemy.orm import Session, selectinload

from app.ai import clean_imported_recipe
from app.config import get_settings
from app.database import get_db, initialize_database
from app.importer import RecipeImportError, import_recipe_from_url
from app.models import (
    Ingredient,
    InstructionStep,
    Recipe,
    RecipeTag,
    build_search_text,
    search_rank_expression,
)

app = FastAPI(title="TheRecipe")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup() -> None:
    """
    Initialize application resources.

    Returns:
    --------
        None:
            Database tables are created when missing.
    """

    initialize_database()


@app.get("/", response_class=HTMLResponse)
def list_recipes(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Render the recipe library.

    Args:
    -----
        request (Request):
            Current HTTP request.
        q (str):
            Optional search query.
        db (Session):
            Database session.

    Returns:
    --------
        HTMLResponse:
            Recipe index page.
    """

    statement = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients),
            selectinload(Recipe.steps),
            selectinload(Recipe.tags),
        )
        .order_by(desc(Recipe.favorite), desc(Recipe.updated_at))
    )
    if q.strip():
        query = q.strip()
        document = func.to_tsvector(literal_column("'simple'"), Recipe.search_vector)
        search_query = func.plainto_tsquery(literal_column("'simple'"), query)
        statement = (
            select(Recipe)
            .options(
                selectinload(Recipe.ingredients),
                selectinload(Recipe.steps),
                selectinload(Recipe.tags),
            )
            .where(
                or_(
                    document.op("@@")(search_query),
                    Recipe.search_vector.ilike(f"%{query}%"),
                )
            )
            .order_by(desc(search_rank_expression(query)), desc(Recipe.updated_at))
        )
    recipes = db.scalars(statement).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "recipes": recipes, "q": q},
    )


@app.get("/recipes/new", response_class=HTMLResponse)
def new_recipe(request: Request) -> HTMLResponse:
    """
    Render an empty recipe form.

    Args:
    -----
        request (Request):
            Current HTTP request.

    Returns:
    --------
        HTMLResponse:
            Recipe form page.
    """

    return templates.TemplateResponse(
        "recipe_form.html",
        {
            "request": request,
            "recipe": None,
            "ingredients_text": "",
            "steps_text": "",
            "tags_text": "",
            "action": "/recipes",
        },
    )


@app.post("/recipes")
def create_recipe(
    title: str = Form(...),
    description: str = Form(""),
    source_url: str = Form(""),
    source_name: str = Form(""),
    image_url: str = Form(""),
    servings: str = Form(""),
    prep_time: str = Form(""),
    cook_time: str = Form(""),
    total_time: str = Form(""),
    notes: str = Form(""),
    rating: int = Form(0),
    favorite: bool = Form(False),
    ingredients: str = Form(""),
    steps: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Create one recipe.

    Args:
    -----
        title (str):
            Recipe title.
        description (str):
            Recipe description.
        source_url (str):
            Original source URL.
        source_name (str):
            Original source name.
        image_url (str):
            Recipe image URL.
        servings (str):
            Serving count.
        prep_time (str):
            Preparation time.
        cook_time (str):
            Cook time.
        total_time (str):
            Total time.
        notes (str):
            Personal notes.
        rating (int):
            Personal rating from 0 to 5.
        favorite (bool):
            Favorite marker.
        ingredients (str):
            Newline-separated ingredient lines.
        steps (str):
            Newline-separated instruction steps.
        tags (str):
            Comma-separated tags.
        db (Session):
            Database session.

    Returns:
    --------
        RedirectResponse:
            Redirect to the created recipe.
    """

    recipe = Recipe()
    _apply_recipe_form(
        recipe,
        {
            "title": title,
            "description": description,
            "source_url": source_url,
            "source_name": source_name,
            "image_url": image_url,
            "servings": servings,
            "prep_time": prep_time,
            "cook_time": cook_time,
            "total_time": total_time,
            "notes": notes,
            "rating": rating,
            "favorite": favorite,
            "ingredients": ingredients,
            "steps": steps,
            "tags": tags,
        },
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return RedirectResponse(f"/recipes/{recipe.id}", status_code=303)


@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def show_recipe(
    recipe_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Render one recipe.

    Args:
    -----
        recipe_id (int):
            Recipe identifier.
        request (Request):
            Current HTTP request.
        db (Session):
            Database session.

    Returns:
    --------
        HTMLResponse:
            Recipe detail page.

    Raises:
    -------
        HTTPException:
            Raised when the recipe is missing.
    """

    recipe = _get_recipe_or_404(db, recipe_id)
    return templates.TemplateResponse(
        "recipe_detail.html",
        {"request": request, "recipe": recipe},
    )


@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
def edit_recipe(
    recipe_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Render the recipe edit form.

    Args:
    -----
        recipe_id (int):
            Recipe identifier.
        request (Request):
            Current HTTP request.
        db (Session):
            Database session.

    Returns:
    --------
        HTMLResponse:
            Recipe edit form.
    """

    recipe = _get_recipe_or_404(db, recipe_id)
    return templates.TemplateResponse(
        "recipe_form.html",
        {
            "request": request,
            "recipe": recipe,
            "ingredients_text": "\n".join(
                _format_ingredient(item) for item in recipe.ingredients
            ),
            "steps_text": "\n".join(step.text for step in recipe.steps),
            "tags_text": ", ".join(tag.name for tag in recipe.tags),
            "action": f"/recipes/{recipe.id}",
        },
    )


@app.post("/recipes/{recipe_id}")
def update_recipe(
    recipe_id: int,
    title: str = Form(...),
    description: str = Form(""),
    source_url: str = Form(""),
    source_name: str = Form(""),
    image_url: str = Form(""),
    servings: str = Form(""),
    prep_time: str = Form(""),
    cook_time: str = Form(""),
    total_time: str = Form(""),
    notes: str = Form(""),
    rating: int = Form(0),
    favorite: bool = Form(False),
    ingredients: str = Form(""),
    steps: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Update one recipe.

    Args:
    -----
        recipe_id (int):
            Recipe identifier.
        title (str):
            Recipe title.
        description (str):
            Recipe description.
        source_url (str):
            Original source URL.
        source_name (str):
            Original source name.
        image_url (str):
            Recipe image URL.
        servings (str):
            Serving count.
        prep_time (str):
            Preparation time.
        cook_time (str):
            Cook time.
        total_time (str):
            Total time.
        notes (str):
            Personal notes.
        rating (int):
            Personal rating from 0 to 5.
        favorite (bool):
            Favorite marker.
        ingredients (str):
            Newline-separated ingredient lines.
        steps (str):
            Newline-separated instruction steps.
        tags (str):
            Comma-separated tags.
        db (Session):
            Database session.

    Returns:
    --------
        RedirectResponse:
            Redirect to the updated recipe.
    """

    recipe = _get_recipe_or_404(db, recipe_id)
    _apply_recipe_form(
        recipe,
        {
            "title": title,
            "description": description,
            "source_url": source_url,
            "source_name": source_name,
            "image_url": image_url,
            "servings": servings,
            "prep_time": prep_time,
            "cook_time": cook_time,
            "total_time": total_time,
            "notes": notes,
            "rating": rating,
            "favorite": favorite,
            "ingredients": ingredients,
            "steps": steps,
            "tags": tags,
        },
    )
    recipe.is_draft = False
    recipe.import_warning = ""
    db.commit()
    return RedirectResponse(f"/recipes/{recipe.id}", status_code=303)


@app.post("/recipes/{recipe_id}/delete")
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Delete one recipe.

    Args:
    -----
        recipe_id (int):
            Recipe identifier.
        db (Session):
            Database session.

    Returns:
    --------
        RedirectResponse:
            Redirect to the recipe index.
    """

    recipe = _get_recipe_or_404(db, recipe_id)
    db.delete(recipe)
    db.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/imports/new", response_class=HTMLResponse)
def new_import(request: Request) -> HTMLResponse:
    """
    Render the URL import form.

    Args:
    -----
        request (Request):
            Current HTTP request.

    Returns:
    --------
        HTMLResponse:
            Import form page.
    """

    return templates.TemplateResponse(
        "import_form.html",
        {"request": request, "warning": ""},
    )


@app.post("/imports/from-url")
async def import_from_url(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Import one recipe URL as an editable draft.

    Args:
    -----
        request (Request):
            Current HTTP request.
        db (Session):
            Database session.

    Returns:
    --------
        RedirectResponse | dict[str, Any]:
            Redirect for form calls or JSON for extension calls.
    """

    wants_json = request.headers.get("content-type", "").startswith("application/json")
    if wants_json:
        payload = await request.json()
        url = str(payload.get("url", ""))
    else:
        form = await request.form()
        url = str(form.get("url", ""))

    if not url:
        if wants_json:
            raise HTTPException(status_code=400, detail="Missing URL.")
        return templates.TemplateResponse(
            "import_form.html",
            {"request": request, "warning": "Please enter a URL."},
            status_code=400,
        )

    try:
        recipe_data, warning = await import_recipe_from_url(url)
    except RecipeImportError as exc:
        recipe_data = {
            "title": url,
            "source_url": url,
            "ingredients": [],
            "steps": [],
            "tags": [],
        }
        warning = str(exc)

    settings = get_settings()
    try:
        recipe_data, ai_warning = clean_imported_recipe(recipe_data, settings)
    except Exception as exc:
        ai_warning = f"AI cleanup failed: {exc}"
    warning = " ".join(item for item in [warning, ai_warning] if item)

    recipe = _recipe_from_import(recipe_data, warning)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)

    edit_url = f"/recipes/{recipe.id}/edit"
    if wants_json:
        return {
            "recipe_id": recipe.id,
            "draft_url": f"{settings.app_base_url}{edit_url}",
        }
    return RedirectResponse(edit_url, status_code=303)


def _get_recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    statement = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients),
            selectinload(Recipe.steps),
            selectinload(Recipe.tags),
        )
        .where(Recipe.id == recipe_id)
    )
    recipe = db.scalar(statement)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return recipe


def _apply_recipe_form(recipe: Recipe, values: dict[str, Any]) -> None:
    recipe.title = values["title"].strip()
    recipe.description = values["description"].strip()
    recipe.source_url = values["source_url"].strip()
    recipe.source_name = values["source_name"].strip()
    recipe.image_url = values["image_url"].strip()
    recipe.servings = values["servings"].strip()
    recipe.prep_time = values["prep_time"].strip()
    recipe.cook_time = values["cook_time"].strip()
    recipe.total_time = values["total_time"].strip()
    recipe.notes = values["notes"].strip()
    recipe.rating = max(0, min(int(values["rating"] or 0), 5))
    recipe.favorite = bool(values["favorite"])

    recipe.ingredients = [
        Ingredient(name=line, sort_order=index)
        for index, line in enumerate(_lines(values["ingredients"]))
    ]
    recipe.steps = [
        InstructionStep(text=line, sort_order=index)
        for index, line in enumerate(_lines(values["steps"]))
    ]
    recipe.tags = [
        RecipeTag(name=tag)
        for tag in _tags(values["tags"])
    ]
    recipe.search_vector = build_search_text(recipe)


def _recipe_from_import(recipe_data: dict[str, Any], warning: str) -> Recipe:
    recipe = Recipe(
        title=str(recipe_data.get("title") or "Imported recipe").strip(),
        description=str(recipe_data.get("description") or "").strip(),
        source_url=str(recipe_data.get("source_url") or "").strip(),
        source_name=str(recipe_data.get("source_name") or "").strip(),
        image_url=str(recipe_data.get("image_url") or "").strip(),
        servings=str(recipe_data.get("servings") or "").strip(),
        prep_time=str(recipe_data.get("prep_time") or "").strip(),
        cook_time=str(recipe_data.get("cook_time") or "").strip(),
        total_time=str(recipe_data.get("total_time") or "").strip(),
        notes=str(recipe_data.get("notes") or "").strip(),
        is_draft=True,
        import_warning=warning,
    )
    recipe.ingredients = [
        Ingredient(name=str(value).strip(), sort_order=index)
        for index, value in enumerate(recipe_data.get("ingredients") or [])
        if str(value).strip()
    ]
    recipe.steps = [
        InstructionStep(text=str(value).strip(), sort_order=index)
        for index, value in enumerate(recipe_data.get("steps") or [])
        if str(value).strip()
    ]
    recipe.tags = [
        RecipeTag(name=str(value).strip().lower())
        for value in recipe_data.get("tags") or []
        if str(value).strip()
    ]
    recipe.search_vector = build_search_text(recipe)
    return recipe


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _tags(value: str) -> list[str]:
    return [tag.strip().lower() for tag in value.split(",") if tag.strip()]


def _format_ingredient(ingredient: Ingredient) -> str:
    parts = [ingredient.amount, ingredient.unit, ingredient.name, ingredient.note]
    return " ".join(part for part in parts if part)
