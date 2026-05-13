"""In-place mutation helpers for erwin DM internal flat-array files.

Used by the /quality/fix endpoints when the user uploaded an erwin native
JSON: instead of returning the normalized MetaMart catalog (which erwin DM
can't open), we apply the rename to the original flat array so the
downloaded result is still a valid erwin model file.

Type and property codes are duplicated from `adapters.py` rather than
imported, to keep this module standalone — if erwin's ontology surprises
us, both sides need updating anyway and the duplication makes that
obvious in code review.
"""
from __future__ import annotations

# O_Ids in erwin DM files are NOT globally unique — each Alter-Schema /
# Diagram / Entity namespace can reuse the same numeric O_Id. So every
# rename must scope the lookup by O_Type as well, otherwise we mutate the
# first match (typically the wrong one).
_ERWIN_TYPE_ENTITY = {"1075838979", "1075839059"}
_ERWIN_TYPE_ATTRIBUTE = "1075838981"
_ERWIN_TYPE_KEY_MEMBER = "1075838986"
_ERWIN_PROP_KEY_MEMBER_ATTR = "1075849017"
# Canonical Name override property — paired with the top-level Name field.
_ERWIN_PROP_NAME = "1073742126"


def _set_name(obj: dict, new_name: str) -> None:
    """Update both the top-level Name field and the canonical Name property."""
    obj["Name"] = new_name
    props = obj.get("Properties")
    if not isinstance(props, dict):
        obj["Properties"] = {_ERWIN_PROP_NAME: [new_name, "kString"]}
        return
    existing = props.get(_ERWIN_PROP_NAME)
    if isinstance(existing, list) and len(existing) >= 2:
        props[_ERWIN_PROP_NAME] = [new_name, existing[1]]
    else:
        props[_ERWIN_PROP_NAME] = [new_name, "kString"]


def rename_entity(items: list, oid: str, new_name: str) -> bool:
    """Rename the entity object (O_Type 1075838979 or 1075839059) with this O_Id.

    Returns True if exactly one matching entity was found. Other objects with
    the same O_Id but different O_Type (erwin reuses O_Ids across namespaces
    like Alter-Schema-Generation and Diagram_Proxy) are not touched.
    """
    found = False
    for it in items:
        if (
            isinstance(it, dict)
            and it.get("O_Id") == oid
            and it.get("O_Type") in _ERWIN_TYPE_ENTITY
        ):
            _set_name(it, new_name)
            found = True
    return found


def rename_attribute(items: list, attr_oid: str, new_name: str) -> bool:
    """Rename an attribute (O_Type 1075838981) plus its key-member references.

    Key members (O_Type 1075838986) reference the attribute by O_Id in
    Property 1075849017, so the structural linkage stays intact either way.
    We update the spelled-out copy on the member too so diagrams and DDL
    generation use the new name everywhere instead of leaving a confusing
    mismatch behind.
    """
    found_attr = False
    for it in items:
        if (
            isinstance(it, dict)
            and it.get("O_Id") == attr_oid
            and it.get("O_Type") == _ERWIN_TYPE_ATTRIBUTE
        ):
            _set_name(it, new_name)
            found_attr = True
    if not found_attr:
        return False

    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("O_Type") != _ERWIN_TYPE_KEY_MEMBER:
            continue
        props = it.get("Properties")
        if not isinstance(props, dict):
            continue
        ref = props.get(_ERWIN_PROP_KEY_MEMBER_ATTR)
        member_attr_oid = None
        if isinstance(ref, list) and ref:
            member_attr_oid = str(ref[0])
        if member_attr_oid == attr_oid:
            _set_name(it, new_name)
    return True
