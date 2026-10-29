"""Sound registry: every generator registers its sounds here with the metadata the
manifest and the verifier need (category, variants, loop, channels, duration hint)."""
from __future__ import annotations

SOUNDS: dict = {}


def sound(name, category, variants=0, loop=False, stereo=False, spatial=None, dur=None,
          desc="", norm=None, fin=0.0005, fout=0.03, trim=True):
    """Register a generator fn(rng, variant_index) -> np.ndarray (n,) mono or (n,2) stereo.

    variants: 0 -> single file without suffix, N>=1 -> files name_01..name_NN.
    norm: ('peak', dBFS) or ('rms', dBFS, ceiling_dBFS). Default: peak -1 dBFS for one-shots,
          RMS -24 dBFS (ceiling -3) for *_bed ambience.
    """
    if norm is None:
        norm = ("rms", -24.0, -3.0) if name.endswith("_bed") else ("peak", -1.0)
    if spatial is None:
        spatial = not stereo

    def deco(fn):
        if name in SOUNDS:
            raise ValueError("duplicate sound " + name)
        SOUNDS[name] = dict(name=name, category=category, variants=variants, loop=loop, stereo=stereo,
                            spatial=spatial, dur=dur, desc=desc, norm=norm, fn=fn, fin=fin, fout=fout,
                            trim=trim, module=fn.__module__)
        return fn
    return deco


def category(cat):
    def s(name, **kw):
        return sound(name, cat, **kw)
    return s


def file_names(spec):
    if spec["variants"] and spec["variants"] > 0:
        return ["%s_%02d.ogg" % (spec["name"], i + 1) for i in range(spec["variants"])]
    return [spec["name"] + ".ogg"]


def load_all():
    """Import every generator module (registers sounds)."""
    import gen_player, gen_tools, gen_bunker, gen_forest, gen_creatures, gen_mine, gen_music  # noqa: F401
    return SOUNDS
