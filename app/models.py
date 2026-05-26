"""Database models for recipes."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import literal_column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Recipe(Base):
    """
    Store a structured recipe.

    Args:
    -----
        No explicit constructor arguments are required.

    Returns:
    --------
        Recipe:
            Recipe ORM instance.
    """

    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    image_url: Mapped[str] = mapped_column(Text, default="")
    servings: Mapped[str] = mapped_column(String(100), default="")
    prep_time: Mapped[str] = mapped_column(String(100), default="")
    cook_time: Mapped[str] = mapped_column(String(100), default="")
    total_time: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    rating: Mapped[int] = mapped_column(Integer, default=0)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    import_warning: Mapped[str] = mapped_column(Text, default="")
    search_vector: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    ingredients: Mapped[list["Ingredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="Ingredient.sort_order",
    )
    steps: Mapped[list["InstructionStep"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="InstructionStep.sort_order",
    )
    tags: Mapped[list["RecipeTag"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeTag.name",
    )


class Ingredient(Base):
    """
    Store one ingredient line.

    Args:
    -----
        No explicit constructor arguments are required.

    Returns:
    --------
        Ingredient:
            Ingredient ORM instance.
    """

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), index=True)
    amount: Mapped[str] = mapped_column(String(80), default="")
    unit: Mapped[str] = mapped_column(String(80), default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str] = mapped_column(String(255), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")


class InstructionStep(Base):
    """
    Store one recipe instruction step.

    Args:
    -----
        No explicit constructor arguments are required.

    Returns:
    --------
        InstructionStep:
            Instruction step ORM instance.
    """

    __tablename__ = "instruction_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    recipe: Mapped[Recipe] = relationship(back_populates="steps")


class RecipeTag(Base):
    """
    Store one recipe tag.

    Args:
    -----
        No explicit constructor arguments are required.

    Returns:
    --------
        RecipeTag:
            Recipe tag ORM instance.
    """

    __tablename__ = "recipe_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    recipe: Mapped[Recipe] = relationship(back_populates="tags")


def build_search_text(recipe: Recipe) -> str:
    """
    Build searchable text for one recipe.

    Args:
    -----
        recipe (Recipe):
            Recipe with related content loaded.

    Returns:
    --------
        str:
            Combined searchable text.
    """

    values = [
        recipe.title,
        recipe.description,
        recipe.notes,
        recipe.source_name,
        " ".join(ingredient.name for ingredient in recipe.ingredients),
        " ".join(step.text for step in recipe.steps),
        " ".join(tag.name for tag in recipe.tags),
    ]
    return " ".join(value for value in values if value)


def search_rank_expression(query: str):
    """
    Build PostgreSQL full-text rank expression.

    Args:
    -----
        query (str):
            User search query.

    Returns:
    --------
        ColumnElement[Any]:
            SQLAlchemy rank expression.
    """

    document = func.to_tsvector(literal_column("'simple'"), Recipe.search_vector)
    search_query = func.plainto_tsquery(literal_column("'simple'"), query)
    return func.ts_rank(document, search_query)
