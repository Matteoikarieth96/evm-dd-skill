"""Shared helpers for the evm-dd scripts: workspace resolution and input validation.

Everything that ends up in a file path, a URL or an HTML attribute goes through one of these checks first.
"""
import os
import re
import sys
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
    try:
        p = urlsplit(u)
    except ValueError:
        return None
    if p.scheme.lower() not in schemes or not p.netloc:
        return None
    return u


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
