"""Configuration formats as canonical trees, plus effective-value rules.

A file can lie about the value an app uses. Each reader returns what the file says, and the effective-value
helpers below say how the app resolves a key, and what is unknown without the app's own defaults:

- JSON / JSONC (VS Code settings, keybindings, .code-workspace): comments and trailing commas are removed
  first. VS Code keys are flat ("editor.tabSize"). Effective value = workspace settings over user settings
  over the built-in default. The built-in default is not on disk, so an unset key is UNKNOWN_DEFAULT.
- Mozilla prefs.js (Thunderbird, Firefox): only user overrides are in the file (user_pref). Effective value =
  the override, else the built-in default from omni.ja, which is not on disk, so UNKNOWN_DEFAULT.
- msgFilterRules.dat (Thunderbird filters): rules with actions, parsed in order.
- dconf dump / gsettings values: the dconf database is binary and is not read. Effective value = the schema
  default from /usr/share/glib-2.0/schemas (the GNOME schema XML) when no dump is given. A dump, when given,
  overrides the default.
- INI (generic .conf/.ini): sections and key=value. The VLC configs are NOT read by this module: VLC is the
  held-out family and has no reader (see canon.HELD_OUT).
- GIMP gimprc: (name value) lines.
"""
import ast
import glob
import json
import os
import re
import xml.etree.ElementTree as ET

UNKNOWN_DEFAULT = 'UNKNOWN_DEFAULT'


# ---------------------------------------------------------------- JSON / JSONC

def strip_jsonc(text):
    """Remove // and /* */ comments and trailing commas, leaving string contents untouched."""
    out, i, n = [], 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == '\\' and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
        elif text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(ch)
            i += 1
    return _drop_trailing_commas(''.join(out))


def _drop_trailing_commas(text):
    """Remove a comma that is directly followed (after whitespace) by } or ]. String contents are not touched."""
    out, i, n = [], 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == '\\' and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif ch == ',':
            j = i + 1
            while j < n and text[j] in ' \t\r\n':
                j += 1
            if j < n and text[j] in '}]':
                i += 1
                continue
            out.append(ch)
        else:
            out.append(ch)
        i += 1
    return ''.join(out)


def read_json(raw_bytes):
    """Parse JSON or JSONC. Returns the object; raises ValueError if it is not valid after cleaning."""
    text = raw_bytes.decode('utf-8-sig')
    try:
        return json.loads(text)
    except ValueError:
        return json.loads(strip_jsonc(text))


def read_jsonl_keybindings(obj):
    """VS Code keybindings.json is a list of {key, command, when}. Keep order; '-cmd' removes a binding."""
    out = {}
    if not isinstance(obj, list):
        return {'bindings': {}}
    for i, item in enumerate(obj, 1):
        out[str(i)] = {'key': item.get('key'), 'command': item.get('command'), 'when': item.get('when')}
    return {'bindings': out}


def vscode_effective(key, user_settings, workspace_settings=None, builtin_defaults=None):
    """Effective VS Code setting: workspace > user > built-in default. UNKNOWN_DEFAULT when the built-in
    default is needed but not available."""
    if workspace_settings and key in workspace_settings:
        return workspace_settings[key], 'workspace'
    if user_settings and key in user_settings:
        return user_settings[key], 'user'
    if builtin_defaults is not None and key in builtin_defaults:
        return builtin_defaults[key], 'builtin'
    return UNKNOWN_DEFAULT, 'unknown'


# ---------------------------------------------------------------- Mozilla prefs.js

_PREF = re.compile(r'^\s*user_pref\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*(.*?)\s*\)\s*;\s*$')


def read_prefs_js(text):
    prefs = {}
    for line in text.splitlines():
        m = _PREF.match(line)
        if not m:
            continue
        key = json.loads('"' + m.group(1) + '"')
        raw = m.group(2)
        if raw in ('true', 'false'):
            val = raw == 'true'
        elif raw.startswith('"'):
            val = json.loads(raw)
        else:
            try:
                val = int(raw)
            except ValueError:
                try:
                    val = float(raw)
                except ValueError:
                    val = raw
        prefs[key] = val
    return {'user_prefs': prefs}


