"""Build every MONKEY NO FEAR creature, then validate the exported FBX files.

Usage (bpy as a module):   <python-with-bpy> build_all.py -- [--no-preview] [--only Rabbit,Hollowback]
Usage (Blender install):   blender -b -P build_all.py -- [--no-preview]

Each creature is built in its own process so no actions / data leak between FBX files
(the FBX exporter's "all actions" mode would otherwise pick up other creatures' actions).
"""
import os
import sys
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = [  # work order from the brief
    ("Rabbit", "creature_rabbit.py"),
    ("Hollowback", "creature_hollowback.py"),
    ("Falsekin", "creature_falsekin.py"),
    ("CeilingClerk", "creature_ceilingclerk.py"),
    ("Borer", "creature_borer.py"),
    ("LanternMourner", "creature_lanternmourner.py"),
    ("Boar", "creature_boar.py"),
    ("Gloomrat", "creature_gloomrat.py"),
    ("Gaunt", "creature_gaunt.py"),
]


def args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def interpreter_cmd(script, extra):
    exe = sys.executable
    try:
        import bpy  # noqa: F401
        bin_path = bpy.app.binary_path
    except Exception:
        bin_path = ""
    # running inside a real Blender binary -> re-launch blender in background mode
    if bin_path and os.path.basename(bin_path).lower().startswith("blender") and \
            os.path.abspath(bin_path) == os.path.abspath(exe):
        return [exe, "-b", "--factory-startup", "-P", script, "--"] + extra
    return [exe, script, "--"] + extra


def main():
    a = args()
    extra = [x for x in a if x == "--no-preview"]
    only = None
    if "--only" in a:
        only = set(a[a.index("--only") + 1].split(","))
    failed = []
    t0 = time.time()
    for name, script in ORDER:
        if only and name not in only:
            continue
        t1 = time.time()
        cmd = interpreter_cmd(os.path.join(HERE, script), extra)
        print("=== building %s: %s" % (name, " ".join(cmd)), flush=True)
        r = subprocess.run(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = [ln for ln in r.stdout.splitlines() if ln.startswith("[mnf]") or "Error" in ln or "Traceback" in ln]
        print("\n".join(lines[-12:]))
        if r.returncode != 0:
            failed.append(name)
            print(r.stdout[-3000:])
        print("=== %s done in %.0fs (exit %d)" % (name, time.time() - t1, r.returncode), flush=True)
    vcmd = interpreter_cmd(os.path.join(HERE, "validate_creatures.py"), [])
    r = subprocess.run(vcmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print("\n".join(ln for ln in r.stdout.splitlines() if not ln.startswith(("Info", "FBX", "  ")) or "VALID" in ln))
    print("total %.0fs, failed: %s" % (time.time() - t0, failed or "none"))
    if failed or r.returncode != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
