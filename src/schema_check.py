"""A JSON Schema checker for the subset the execution handoff's schema uses.

``docs/operations/orders-schema.json`` is an ordinary JSON Schema (draft
2020-12) that any validator can read. This repository pins no validator, so
the files it writes are checked here against that same schema with the
keywords the schema uses and nothing else: ``type`` (a name or a list),
``properties``, ``required``, ``additionalProperties`` (true or false),
``items``, ``enum``, ``const``, ``minimum``, ``maximum``, ``exclusiveMinimum``,
``minLength``, ``maxLength``, ``pattern``, ``minItems``, ``maxItems`` and a
``$ref`` into the same document's ``$defs``. A schema that uses any other
keyword is refused by name, so the checker can never pass a file by
ignoring a rule it does not read.
"""
from __future__ import annotations

import re
from typing import Any

KEYWORDS = frozenset({
    "$schema", "$id", "$defs", "$ref", "$comment", "title", "description", "type", "properties", "required",
    "additionalProperties", "items", "enum", "const", "minimum", "maximum", "exclusiveMinimum", "minLength",
    "maxLength", "pattern", "minItems", "maxItems"})

TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


class SchemaError(ValueError):
    """The schema uses a keyword or a reference this checker does not read."""


def _resolve(root: dict, ref: str) -> dict:
    if not ref.startswith("#/$defs/"):
        raise SchemaError(f"unsupported $ref {ref!r}")
    name = ref[len("#/$defs/"):]
    defs = root.get("$defs") or {}
    if name not in defs:
        raise SchemaError(f"$ref to a missing definition {name!r}")
    return defs[name]


def errors(value: Any, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Every place ``value`` does not meet ``schema``, as ``path: problem``."""
    root = schema if root is None else root
    if not isinstance(schema, dict):
        raise SchemaError(f"{path}: a schema must be an object")
    unknown = set(schema) - KEYWORDS
    if unknown:
        raise SchemaError(f"{path}: unsupported schema keywords {sorted(unknown)}")
    if "$ref" in schema:
        return errors(value, _resolve(root, schema["$ref"]), root, path)
    out: list[str] = []
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if any(n not in TYPES for n in names):
            raise SchemaError(f"{path}: unsupported type {schema['type']!r}")
        if not any(TYPES[n](value) for n in names):
            return [f"{path}: expected {'/'.join(names)}, got {type(value).__name__}"]
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        out.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and not any(value == e and type(value) is type(e) for e in schema["enum"]):
        out.append(f"{path}: {value!r} is not one of {schema['enum']!r}")
    if TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{path}: {value!r} is under the minimum {schema['minimum']!r}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{path}: {value!r} is over the maximum {schema['maximum']!r}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            out.append(f"{path}: {value!r} is not over {schema['exclusiveMinimum']!r}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            out.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{path}: {value!r} does not match {schema['pattern']!r}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                out.extend(errors(item, schema["items"], root, f"{path}[{i}]"))
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                out.append(f"{path}: missing {name!r}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        if extra not in (True, False):
            raise SchemaError(f"{path}: additionalProperties must be true or false")
        for name, item in value.items():
            if name in props:
                out.extend(errors(item, props[name], root, f"{path}.{name}"))
            elif extra is False:
                out.append(f"{path}: unexpected {name!r}")
    return out


def check_definitions(root: dict) -> None:
    """Walk every subschema once, so an unsupported keyword anywhere is refused
    before any file is judged by the schema."""
    def walk(schema, path):
        if not isinstance(schema, dict):
            raise SchemaError(f"{path}: a schema must be an object")
        unknown = set(schema) - KEYWORDS
        if unknown:
            raise SchemaError(f"{path}: unsupported schema keywords {sorted(unknown)}")
        if "$ref" in schema:
            _resolve(root, schema["$ref"])
        for name, sub in (schema.get("properties") or {}).items():
            walk(sub, f"{path}.{name}")
        if isinstance(schema.get("items"), dict):
            walk(schema["items"], f"{path}[]")
        for name, sub in (schema.get("$defs") or {}).items():
            walk(sub, f"#/$defs/{name}")
    walk(root, "$")
