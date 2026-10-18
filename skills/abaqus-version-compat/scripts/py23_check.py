#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
py23_check.py - static check that an Abaqus script will run on BOTH kernels:
Python 2.7 (Abaqus 2023 and older) and Python 3.10 (Abaqus 2024 and newer).
Plain Python (2.7 or 3), no Abaqus needed:

    python py23_check.py script.py [more.py ...]   [--strict]
    python py23_check.py path/to/folder            (all *.py below it)

It is a regex linter, not a parser: it reports likely problems with line numbers and a fix.
Exit code 0 = no errors (warnings allowed unless --strict), 1 = errors found.

Checks
  ERROR  f-strings                           (SyntaxError on 2.7)
  ERROR  print statement                     (SyntaxError on 3)
  ERROR  'except X, e:'                      (SyntaxError on 3)
  ERROR  backticks, '<>' operator, 'exec "..."'
  ERROR  octal literals like 0777            (SyntaxError on 3)
  WARN   dict.iteritems/itervalues/iterkeys/has_key, xrange, raw_input, unicode(), basestring,
         long(), dict.keys()[i]
  WARN   integer division '/' between two int literals
  WARN   print(...) used without 'from __future__ import print_function' (prints a tuple on 2.7)
  WARN   'from abaqus import *' without restoring builtins sum/min/max/abs/round
         (the abaqus module shadows them with its own versions)
  WARN   master=/slave= keywords (renamed main=/secondary= in Abaqus 2022; the old names may
         be rejected by newer releases) and main=/secondary= (unknown before 2022)
  WARN   variable names that shadow abaqusConstants (ON, OFF, STANDARD, ...) or Abaqus
         modules (part, mesh, step, job, load, ...) as assignment targets
  INFO   open(..., encoding=) (keyword not in 2.7 open; use io.open)

OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import io
import os
import re
import sys

ABQ_MODULES = ('part', 'material', 'section', 'assembly', 'step', 'interaction', 'load', 'mesh',
               'job', 'sketch', 'visualization', 'xyPlot', 'displayGroupOdbToolset', 'connectorBehavior',
               'regionToolset', 'odbAccess')
ABQ_CONSTANTS = ('ON', 'OFF', 'STANDARD', 'EXPLICIT', 'MODEL', 'CARTESIAN', 'HEX', 'TET', 'QUAD',
                 'TRI', 'SWEEP', 'STRUCTURED', 'FREE', 'UNSET', 'DEFAULT', 'SOLID', 'SHELL')

RULES = [
    ('ERROR', re.compile(r'(?<![A-Za-z0-9_\'"])(?:[fF]|[fF][rR]|[rR][fF])(?:\'|")'),
     'f-string: SyntaxError on Python 2.7 (Abaqus <= 2023). Use "%s" % x or "{}".format(x).'),
    ('ERROR', re.compile(r'^\s*print\s+(?![\s(=])[^\s].*$|^\s*print\s*$'),
     'print statement: SyntaxError on Python 3 (Abaqus >= 2024). Use print(...) + from __future__ import print_function.'),
    ('ERROR', re.compile(r'^\s*except\s+[\w.]+(?:\s*\([^)]*\))?\s*,\s*\w+\s*:'),
     'except X, e: SyntaxError on Python 3. Use "except X as e:".'),
    ('ERROR', re.compile(r'`[^`\n]+`'), 'backtick repr: removed in Python 3. Use repr(x).'),
    ('ERROR', re.compile(r'\s<>\s'), '<> operator: removed in Python 3. Use !=.'),
    ('ERROR', re.compile(r'^\s*exec\s+["\'\w]'), 'exec statement: use exec(code).'),
    ('ERROR', re.compile(r'(?<![\w.])0[0-7]+(?![\w.xXoObBeEjJ])'), 'old octal literal: write 0o777.'),
    ('WARN', re.compile(r'\.(iteritems|itervalues|iterkeys|has_key)\s*\('),
     'Python-2-only dict method. Use .items()/.values()/.keys() or "k in d".'),
    ('WARN', re.compile(r'(?<![\w.])(xrange|raw_input|basestring|unicode|long)\s*\('),
     'Python-2-only builtin. Use range/input/str (or guard with try/except NameError).'),
    ('WARN', re.compile(r'\.keys\(\)\s*\['), 'dict.keys()[i] fails on Python 3. Use list(d.keys())[i].'),
    ('WARN', re.compile(r'(?<![\w.])\d+\s*/\s*\d+(?![\w.])'),
     'int / int: integer division on 2.7, float on 3. Write 1.0/2 or 1//2.'),
    ('WARN', re.compile(r'\b(master|slave)\s*='),
     'master=/slave= renamed main=/secondary= in Abaqus 2022. Support both (try new, fall back to old).'),
    ('INFO', re.compile(r'(?<![\w.])open\([^)]*encoding\s*='), 'open(..., encoding=) is not in 2.7: use io.open.'),
]

STRING_RE = re.compile(r'("""|\'\'\')')


