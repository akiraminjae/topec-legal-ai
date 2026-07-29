"""Shared, schema-tolerant XML parsing helpers for the law.go.kr / data.go.kr
family of APIs. Records are read generically (tag -> text) and fields are
looked up by trying several known candidate tag names, so a minor schema
revision on the provider's side degrades to a missing field instead of an
exception.
"""
import xml.etree.ElementTree as ET


def text_map(elem: ET.Element) -> dict[str, str]:
    """Flatten an XML record's direct children into a {tag: text} dict."""
    result: dict[str, str] = {}
    for child in elem:
        if child.text and child.text.strip():
            result[child.tag] = child.text.strip()
    return result


def first(d: dict[str, str], *candidates: str) -> str | None:
    for c in candidates:
        if d.get(c):
            return d[c]
    return None
