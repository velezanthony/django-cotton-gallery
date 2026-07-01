"""Annotation parser for component source files.

Reads `@description`, `@prop`, `@slot`, `@trigger` blocks from `{# ... #}` comments
and produces a structured `ParsedComponent`. Pure — no I/O, no Django imports.

Annotation syntax (pipe-style, Django filter feel):

    {# @description Short one-line component summary #}
    {# @prop variant:select['primary', 'secondary'] | default:"primary" | description:"Style" #}
    {# @prop loading:boolean | default:False | description:"Show spinner" #}
    {# @prop label:text | default:"Click me" | description:"Button label" #}
    {# @prop count:number | default:0 | description:"Badge count" #}
    {# @prop lat:text | description:"Latitude" | required #}
    {# @prop old-api:text | deprecated:"Use new-api" | hidden #}
    {# @slot Click me — Default slot content #}
    {# @slot:actions <button>Save</button> — Named slot with default content #}
    {# @slot:breadcrumb — Named slot, no default content #}
    {# @trigger <button>Open</button> — Trigger for modals/drawers #}
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .schemas import ParsedComponent, Prop, PropType, Slot

TRUTHY_TOKENS: frozenset[str | bool] = frozenset({"True", "true", "1", "on", True})


@dataclass
class _PropFilters:
    """Mutable builder for a `@prop`'s pipe filters (`| default: | required | …`).

    Internal to the parser: born empty, filled while scanning the filter
    segments, then read once to build the immutable `Prop`. Mutable on
    purpose — it's a short-lived builder, not a domain contract, so it gives
    the fields a real shape (and real types) instead of an `Any`-valued dict.
    """

    default: str = ""
    has_default: bool = False
    description: str = ""
    required: bool = False
    deprecated: str | None = None
    hidden: bool = False
    example: str = ""


_PROP_BLOCK = re.compile(r"\{#\s*@prop\s+(.+?)\s*#\}")
_FILTER = re.compile(r'^([\w-]+)(?::(?:"([^"]*)"|(\S+)))?$')
_HEAD = re.compile(r"^(:?[\w-]+):(\w+)(?:\[([^\]]*)\])?$")
_OPTION = re.compile(r"'([^']*)'")
_SLOT = re.compile(r"\{#\s*@slot(?::(?P<name>[\w-]+))?\s*(?P<body>.*?)\s*#\}")
_TRIGGER = re.compile(r"\{#\s*@trigger\s+(?P<content>.*?)(?:\s*—\s*(?P<desc>[^#]*))?\s*#\}")
_DESCRIPTION = re.compile(r"\{#\s*@description\s+(.+?)\s*#\}")
_ACCEPTS_ATTRS = re.compile(r'\{\{\s*attrs\b|:?attrs="attrs"|\battrs="attrs"')


class AnnotationParser:
    """Stateless parser that turns raw component source into a `ParsedComponent`."""

    def parse(self, source: str) -> ParsedComponent:
        return ParsedComponent(
            props=tuple(self._iter_props(source)),
            slots=tuple(self._iter_slots(source)),
            trigger=self._extract_trigger(source),
            description=self.extract_description(source),
            accepts_attrs=bool(_ACCEPTS_ATTRS.search(source)),
        )

    @staticmethod
    def extract_description(source: str) -> str:
        match = _DESCRIPTION.search(source)
        return match.group(1).strip() if match else ""

    def _iter_props(self, source: str) -> Iterator[Prop]:
        for match in _PROP_BLOCK.finditer(source):
            prop = self._parse_prop_body(match.group(1))
            if prop is not None:
                yield prop

    def _parse_prop_body(self, body: str) -> Prop | None:
        segments = [s.strip() for s in body.split("|")]

        head_match = _HEAD.match(segments[0])
        if not head_match:
            return None

        name = head_match.group(1)
        ptype: PropType = head_match.group(2)  # type: ignore[assignment]
        opts_str = head_match.group(3) or ""
        options = tuple(_OPTION.findall(opts_str)) if opts_str else ()

        attrs = self._parse_filters(segments[1:])

        if attrs.has_default:
            attrs.required = False

        default: str | bool = attrs.default
        if ptype == "boolean" and attrs.has_default:
            default = default in TRUTHY_TOKENS

        return Prop(
            name=name,
            clean_name=name.lstrip(":"),
            type=ptype,
            options=options,
            default=default,
            has_default=attrs.has_default,
            description=attrs.description,
            required=attrs.required,
            deprecated=attrs.deprecated,
            hidden=attrs.hidden,
            example=attrs.example,
        )

    @staticmethod
    def _parse_filters(segments: list[str]) -> _PropFilters:
        result = _PropFilters()
        for seg in segments:
            match = _FILTER.match(seg)
            if not match:
                continue
            key = match.group(1)
            val = match.group(2) if match.group(2) is not None else (match.group(3) or "")

            if key == "default":
                result.has_default = True
                result.default = val
            elif key == "description":
                result.description = val
            elif key == "required":
                result.required = True
            elif key == "deprecated":
                result.deprecated = val
            elif key == "hidden":
                result.hidden = True
            elif key == "example":
                result.example = val
        return result

    def _iter_slots(self, source: str) -> Iterator[Slot]:
        for match in _SLOT.finditer(source):
            body = (match.group("body") or "").strip()
            content, description = self._split_slot_body(body)
            yield Slot(name=match.group("name"), content=content, description=description)

    @staticmethod
    def _split_slot_body(body: str) -> tuple[str, str]:
        if body.startswith("—"):
            return "", body.lstrip("—").strip()
        if " — " in body:
            content, description = body.split(" — ", 1)
            return content.strip(), description.strip()
        return body, ""

    @staticmethod
    def _extract_trigger(source: str) -> str:
        match = _TRIGGER.search(source)
        return match.group("content").strip() if match else ""
