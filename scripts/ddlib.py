"""Shared helpers for the evm-dd scripts: workspace resolution and input validation.

Everything that ends up in a file path, a URL or an HTML attribute goes through one of these checks first.
"""
import ipaddress
import math
import os
import re
import sys
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")  # X handles: letters, digits, underscore, max 15
ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
URL_FORBIDDEN = set('\x00\r\n\t "<>`\\')


def home():
    """Workspace root: $EVM_DD_HOME, default ~/evm-dd."""
    return os.path.realpath(os.path.expanduser(os.environ.get("EVM_DD_HOME", "~/evm-dd")))


def check_slug(s):
    if not isinstance(s, str) or not SLUG_RE.match(s):
        raise ValueError(f"invalid project slug {s!r}: lowercase letters, digits and hyphens, max 64 characters")
    return s


def check_handle(h):
    h = (h or "").strip().lstrip("@")
    if not HANDLE_RE.match(h):
        raise ValueError(f"invalid X handle {h!r}: letters, digits and underscore, max 15 characters")
    return h


def check_handles(csv):
    return [check_handle(x) for x in (csv or "").split(",") if x.strip()]


def check_date(s):
    datetime.strptime(s, "%Y-%m-%d")
    return s


def check_asset_name(name):
    """A file name inside assets/: no directories, no leading dot."""
    if not isinstance(name, str) or not ASSET_RE.match(name) or ".." in name:
        raise ValueError(f"invalid asset file name {name!r}: a plain file name inside assets/")
    return name


def safe_url(u, schemes=("http", "https")):
    """Return the URL if it is an absolute http(s) URL with a host and no characters that could break out of an
    HTML attribute; otherwise None. javascript:, data:, vbscript: and relative URLs are rejected."""
    if not isinstance(u, str):
        return None
    u = u.strip()
    if not u or any(c in URL_FORBIDDEN for c in u):
        return None
    if any(unicodedata.category(c) == "Cf" for c in u):  # bidi overrides, zero-width characters
        return None
    try:
        p = urlsplit(u)
        host = p.hostname or ""
    except ValueError:
        return None
    if p.scheme.lower() not in schemes or not p.netloc or not host:
        return None
    if "@" in p.netloc:  # https://official.example@other.example/ shows one host and opens another
        return None
    if not host.isascii():  # look-alike Unicode hosts; use the xn-- form if an IDN is genuinely needed
        return None
    try:
        ipaddress.ip_address(host.strip("[]"))
        return None  # IP-literal hosts (127.0.0.1, private ranges) never belong in a public report
    except ValueError:
        pass
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return None
    return u


def check_score(x):
    """A finite number between 1 and 10."""
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 1 <= x <= 10:
        raise ValueError(f"score {x!r} must be a finite number between 1 and 10")
    return x


IMAGE_MAGIC = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF8", "image/gif"))
MAX_LOGO_BYTES = 5 * 1024 * 1024


def read_asset(assets_dir, name):
    """Read a logo from assets/: plain file name, no symlinks, must resolve inside assets/, at most 5 MB,
    and the bytes must really be PNG, JPEG, GIF, WebP or SVG. Returns (mime, bytes)."""
    check_asset_name(name)
    base = os.path.realpath(assets_dir)
    path = os.path.join(assets_dir, name)
    if os.path.islink(path):
        raise ValueError(f"assets/{name} is a symbolic link; copy the real file into assets/ instead")
    real = os.path.realpath(path)
    if os.path.dirname(real) != base or not os.path.isfile(real):
        raise ValueError(f"assets/{name} is not a regular file inside assets/")
    if os.path.getsize(real) > MAX_LOGO_BYTES:
        raise ValueError(f"assets/{name} is larger than 5 MB")
    with open(real, "rb") as f:
        data = f.read()
    for magic, mime in IMAGE_MAGIC:
        if data.startswith(magic):
            return mime, data
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", data
    head = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if name.lower().endswith(".svg") and (head.startswith(b"<svg") or head.startswith(b"<?xml")) and b"<svg" in data[:4096].lower():
        return "image/svg+xml", data
    raise ValueError(f"assets/{name} is not a PNG, JPEG, GIF, WebP or SVG image")


def project_dir(arg, must_exist=True):
    """Resolve a project: an existing directory path (examples, tests), or a slug inside $EVM_DD_HOME/projects."""
    if os.sep in arg or arg.startswith("."):
        if os.path.isdir(arg):
            return os.path.realpath(arg)
        die(f"project directory not found: {arg}")
    try:
        slug = check_slug(arg)
    except ValueError as e:
        die(str(e))
    p = os.path.join(home(), "projects", slug)
    if must_exist and not os.path.isdir(p):
        die(f"project not found: {arg} (looked in {p})")
    return p


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)
