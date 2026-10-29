"""mnf_registry - registry of texture-set generators (filled by the mnf_sets_* modules)."""
REGISTRY = {}


def texset(name, tiling_m, cutout=False, emission=False, notes="", kind="pbr", size=512):
    """Register a generator.

    kind: 'pbr'    -> fn(size) returns TexSet, written as <name>_A/_N/_M[/_E].png
          'normal' -> fn(size) returns TexSet, only <name>_N.png written
          'sprite' -> fn(size) returns RGBA float array, written as <name>.png
    """
    def deco(fn):
        REGISTRY[name] = dict(fn=fn, tiling_m=tiling_m, cutout=cutout, emission=emission,
                              notes=notes, kind=kind, size=size)
        return fn
    return deco
