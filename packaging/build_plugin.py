"""Assemble the Understudy MCP server into a Copilot plugin bundle.

This produces a Teams app style zip that points Copilot at the MCP server. The
manifest in manifest.template.json follows the documented Teams app shape, but
the Copilot and Cowork plugin schema is in preview and changes, so validate the
values against your tenant's current developer docs, and supply your own
color.png (192 by 192) and outline.png (32 by 32) icons, before sideloading.

Build it with:  python -m packaging.build_plugin
"""

from __future__ import annotations

import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))


def build(output_path: str = "understudy_plugin.zip", manifest_path: str = "", icon_dir: str = "") -> str:
    manifest_path = manifest_path or os.path.join(HERE, "manifest.template.json")
    icon_dir = icon_dir or HERE

    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    color = os.path.join(icon_dir, "color.png")
    outline = os.path.join(icon_dir, "outline.png")
    missing = [path for path in (color, outline) if not os.path.exists(path)]
    if missing:
        raise FileNotFoundError(
            "add the required plugin icons before packaging: " + ", ".join(missing)
        )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
        bundle.write(color, "color.png")
        bundle.write(outline, "outline.png")
    return output_path


if __name__ == "__main__":
    print("built " + build())
