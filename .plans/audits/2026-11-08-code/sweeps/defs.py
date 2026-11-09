# Unreferenced top-level names in framework/: run from the repository root, `python3 .plans/audits/2026-11-08-code/sweeps/defs.py`.
# fw = hits in framework/ (1 = only its definition); all = hits anywhere scanned. A candidate list, never a verdict.
import ast, re, subprocess, sys, pathlib
root = pathlib.Path('.')
files = [p for p in root.glob('framework/**/*.py') if 'Apps' not in p.parts and '__pycache__' not in p.parts]
corpus_files = [p for p in list(root.glob('framework/**/*')) + list(root.glob('tests/**/*.py')) + list(root.glob('recipes/**/*')) + [root/'gjallarhorn.sh', root/'launch.sh', root/'Makefile'] + list(root.glob('framework/*.mk')) + list(root.glob('src/**/*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.root','.yoda','.pdf','.png')]
texts = {}
for p in corpus_files:
    try: texts[p] = p.read_text(encoding='utf-8')
    except Exception: pass
fw_text = {p:t for p,t in texts.items() if str(p).startswith('framework')}
out = []
for f in files:
    tree = ast.parse(f.read_text())
    names = []
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)): names.append((node.name,node.lineno,'def'))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name): names.append((t.id,node.lineno,'var'))
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub,(ast.FunctionDef,)) and not sub.name.startswith('__'):
                    names.append((sub.name, sub.lineno, 'meth'))
    for name,line,kind in names:
        rx = re.compile(r'(?<![A-Za-z0-9_])'+re.escape(name)+r'(?![A-Za-z0-9_])')
        fw = sum(len(rx.findall(t)) for t in fw_text.values())
        allc = sum(len(rx.findall(t)) for t in texts.values())
        if fw <= 1:
            out.append(f"{f}:{line} {kind} {name} fw={fw} all={allc}")
print("\n".join(out))
