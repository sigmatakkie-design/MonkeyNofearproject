"""Static checks for the Unity scripts that a plain C# compile cannot catch.

  * every MonoBehaviour / ScriptableObject subclass must live in a file of the same name, otherwise
    Unity cannot serialize it in scenes/prefabs ("script class cannot be found")
  * at most one such class per file
  * Editor-only API (UnityEditor) must not be used in runtime scripts outside #if UNITY_EDITOR

Usage: python3 Tools/common/validate_scripts.py [project_root]
"""
import os, re, sys

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', '..'))
scripts = os.path.join(root, 'Assets')
UNITY_BASES = {'MonoBehaviour', 'ScriptableObject', 'Editor', 'EditorWindow', 'StateMachineBehaviour'}
class_re = re.compile(r'^\s*(?:public|internal)?\s*(?:sealed\s+|abstract\s+|partial\s+)*class\s+(\w+)\s*(?::\s*([\w\.<>, ]+))?', re.M)

# first pass: collect all classes and their bases so indirect subclasses are found
classes = {}
for dp, _, files in os.walk(scripts):
    for f in files:
        if f.endswith('.cs'):
            p = os.path.join(dp, f)
            src = open(p, encoding='utf-8').read()
            for m in class_re.finditer(src):
                bases = [b.strip().split('.')[-1] for b in (m.group(2) or '').split(',') if b.strip()]
                classes[m.group(1)] = (p, bases[0] if bases else None)

def is_unity_object(name, depth=0):
    if depth > 10 or name not in classes:
        return False
    base = classes[name][1]
    return base in UNITY_BASES or is_unity_object(base, depth + 1)

errors = []
per_file = {}
for name, (path, base) in classes.items():
    if is_unity_object(name) or base in UNITY_BASES:
        per_file.setdefault(path, []).append(name)
for path, names in per_file.items():
    fname = os.path.splitext(os.path.basename(path))[0]
    if fname not in names:
        errors.append(f'{os.path.relpath(path, root)}: no Unity class named {fname} (found {names})')
    extra = [n for n in names if n != fname]
    if extra:
        errors.append(f'{os.path.relpath(path, root)}: extra Unity classes {extra} must move to their own files')

for dp, _, files in os.walk(os.path.join(scripts, 'MonkeyNoFear', 'Scripts', 'Runtime')):
    for f in files:
        if not f.endswith('.cs'):
            continue
        p = os.path.join(dp, f)
        src = open(p, encoding='utf-8').read()
        if 'using UnityEditor' in src and '#if UNITY_EDITOR' not in src:
            errors.append(f'{os.path.relpath(p, root)}: UnityEditor used in runtime code without #if UNITY_EDITOR')

print(f'checked {len(classes)} classes, {sum(len(v) for v in per_file.values())} Unity objects')
for e in errors:
    print('ERROR', e)
sys.exit(1 if errors else 0)
