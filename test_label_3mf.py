#!/usr/bin/env python3
"""Check a label 3MF really is a valid two-colour 3MF.

``playdoh_label.py`` writes its 3MF by hand (see ``mesh_utils.write_color_3mf``)
rather than going through a library, so nothing stops a typo in the XML from
producing a file that trimesh happily round-trips but a slicer refuses. This
reads the file back with **lib3mf**, the 3MF Consortium's reference
implementation, in strict mode — the same parser Bambu Studio's "Standard 3MF
File Color Parsing" is built on — and asserts the things that make the label
print in two colours:

* the package parses in strict mode with no warnings,
* the ``<basematerials>`` group carries the expected number of distinct colours,
* every mesh object resolves to one of them via its object-level ``pid``/``pindex``,
* every part is manifold and correctly oriented (a slicer will not need to repair
  it), and
* the parts are assembled under a single build item, so the label arrives as one
  movable object.

Also verifies the Bambu/Orca ``Metadata/model_settings.config`` pins each part to
its own extruder, which is what makes the label open pre-split across filaments.

Usage::

    python test_label_3mf.py                       # checks the committed samples
                                                   # (labels *and* collar tags)
    python test_label_3mf.py path/to/label.3mf ...

Requires ``pip install lib3mf`` (not needed to *generate* labels, only to check
them).
"""
from __future__ import annotations

import glob
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

try:
    import lib3mf
except ImportError:                                    # pragma: no cover
    sys.exit("lib3mf missing - pip install lib3mf")

EXPECTED_COLOURS = 2                                   # border + name


def check(path: str) -> list[str]:
    """Return a list of problems with ``path`` (empty means it passed)."""
    problems: list[str] = []
    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    reader = model.QueryReader("3mf")
    reader.SetStrictModeActive(True)
    try:
        reader.ReadFromFile(path)
    except Exception as exc:                           # noqa: BLE001
        return [f"strict-mode parse failed: {exc}"]

    for i in range(reader.GetWarningCount()):
        problems.append(f"parser warning: {reader.GetWarning(i)}")

    # --- colours ----------------------------------------------------------
    # lib3mf addresses materials by 1-based *property id*, not by the 0-based
    # pindex written into the XML, so map through GetAllPropertyIDs().
    materials: dict[tuple[int, int], tuple[str, str]] = {}
    groups = model.GetBaseMaterialGroups()
    while groups.MoveNext():
        group = groups.GetCurrentBaseMaterialGroup()
        gid = group.GetResourceID()
        for prop_id in group.GetAllPropertyIDs():
            colour = group.GetDisplayColor(prop_id)
            materials[(gid, prop_id)] = (
                group.GetName(prop_id),
                f"#{colour.Red:02X}{colour.Green:02X}{colour.Blue:02X}",
            )

    distinct = {hexc for _, hexc in materials.values()}
    if len(distinct) != EXPECTED_COLOURS:
        problems.append(
            f"expected {EXPECTED_COLOURS} distinct colours, found "
            f"{len(distinct)} ({sorted(distinct)})")

    # --- objects ----------------------------------------------------------
    meshes, assemblies = [], []
    objects = model.GetObjects()
    while objects.MoveNext():
        obj = objects.GetCurrentObject()
        oid = obj.GetResourceID()
        if obj.IsMeshObject():
            meshes.append(oid)
            mesh = model.GetMeshObjectByID(oid)
            if not mesh.IsManifoldAndOriented():
                problems.append(f"object {oid} is not manifold+oriented")
            pid, prop_id, has_property = obj.GetObjectLevelProperty()
            if not has_property:
                problems.append(f"object {oid} has no object-level colour")
            elif (pid, prop_id) not in materials:
                problems.append(
                    f"object {oid} points at unknown material "
                    f"pid={pid} property={prop_id}")
        elif obj.IsComponentsObject():
            assemblies.append(oid)

    if len(meshes) != EXPECTED_COLOURS:
        problems.append(f"expected {EXPECTED_COLOURS} mesh parts, found {len(meshes)}")

    # each part should get its own colour, not all point at the same one
    assigned = set()
    objects = model.GetObjects()
    while objects.MoveNext():
        obj = objects.GetCurrentObject()
        if obj.IsMeshObject():
            pid, prop_id, has_property = obj.GetObjectLevelProperty()
            if has_property:
                assigned.add(materials.get((pid, prop_id), (None, None))[1])
    if len(assigned) != len(meshes):
        problems.append(f"parts share colours: {len(meshes)} parts, {len(assigned)} colours used")

    # --- build ------------------------------------------------------------
    items = model.GetBuildItems()
    build = []
    while items.MoveNext():
        build.append(items.GetCurrent().GetObjectResourceID())
    if len(build) != 1:
        problems.append(f"expected 1 build item, found {len(build)}")
    elif assemblies and build[0] not in assemblies:
        problems.append(f"build item {build[0]} is not the assembly {assemblies}")

    # --- Bambu native part config ----------------------------------------
    with zipfile.ZipFile(path) as zf:
        if "Metadata/model_settings.config" not in zf.namelist():
            problems.append("missing Metadata/model_settings.config")
        else:
            cfg = ET.fromstring(zf.read("Metadata/model_settings.config"))
            extruders = [
                md.get("value")
                for part in cfg.iter("part")
                for md in part.iter("metadata")
                if md.get("key") == "extruder"
            ]
            if sorted(extruders) != [str(i + 1) for i in range(EXPECTED_COLOURS)]:
                problems.append(
                    f"model_settings.config extruders {extruders}, expected "
                    f"{[str(i + 1) for i in range(EXPECTED_COLOURS)]}")

    return problems


def main(argv: list[str]) -> int:
    paths = argv[1:] or sorted(
        glob.glob(os.path.join("printable_files", "labels", "*.3mf"))
        + glob.glob(os.path.join("printable_files", "dogtags", "*.3mf")))
    if not paths:
        sys.exit("no 3MF files to check")

    failed = 0
    for path in paths:
        problems = check(path)
        if problems:
            failed += 1
            print(f"FAIL  {os.path.basename(path)}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {os.path.basename(path)}")

    print(f"\n{len(paths) - failed}/{len(paths)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
