"""Domain types for the component gallery.

These dataclasses are the contract between the parser, catalog, preview,
and the Django views. Frozen to keep them immutable once constructed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PropType = Literal["text", "number", "boolean", "select"]


@dataclass(frozen=True)
class Prop:
    """A single component prop, parsed from a `@prop` annotation."""

    name: str
    clean_name: str
    type: PropType
    options: tuple[str, ...] = ()
    default: str | bool = ""
    has_default: bool = False
    description: str = ""
    required: bool = False
    deprecated: str | None = None
    hidden: bool = False
    example: str = ""


@dataclass(frozen=True)
class Slot:
    """A slot, default or named, parsed from a `@slot` or `@slot:name` annotation."""

    name: str | None
    content: str = ""
    description: str = ""


@dataclass(frozen=True)
class ParsedComponent:
    """Result of running the annotation parser on a single component source file."""

    props: tuple[Prop, ...] = ()
    slots: tuple[Slot, ...] = ()
    trigger: str = ""
    description: str = ""
    accepts_attrs: bool = False

    @property
    def has_slots(self) -> bool:
        return bool(self.slots)


@dataclass(frozen=True)
class Component:
    """A scanned component on disk, ready to be linked from the gallery."""

    name: str
    path: str
    tag_path: str
    category: str
    subcategory: str
    description: str = ""
    source: str = ""


Catalog = dict[str, dict[str, list[Component]]]


@dataclass(frozen=True)
class GalleryAssets:
    """Consumer-injected assets rendered into the gallery base template.

    Resolved by `context_processors.gallery_assets` from Django settings.
    All fields are optional. Inline HTML/JS lives in `_extra_head.html` and
    `_extra_body.html` partials, not in settings — see docs.
    """

    extra_css: tuple[str, ...] = ()
    extra_js: tuple[str, ...] = ()
    dependencies: tuple = ()


@dataclass(frozen=True)
class CatalogConfig:
    """Consumer-driven catalog configuration, read from Django settings."""

    cotton_dir: Path
    excluded_categories: frozenset[str] = field(default_factory=frozenset)
    category_order: tuple[str, ...] = ()
    category_sort: Literal["asc", "desc"] = "asc"
    subcategory_order: dict[str, tuple[str, ...]] = field(default_factory=dict)
    subcategory_sort: Literal["asc", "desc"] = "asc"
