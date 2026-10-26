"""Preflight immutable JSON payloads before allocating serialization copies."""
from __future__ import annotations

import json
from itertools import chain
from typing import Any


class PayloadBudgetExceeded(ValueError):
    pass


def encode_json_payload(value: Any, *, sort_keys: bool = False, compact: bool = False,
                        newline: bool = False) -> bytes:
    """Encode a preflighted snapshot without a growing aggregate text buffer.

    The caller reserves the larger of two text copies and text plus UTF-8
    output. Joining iterencode chunks releases them before UTF-8 allocation.
    Container/scalar overhead remains separate from the payload budget.
    """
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=sort_keys,
                               separators=(",", ":") if compact else (", ", ": "))
    return "".join(chain(encoder.iterencode(value), ("\n",) if newline else ())).encode("utf-8")


def decoded_string_bytes(value: Any, seen: set[int] | None = None) -> int:
    """Count JSON string contents, sharing repeated references once.

    Container/scalar object overhead is outside the payload budget. Passing a
    set also records the string identities retained by a decoded payload.
    """
    seen = set() if seen is None else seen
    if isinstance(value, str):
        identity = id(value)
        if identity in seen:
            return 0
        seen.add(identity)
        highest = 0 if value.isascii() else ord(max(value))
        width = 4 if highest > 0xFFFF else 2 if highest > 0xFF else 1
        return len(value) * width
    if isinstance(value, dict):
        return sum(decoded_string_bytes(key, seen) + decoded_string_bytes(item, seen)
                   for key, item in value.items())
    if isinstance(value, list):
        return sum(decoded_string_bytes(item, seen) for item in value)
    return 0


def prepare_json_payload(value: Any, limit: int, parents: set[int] | None = None) -> tuple[Any, int, int, int]:
    """Detach containers and size UTF-8 bytes plus Python text character storage.

    Immutable source strings are shared, not copied. Container/object overhead
    is separate from the serialized-payload budget. Match json.dumps defaults
    with ensure_ascii=False and allow_nan=False.
    """
    if limit < 0:
        raise PayloadBudgetExceeded
    result: Any
    char_width = 1
    if isinstance(value, str):
        if len(value) + 2 > limit:
            raise PayloadBudgetExceeded
        size = len(value)
        if not value.isascii():
            highest = ord(max(value))
            char_width = 4 if highest > 0xFFFF else 2 if highest > 0xFF else 1
            if (len(value) + 2) * (1 + char_width) > limit:
                raise PayloadBudgetExceeded
            size = 0
            for char in value:
                code = ord(char)
                if 0xD800 <= code <= 0xDFFF:
                    raise ValueError("Unpaired surrogate in JSON payload")
                size += 1 + (code > 0x7F) + (code > 0x7FF) + (code > 0xFFFF)
        escapes = 2 + value.count('"') + value.count("\\")
        escapes += 5 * sum(value.count(chr(code)) for code in range(32))
        escapes -= 4 * sum(value.count(char) for char in "\b\f\n\r\t")
        size += escapes
        characters = len(value) + escapes
        result = value
    elif value is None or isinstance(value, (bool, int, float)):
        size = len(json.dumps(value, allow_nan=False))
        characters = size
        result = value
    elif isinstance(value, (dict, list, tuple)):
        parents = set() if parents is None else parents
        identity = id(value)
        if identity in parents:
            raise ValueError("Circular JSON payload")
        parents.add(identity)
        size = characters = 2
        try:
            if isinstance(value, dict):
                result = {}
                for index, (key, item) in enumerate(value.items()):
                    if not (key is None or isinstance(key, (str, bool, int, float))):
                        raise TypeError("Unsupported JSON object key")
                    key_text = key if isinstance(key, str) else json.dumps(key, allow_nan=False)
                    _, key_size, key_chars, key_width = prepare_json_payload(key_text, limit, parents)
                    separator = 2 + (2 if index else 0)
                    size += key_size + separator
                    characters += key_chars + separator
                    char_width = max(char_width, key_width)
                    detached, item_size, item_chars, item_width = prepare_json_payload(item, limit, parents)
                    result[key] = detached
                    size += item_size
                    characters += item_chars
                    char_width = max(char_width, item_width)
                    if size + characters * char_width > limit:
                        raise PayloadBudgetExceeded
            else:
                result = []
                for index, item in enumerate(value):
                    size += 2 if index else 0
                    characters += 2 if index else 0
                    detached, item_size, item_chars, item_width = prepare_json_payload(item, limit, parents)
                    result.append(detached)
                    size += item_size
                    characters += item_chars
                    char_width = max(char_width, item_width)
                    if size + characters * char_width > limit:
                        raise PayloadBudgetExceeded
        finally:
            parents.remove(identity)
    else:
        raise TypeError("Unsupported JSON value")
    if size + characters * char_width > limit:
        raise PayloadBudgetExceeded
    return result, size, characters, char_width

