"""Cross-checks names used in C# against what the asset pipelines produced:
   * sound group names (PlayAt / Play2D / CreateLoop / Say / SoundAt / *Sound fields / voiceLoop)
   * animation clip names used per creature script against creatures_manifest.json
Usage: python3 Tools/common/check_references.py [project_root]
"""
import json, os, re, sys

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', '..'))
scripts = os.path.join(root, 'Assets', 'MonkeyNoFear', 'Scripts')
audio = json.load(open(os.path.join(root, 'Assets/MonkeyNoFear/Audio/audio_manifest.json')))

call_re = re.compile(r'(?:PlayAt|Play2D|CreateLoop|Say|SoundAt)\(\s*"([a-z0-9_]+)"')
field_re = re.compile(r'(?:Sound|Loop|sound|loop|voiceLoop|hitSound|breakSound|finalBreakSound)\s*=\s*"([a-z0-9_]+)"')
ternary_re = re.compile(r'\?\s*"([a-z0-9_]+)"\s*:\s*"([a-z0-9_]+)"')
used = {}
for dp, _, files in os.walk(scripts):
    for f in files:
        if not f.endswith('.cs'):
            continue
        src = open(os.path.join(dp, f), encoding='utf-8').read()
        for m in call_re.finditer(src):
            used.setdefault(m.group(1), set()).add(f)
        for m in field_re.finditer(src):
            used.setdefault(m.group(1), set()).add(f)
        for line in src.splitlines():
            if any(k in line for k in ('PlayAt', 'Play2D', 'Sound', 'snd')):
                for m in ternary_re.finditer(line):
                    for g in m.groups():
                        used.setdefault(g, set()).add(f)

missing = {k: v for k, v in used.items() if k not in audio and not k.startswith('hand_tap_') or (k.startswith('hand_tap_') and k not in audio)}
missing = {k: v for k, v in missing.items() if k not in audio}
print(f'{len(used)} sound names referenced, {len(audio)} in manifest')
for k, v in sorted(missing.items()):
    print('MISSING SOUND', k, sorted(v))

# surface tap sounds are built dynamically
for k in ['hand_tap_metal', 'hand_tap_wood', 'hand_tap_foliage', 'hand_tap_mud', 'hand_tap_ground', 'hand_tap_rock',
          'item_drop_metal', 'item_drop_wood', 'item_drop_soft', 'item_drop_stone']:
    if k not in audio:
        print('MISSING SOUND (dynamic)', k)

cm_path = os.path.join(root, 'Assets/MonkeyNoFear/Art/Models/Creatures/creatures_manifest.json')
if os.path.exists(cm_path):
    cm = json.load(open(cm_path))
    play_re = re.compile(r'(?:Play|PlayOnce|SyncSpeed|EventTime|Has|Info)\(\s*"([a-z_]+)"')
    per_script = {'Hollowback.cs': ['Hollowback'], 'Falsekin.cs': ['Falsekin', 'Rabbit'], 'WildAnimal.cs': ['Rabbit', 'Boar', 'Gloomrat'],
                  'CeilingClerk.cs': ['CeilingClerk'], 'Borer.cs': ['Borer'], 'LanternMourner.cs': ['LanternMourner'], 'Gaunt.cs': ['Gaunt']}
    for dp, _, files in os.walk(scripts):
        for f in files:
            if f not in per_script:
                continue
            src = open(os.path.join(dp, f), encoding='utf-8').read()
            clips = set(play_re.findall(src))
            for creature in per_script[f]:
                if creature not in cm:
                    print(f'(creature {creature} not delivered yet)')
                    continue
                have = set(cm[creature]['clips'])
                lacking = sorted(c for c in clips if c not in have)
                if lacking:
                    print(f'CLIPS used by {f} missing on {creature}: {lacking}')
