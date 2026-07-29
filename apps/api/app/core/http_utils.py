from urllib.parse import quote


def content_disposition(filename: str, disposition: str = "attachment") -> str:
    """Build a Content-Disposition header safe for non-ASCII (e.g. Korean) filenames.

    HTTP headers must be Latin-1; RFC 5987's filename* parameter carries the
    UTF-8 name, while filename= keeps an ASCII-safe fallback for older clients.
    """
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "download"
    encoded = quote(filename)
    return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
