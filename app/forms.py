"""Small declarative form layer: field definitions, server-side validation and database option lists."""
import re
from datetime import datetime

from .db import q, scalar


class F:
    def __init__(self, name, label, type="text", req=False, options=None, fk=None, help="", default=None,
                 rows=3, step=None, hidden_in_form=False):
        self.name, self.label, self.type, self.req = name, label, type, req
        self.options, self.fk, self.help, self.default = options, fk, help, default
        self.rows, self.step, self.hidden_in_form = rows, step, hidden_in_form

    def choices(self):
        """[(value, label)] for select / fk fields."""
        if self.type == "select":
            return [(o, o.replace("_", " ").capitalize()) if isinstance(o, str) else o for o in self.options]
        if self.type == "fk":
            table, label = self.fk[0], self.fk[1]
            where = self.fk[2] if len(self.fk) > 2 else "1=1"
            return [(r["id"], r["lbl"]) for r in q(f"SELECT id, {label} AS lbl FROM {table} WHERE {where} ORDER BY lbl")]
        return []


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_form(fields, form):
    """Return (values, errors). Empty optional values become None."""
    vals, errs = {}, {}
    for f in fields:
        if f.hidden_in_form:
            continue
        raw = form.get(f.name, "")
        raw = raw.strip() if isinstance(raw, str) else raw
        if f.type == "bool":
            vals[f.name] = 1 if form.get(f.name) in ("1", "on", "true") else 0
            continue
        if raw in ("", None):
            if f.req:
                errs[f.name] = f"{f.label} is required."
            vals[f.name] = None
            continue
        try:
            if f.type in ("text", "email", "url"):
                if len(raw) > 500:
                    raise ValueError("is too long (max 500 characters)")
                if f.type == "email" and not EMAIL_RE.match(raw):
                    raise ValueError("must be a valid email address")
                vals[f.name] = raw
            elif f.type == "textarea":
                if len(raw) > 20000:
                    raise ValueError("is too long")
                vals[f.name] = raw
            elif f.type == "int":
                vals[f.name] = int(raw)
            elif f.type == "number":
                v = float(raw)
                if v != v or v in (float("inf"), float("-inf")):
                    raise ValueError("must be a number")
                vals[f.name] = v
            elif f.type == "date":
                datetime.strptime(raw, "%Y-%m-%d")
                vals[f.name] = raw
            elif f.type == "datetime":
                s = raw.replace("T", " ")
                if len(s) == 16:
                    s += ":00"
                datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                vals[f.name] = s
            elif f.type == "select":
                allowed = [c[0] for c in f.choices()]
                if raw not in allowed:
                    raise ValueError("has an invalid choice")
                vals[f.name] = raw
            elif f.type == "fk":
                table = f.fk[0]
                if scalar(f"SELECT COUNT(*) FROM {table} WHERE id=?", (int(raw),)) == 0:
                    raise ValueError("refers to a record that does not exist")
                vals[f.name] = int(raw)
            else:
                vals[f.name] = raw
        except ValueError as e:
            msg = str(e)
            if msg.startswith("invalid literal") or msg.startswith("could not convert") or "does not match" in msg:
                msg = "has an invalid value"
            errs[f.name] = f"{f.label} {msg}." if not msg.endswith(".") else f"{f.label} {msg}"
    return vals, errs


def form_value(f, row, form=None):
    """Value to prefill an input with."""
    if form is not None and f.name in form:
        return form.get(f.name)
    if row is not None and f.name in row.keys():
        v = row[f.name]
        if f.type == "datetime" and v:
            return str(v)[:16].replace(" ", "T")
        return v
    return f.default