def prefs_effective(prefs_tree, key):
    """Effective Mozilla pref: the user override if present, else UNKNOWN_DEFAULT (defaults are in omni.ja)."""
    user = prefs_tree.get('user_prefs', {})
    if key in user:
        return user[key], 'user'
    return UNKNOWN_DEFAULT, 'unknown'


# ---------------------------------------------------------------- Thunderbird msgFilterRules.dat

def read_msg_filter_rules(text):
    rules = {}
    version = None
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or '=' not in line:
            continue
        key, _, val = line.partition('=')
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        if key == 'version':
            version = val
        elif key == 'name':
            current = {'name': val, 'enabled': None, 'type': None, 'condition': None, 'actions': {}}
            rules[str(len(rules) + 1)] = current
        elif current is None:
            continue
        elif key == 'enabled':
            current['enabled'] = val == 'yes'
        elif key == 'type':
            current['type'] = int(val)
        elif key == 'condition':
            current['condition'] = val
        elif key == 'action':
            current['actions'][str(len(current['actions']) + 1)] = {'action': val, 'value': None}
        elif key == 'actionValue' and current['actions']:
            last = str(len(current['actions']))
            current['actions'][last]['value'] = val
    for r in rules.values():
        r['matches_all_messages'] = bool(r['condition']) and r['condition'].startswith('ALL')
    return {'version': version, 'rules': rules}


# ---------------------------------------------------------------- INI (generic; VLC is held out)

def read_ini(text):
    sections = {}
    cur = ''
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('[') and line.endswith(']'):
            cur = line[1:-1]
            sections.setdefault(cur, {})
            continue
        key, sep, val = line.partition('=')
        if not sep:
            continue
        sections.setdefault(cur, {})[key.strip()] = val.strip()
    return {'sections': sections}


# ---------------------------------------------------------------- dconf / GVariant

def _gvariant(text):
    if text is None:
        return None
    t = text.strip()
    try:
        return ast.literal_eval(t.replace('true', 'True').replace('false', 'False'))
    except (ValueError, SyntaxError):
        return t


def read_dconf_dump(text):
    db = {}
    section = ''
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            continue
        key, sep, val = line.partition('=')
        if sep:
            db.setdefault(section, {})[key.strip()] = _gvariant(val)
    return {'values': db}


_SCHEMA_CACHE = {}


def gsettings_schema_defaults(schema_dirs=('/usr/share/glib-2.0/schemas',)):
    """{schema id: {key: default}} from the GNOME schema XML files (defaults only)."""
    if _SCHEMA_CACHE:
        return _SCHEMA_CACHE
    for d in schema_dirs:
        for path in glob.glob(os.path.join(d, '*.gschema.xml')):
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            for schema in root.iter('schema'):
                sid = schema.get('id')
                keys = _SCHEMA_CACHE.setdefault(sid, {})
                for k in schema.iter('key'):
                    dflt = k.find('default')
                    keys[k.get('name')] = _gvariant(dflt.text) if dflt is not None else UNKNOWN_DEFAULT
    return _SCHEMA_CACHE


def gsettings_effective(schema, key, dconf_values=None):
    """Effective GNOME setting: the dconf value if a dump is given, else the schema default."""
    if dconf_values and schema in dconf_values and key in dconf_values[schema]:
        return dconf_values[schema][key], 'dconf'
    defaults = gsettings_schema_defaults()
    if schema in defaults and key in defaults[schema]:
        return defaults[schema][key], 'schema-default'
    return UNKNOWN_DEFAULT, 'unknown'


# ---------------------------------------------------------------- GIMP gimprc

def read_gimprc(text):
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith('(') or ')' not in line:
            continue
        inner = line[1:line.rindex(')')].strip()
        name, _, val = inner.partition(' ')
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val in ('yes', 'no'):
            val = val == 'yes'
        else:
            try:
                val = int(val)
            except ValueError:
                pass
        values[name] = val
    return {'settings': values}


# ---------------------------------------------------------------- Python source

def read_python(text):
    tree = ast.parse(text)
    functions, module_stmts = {}, []
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            body = [ast.unparse(s) for s in stmt.body]
            whiles = [[ast.unparse(s) for s in n.body] for n in ast.walk(stmt) if isinstance(n, ast.While)]
            functions[stmt.name] = {'statements': body, 'while_bodies': whiles}
        else:
            module_stmts.append(ast.unparse(stmt))
    return {'functions': functions, 'module_statements': module_stmts}
