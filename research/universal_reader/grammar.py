"""Extended predicate grammar for the universal reader.

specexec.py (frozen, imported read-only) parses 206 of the 302 must-predicates in the Exp 5 specs. This module
subclasses its parser, so every predicate the frozen parser accepts gets the same AST (checked by the unit tests).
The forms the frozen parser rejects get new nodes:

  regex literals (/.../flags after matches, contains or does_not_match), keyword arguments (name=value), dict
  literals, tuples, ranges as arguments (pages(1..25)), bitwise & and | (parsed, evaluated as UNSUPPORTED), ternary
  (c ? a : b), contains, does_not_match, is / is not, similarity (with an optional threshold), ordered_by, a
  generator with several for clauses, a filter (items where cond, or .where(cond)), a statement form if C: B,
  statement sequences separated by ';' with let NAME = expr and expr as NAME bindings, 'for each v in it: body',
  the set operators as calls (set_equal(a, b)), keywords used as attribute names (x.includes(...)), and an
  'of DOC' clause after a quantifier.

Two forms are not parsed into an executable node:
  'probe ...' predicates run a live app or command. They are kept as ('live', text, reason).
  Anything else the grammar rejects is kept as ('prose', text, reason): natural language, or syntax with no
  defined meaning. Both evaluate to UNSUPPORTED, never to an error.
"""
import importlib.util
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_FROZEN_NAME = 'specexec_frozen'
_FROZEN_PATH = os.path.join(_HERE, '..', 'exp6-executed', 'specexec.py')
# One module object for the frozen executor, shared with evaluate.py, so Unsupported and ReaderMiss are the same
# classes everywhere.
if _FROZEN_NAME in sys.modules:
    _frozen = sys.modules[_FROZEN_NAME]
else:
    _spec = importlib.util.spec_from_file_location(_FROZEN_NAME, _FROZEN_PATH)
    _frozen = importlib.util.module_from_spec(_spec)
    sys.modules[_FROZEN_NAME] = _frozen
    _spec.loader.exec_module(_frozen)

Unsupported = _frozen.Unsupported
ReaderMiss = _frozen.ReaderMiss
strip_comment = _frozen.strip_comment

NEW_KEYWORDS = {'contains', 'does_not_match', 'ordered_by', 'is', 'as'}
KEYWORDS = set(_frozen.KEYWORDS) | NEW_KEYWORDS
OP_WORDS = {'matches', 'startswith', 'endswith', 'set_equal', 'multiset_equal', 'subset_of', 'includes',
            'includes_any', 'equals_by_character', 'contains', 'does_not_match'}

TOKEN = re.compile(r"""
 (?P<ws>\s+)
|(?P<num>0o[0-7]+|\d+\.\d+|\d+)
|(?P<str>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
|(?P<id>[A-Za-z_][A-Za-z0-9_]*)
|(?P<op>==|!=|<=|>=|\.\.|[<>+\-*/().,\[\]{}:;=?&|])
""", re.X)
REGEX = re.compile(r'/((?:[^/\\\n]|\\.)*)/([a-zA-Z]*)')
REGEX_AFTER = {'matches', 'contains', 'does_not_match'}
PROBE = re.compile(r'probe\b')