def strip_comment(line):
    """Remove a trailing # comment that is not inside a string (good enough for linting)."""
    out, q = [], None
    i = 0
    while i < len(line):
        c = line[i]
        if q:
            if c == '\\':
                out.append(line[i:i + 2])
                i += 2
                continue
            if c == q:
                q = None
        elif c in '"\'':
            q = c
        elif c == '#':
            break
        out.append(c)
        i += 1
    return ''.join(out)


def blank_strings(line):
    """Replace the contents of simple string literals with x so rules do not fire inside them."""
    return re.sub(r'(?<![fF])(["\'])(?:\\.|(?!\1).)*\1', lambda m: m.group(1) + 'x' * 3 + m.group(1), line)


def check_file(path):
    issues = []
    try:
        src = io.open(path, encoding='utf-8', errors='replace').read()
    except (IOError, OSError) as exc:
        return [('ERROR', 0, 'cannot read: %s' % exc, '')]
    lines = src.splitlines()
    has_pf = 'print_function' in src
    uses_print_call = False
    in_doc = None
    depth = 0
    for n, raw in enumerate(lines, 1):
        line = raw
        if in_doc:                                   # inside a triple-quoted block
            if in_doc in line:
                line = line.split(in_doc, 1)[1]
                in_doc = None
            else:
                continue
        m = STRING_RE.search(line)
        while m:
            q = m.group(1)
            rest = line[m.end():]
            if q in rest:
                line = line[:m.start()] + 'x' + rest.split(q, 1)[1]
                m = STRING_RE.search(line)
            else:
                line = line[:m.start()]
                in_doc = q
                break
        code = strip_comment(line)
        if not code.strip():
            continue
        if re.search(r'(?<![\w.])print\s*\(', code):
            uses_print_call = True
        fstr_line = code
        code_ns = blank_strings(code)
        for sev, rx, msg in RULES:
            target = fstr_line if msg.startswith('f-string') else code_ns
            if rx.search(target):
                if msg.startswith('master=') and re.search(r'\bmain\s*=', src):
                    sev, msg = 'INFO', 'master=/slave= used as a fallback next to main=/secondary= (OK).'
                issues.append((sev, n, msg, raw.strip()))
        if depth == 0:                               # skip keyword-argument continuation lines
            for name in ABQ_MODULES + ABQ_CONSTANTS:
                if re.match(r'^\s*%s\s*=[^=]' % re.escape(name), code_ns) or \
                        re.match(r'^\s*for\s+%s\s+in\b' % re.escape(name), code_ns):
                    if name in ABQ_CONSTANTS:
                        issues.append(('WARN', n, '"%s" shadows an abaqusConstants symbol; rename the variable.'
                                       % name, raw.strip()))
                    elif re.search(r'^\s*import\s+%s\b' % re.escape(name), src, re.M):
                        issues.append(('INFO', n, '"%s" rebinds the imported Abaqus module %s; fine only if the '
                                       'module is not used afterwards.' % (name, name), raw.strip()))
        depth = max(0, depth + code_ns.count('(') + code_ns.count('[') + code_ns.count('{')
                    - code_ns.count(')') - code_ns.count(']') - code_ns.count('}'))
    if uses_print_call and not has_pf:
        issues.append(('WARN', 0, 'print(...) without "from __future__ import print_function": '
                       'print(a, b) prints a tuple on 2.7.', ''))
    if re.search(r'^\s*from\s+abaqus\s+import\s+\*', src, re.M):
        if not re.search(r'__builtin__|builtins', src):
            issues.append(('WARN', 0, '"from abaqus import *" shadows sum/min/max/abs/round. Restore them: '
                           'try: import builtins as _b / except ImportError: import __builtin__ as _b; '
                           'sum, min, max = _b.sum, _b.min, _b.max', ''))
    if re.search(r'\bmain\s*=', src) and not re.search(r'\bmaster\s*=', src) and \
            re.search(r'Tie\(|SurfaceToSurfaceContact|Coupling\(', src):
        issues.append(('INFO', 0, 'main=/secondary= only: fails on Abaqus 2021 and older (master=/slave=).', ''))
    return issues


def main(argv):
    strict = '--strict' in argv
    paths = [a for a in argv if not a.startswith('--')]
    if not paths:
        print(__doc__)
        return 2
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, fs in os.walk(p):
                dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
                files += [os.path.join(root, f) for f in sorted(fs) if f.endswith('.py')]
        else:
            files.append(p)
    n_err = n_warn = 0
    for f in files:
        iss = check_file(f)
        for sev, ln, msg, txt in iss:
            print('%s:%s: %s: %s%s' % (f, ln, sev, msg, ('\n    ' + txt) if txt else ''))
            n_err += sev == 'ERROR'
            n_warn += sev == 'WARN'
    print('py23_check: %d file(s), %d error(s), %d warning(s)' % (len(files), n_err, n_warn))
    return 1 if (n_err or (strict and n_warn)) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
