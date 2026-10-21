# -*- coding: utf-8 -*-
"""Нормы JLCPCB/PCBWay (2 слоя, 1 oz) в .kicad_pro."""
import json, sys, os
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"meta": {"filename": os.path.basename(p), "version": 3}}
ds = d.setdefault("board", {}).setdefault("design_settings", {})
rules = ds.setdefault("rules", {})
rules.update({"min_clearance": 0.2, "min_connection": 0.2, "min_copper_edge_clearance": 0.3,
              "min_hole_clearance": 0.25, "min_hole_to_hole": 0.5, "min_track_width": 0.2,
              "min_through_hole_diameter": 0.3, "min_via_diameter": 0.5, "min_via_annular_width": 0.13,
              "min_text_height": 0.8, "min_text_thickness": 0.12, "min_silk_clearance": 0.0,
              "solder_mask_clearance": 0.05, "solder_mask_min_width": 0.1})
sev = ds.setdefault("rule_severities", {})
sev.update({"silk_overlap": "ignore", "silk_over_copper": "ignore", "text_height": "warning", "text_thickness": "warning",
            "footprint_type_mismatch": "ignore", "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
            "missing_courtyard": "ignore", "isolated_copper": "warning", "copper_sliver": "warning",
            "silk_edge_clearance": "ignore", "courtyards_overlap": "error", "copper_edge_clearance": "error",
            "solder_mask_bridge": "ignore", "pth_inside_courtyard": "ignore", "npth_inside_courtyard": "ignore",
            "footprint_symbol_mismatch": "ignore", "missing_footprint": "ignore", "extra_footprint": "ignore", "net_conflict": "ignore"})
ds["track_widths"] = [0.25, 0.5, 1.0]
ds["via_dimensions"] = [{"diameter": 0.7, "drill": 0.35}]
ns = d.setdefault("net_settings", {})
classes = ns.setdefault("classes", [])
if not any(c.get("name") == "Default" for c in classes):
    classes.append({"name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.7, "via_drill": 0.35,
                    "bus_width": 12, "wire_width": 6, "line_style": 0, "diff_pair_gap": 0.25, "diff_pair_width": 0.2,
                    "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3, "microvia_drill": 0.1,
                    "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"})
erc = d.setdefault("erc", {}).setdefault("rule_severities", {})
erc.update({"lib_symbol_issues": "ignore", "footprint_link_issues": "ignore", "lib_symbol_mismatch": "ignore"})
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("pro ok")