def tokenize(src):
    out, pos = [], 0
    while pos < len(src):
        if src[pos] == '/' and out and out[-1][0] == 'kw' and out[-1][1] in REGEX_AFTER:
            m = REGEX.match(src, pos)
            if not m:
                raise Unsupported(f"unterminated regex at {src[pos:pos + 20]!r}")
            out.append(('regex', (m.group(1), m.group(2))))
            pos = m.end()
            continue
        m = TOKEN.match(src, pos)
        if not m:
            raise Unsupported(f"cannot tokenize at {src[pos:pos + 20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == 'ws':
            continue
        val = m.group(kind)
        # a word after a dot is an attribute name even when it is a keyword (x.includes, x.where)
        if kind == 'id' and val in KEYWORDS and out[-1:] != [('op', '.')]:
            kind = 'kw'
        out.append((kind, val))
    out.append(('eof', None))
    return out


class Parser(_frozen.Parser):
    def __init__(self, src):
        self.t = tokenize(src)
        self.i = 0

    # ---- statements: a sequence separated by ';'
    def statement(self):
        if self.is_('id', 'let') and self.is_('id', None, 1) and self.is_('op', '=', 2):
            self.take()
            name = self.take()[1]
            self.take()
            return ('let', name, self.or_())
        if self.is_('kw', 'if'):  # if COND: BODY, the same as not COND or BODY
            self.take()
            cond = self.or_()
            self.expect('op', ':')
            return ('or', ('not', cond), self.or_())
        e = self.or_()
        if self.is_('kw', 'as'):
            self.take()
            return ('let', self.expect('id')[1], e)
        return e

    def statements(self):
        out = [self.statement()]
        while self.is_('op', ';'):
            self.take()
            if self.is_('eof'):
                break
            out.append(self.statement())
        if not self.is_('eof'):
            raise Unsupported(f"trailing tokens at {self.peek()[1]!r}")
        return out

    # ---- operators
    def or_(self):
        l = super().or_()
        if self.is_('op', '?'):
            self.take()
            a = self.or_()
            self.expect('op', ':')
            b = self.or_()
            return ('ternary', l, a, b)
        return l

    def cmp(self):
        l = self.add()
        while True:
            t = self.peek()
            if t[0] == 'op' and t[1] in ('==', '!=', '<', '<=', '>', '>='):
                self.take(); l = ('cmp', t[1], l, self.add())
            elif self.is_('kw', 'in'):
                self.take(); l = ('in', l, self.rhs_with_range())
            elif self.is_('kw', 'not') and self.is_('kw', 'in', 1):
                self.take(); self.take(); l = ('not', ('in', l, self.rhs_with_range()))
            elif self.is_('kw', 'within'):
                self.take(); self.expect('op', '('); tol = self.or_(); self.expect('op', ')')
                l = ('within', l, tol, self.add())
            elif t[0] == 'kw' and t[1] in ('matches', 'startswith', 'endswith', 'set_equal', 'multiset_equal',
                                           'subset_of', 'includes', 'includes_any', 'equals_by_character',
                                           'contains', 'does_not_match'):
                self.take(); l = ('op', t[1], l, self.add())
            elif self.is_('kw', 'is'):
                self.take()
                negate = self.is_('kw', 'not')
                if negate:
                    self.take()
                l = ('is', l, self.add())
                if negate:
                    l = ('not', l)
            elif t[0] == 'id' and t[1] == 'similarity':  # infix; the call form similarity(a, b) is a primary
                self.take()
                op = thr = None
                if self.peek()[0] == 'op' and self.peek()[1] in ('>=', '>', '<=', '<'):
                    op = self.take()[1]
                    thr = self.add()
                l = ('similar', l, op, thr, self.add())
            elif self.is_('kw', 'ordered_by'):
                self.take()
                l = ('ordered', l, self.expect('id')[1])
            else:
                return l

    def mul(self):
        l = self.unary()
        while self.peek()[0] == 'op' and self.peek()[1] in ('*', '/', '&', '|'):
            op = self.take()[1]
            l = ('arith', op, l, self.unary())
        return l

    # ---- primaries
    def primary(self):
        t = self.peek()
        if t[0] == 'regex':
            self.take()
            return ('regex', t[1][0], t[1][1])
        if t[0] == 'kw' and t[1] in OP_WORDS and self.is_('op', '(', 1):  # set_equal(a, b) as a call
            self.take()
            return ('name', t[1])
        if t[0] == 'kw' and t[1] == 'for' and self.is_('id', 'each', 1):  # for each v in it [where c]: body
            self.take()
            self.take()
            var = self.expect('id')[1]
            self.expect('kw', 'in')
            it = self.rhs_with_range()
            cond = None
            if self.is_('kw', 'where'):
                self.take()
                cond = self.or_()
            self.expect('op', ':')
            return ('qstmt', 'all', var, it, cond, self.or_())
        if self.is_('op', '('):
            self.take()
            e = self.or_()
            if not self.is_('op', ','):
                self.expect('op', ')')
                return e
            items = [e]
            while self.is_('op', ','):
                self.take()
                if self.is_('op', ')'):
                    break
                items.append(self.or_())
            self.expect('op', ')')
            return ('tuple', items)
        if self.is_('op', '{'):
            self.take()
            pairs, items = [], []
            while not self.is_('op', '}'):
                k = self.or_()
                if self.is_('op', ':'):
                    self.take()
                    pairs.append((k, self.or_()))
                else:
                    items.append(k)
                if self.is_('op', ','):
                    self.take()
            self.take()
            if pairs and items:
                raise Unsupported('mixed dict and set literal')
            return ('dict', pairs) if pairs else ('set', items)
        return super().primary()

    # ---- calls: keyword arguments, ranges, generators with several for clauses, filters and quantifiers
    def args(self):
        self.expect('op', '(')
        if self.is_('op', ')'):
            self.take()
            return []
        if self.is_('id') and self.is_('op', '=', 1):  # keyword arguments only
            out = []
            while True:
                name = self.expect('id')[1]
                self.expect('op', '=')
                out.append(('kwarg', name, self.or_()))
                if self.is_('op', ','):
                    self.take()
                    continue
                self.expect('op', ')')
                return out
        first = self.or_()
        if self.is_('op', '..'):
            self.take()
            first = ('range', first, self.add())
        if self.is_('kw', 'for'):
            clauses = []
            while self.is_('kw', 'for'):
                self.take()
                var = self.expect('id')[1]
                self.expect('kw', 'in')
                it = self.or_()
                if self.is_('op', '..'):
                    self.take()
                    it = ('range', it, self.add())
                cond = None
                if self.is_('kw', 'if'):
                    self.take()
                    cond = self.or_()
                clauses.append((var, it, cond))
            self.expect('op', ')')
            if len(clauses) == 1:
                var, it, cond = clauses[0]
                return [('gen', first, var, it, cond)]
            return [('genm', first, clauses)]
        if self.is_('kw', 'where') or self.is_('op', ':'):
            if first[0] != 'in':
                if self.is_('kw', 'where'):  # a filter of a collection: count(items where cond)
                    self.take()
                    cond = self.or_()
                    self.expect('op', ')')
                    return [('filter', first, cond)]
                raise Unsupported("quantifier needs 'v in iterable'")
            if first[1][0] != 'name':
                raise Unsupported("quantifier variable must be a name")
            var, it = first[1][1], first[2]
            cond = None
            if self.is_('kw', 'where'):
                self.take()
                cond = self.or_()
            if not self.is_('op', ':'):  # no body: the condition after 'where' is the body
                self.expect('op', ')')
                return [('quant', var, it, None, cond if cond is not None else ('lit', True))]
            self.take()
            body = self.or_()
            self.expect('op', ')')
            return [('quant', var, it, cond, body)]
        args = [first]
        while self.is_('op', ','):
            self.take()
            if self.is_('id') and self.is_('op', '=', 1):
                name = self.take()[1]
                self.take()
                args.append(('kwarg', name, self.or_()))
            else:
                args.append(self.or_())
        self.expect('op', ')')
        return args

    def quant_stmt(self):
        """all|exists [NOUN] v in ITER [of DOC] [where COND] [: BODY]. Without a body the condition is the body."""
        kind = self.take()[1]
        if self.is_('id', None, 1):
            self.take()  # NOUN
        var = self.expect('id')[1]
        self.expect('kw', 'in')
        it = self.rhs_with_range()
        doc = None
        if self.is_('id', 'of'):
            self.take()
            doc = self.or_()
        cond = None
        if self.is_('kw', 'where'):
            self.take()
            cond = self.or_()
        if self.is_('op', ':'):
            self.take()
            node = ('qstmt', kind, var, it, cond, self.or_())
        else:
            node = ('qstmt', kind, var, it, None, cond if cond is not None else ('lit', True))
        return ('ctx', doc, node) if doc is not None else node


def _parse_statements(src):
    p = Parser(src)
    return p.statements()


def parse(src):
    """Parse one predicate. Never raises: a predicate the grammar cannot read is returned as a 'prose' node, and a
    live probe as a 'live' node, so the evaluator reports both as UNSUPPORTED."""
    try:
        stmts = _parse_statements(src)
    except Exception as e:  # any parse failure is a finding recorded in the node, not an exception
        if PROBE.match(src.lstrip()):
            return ('live', src, 'probe: runs a live app or command, not readable from a saved state')
        return ('prose', src, f'{type(e).__name__}: {e}')
    if len(stmts) == 1 and stmts[0][0] != 'let':
        return stmts[0]
    return ('seq', stmts)
