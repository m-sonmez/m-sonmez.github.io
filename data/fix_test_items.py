#!/usr/bin/env python3
"""
fix_test_items.py
=================
Clinically-Accurate Reconciliation & Standardisation Engine for `test_items.json`.

Usage:
    python fix_test_items.py --dry-run --verbose     # Detailed preview of all changes
    python fix_test_items.py --apply --verbose       # Create backup, apply & print full log
"""

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional


def format_decimal(val: Optional[Any]) -> Optional[str]:
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str or val_str in ("-", "None", "null"):
        return None
    try:
        return f"{float(val_str):.4f}"
    except ValueError:
        return val_str


def fix_dataset(
    file_path: str = "test_items.json",
    convert_tbil_bg: bool = False,
    verbose: bool = False,
):
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data: List[Dict[str, Any]] = json.load(f)

    fixed_data: List[Dict[str, Any]] = []
    modifications = 0
    mod_details = []
    category_counts = defaultdict(int)

    for idx, item in enumerate(data):
        fixed = deepcopy(item)
        code = (item.get("code") or "").strip()
        unit = (item.get("unit") or "").strip()
        name = (item.get("name") or "").strip()
        desc = (item.get("description") or "").strip()
        rmin = item.get("reference_min")
        rmax = item.get("reference_max")
        result = item.get("result")
        at_time = item.get("at")
        test_id = item.get("test_id")

        item_mods = []

        # --- 1. Blood Gas Total Bilirubin (TBIL-BG) ---
        if code == "TBIL-BG":
            if convert_tbil_bg:
                if result and float(result) > 10.0:
                    converted_res = float(result) / 17.1
                    fixed["result"] = f"{converted_res:.4f}"
                    fixed["unit"] = "mg/dL"
                    item_mods.append(
                        f"Converted unit & scale: {result} µmol/L -> {fixed['result']} mg/dL"
                    )
                    category_counts["TBIL-BG (Converted to mg/dL)"] += 1
            else:
                if unit == "mg/dL" and float(result or 0) > 10.0:
                    fixed["unit"] = "µmol/L"
                    item_mods.append(
                        f"Corrected unit label: 'mg/dL' -> 'µmol/L' (raw optical value: {result})"
                    )
                    category_counts["TBIL-BG (Unit corrected to µmol/L)"] += 1

        # --- 2. Standard Bicarbonate (SBC) Reference Range ---
        if code == "SBC":
            if rmin == "-3.0000" and rmax == "3.0000":
                fixed["reference_min"] = "21.0000"
                fixed["reference_max"] = "27.0000"
                item_mods.append(
                    "Corrected reference range: (-3.0000..3.0000) -> (21.0000..27.0000 mmol/L)"
                )
                category_counts["SBC (Reference range corrected)"] += 1

        # --- 3. PLCC Typo in Test #7 ---
        if code == "PLCC" and unit == "10^9/µL":
            fixed["unit"] = "10^9/L"
            item_mods.append("Corrected unit typo: '10^9/µL' -> '10^9/L'")
            category_counts["PLCC (Unit typo fixed)"] += 1

        # --- 4. PDW (%) vs PDW (fL) ---
        if code == "PDW":
            if unit == "%":
                fixed["name"] = "Trombosit Dağılım Genişliği (PDW-CV)"
                fixed["code"] = "PDW-CV"
                item_mods.append(
                    "Re-indexed parameter: 'PDW' (%) -> 'PDW-CV' (%) to separate from volumetric 'PDW' (fL)"
                )
                category_counts["PDW (Separated PDW-CV %)"] += 1
            elif unit == "fL":
                fixed["name"] = "Trombosit Dağılım Genişliği (PDW)"

        # --- 5. INR '-' unit ---
        if code == "INR" and unit in ("-", ""):
            fixed["unit"] = "INR"
            item_mods.append("Normalised unit: '-' -> 'INR'")
            category_counts["INR (Unit normalised)"] += 1

        # --- 6. NRBC Missing Description ---
        if code in ("NRBC#", "NRBC%") and desc == "-":
            fixed["description"] = "Hemogram"
            item_mods.append("Set panel description: '-' -> 'Hemogram'")
            category_counts["NRBC (Description fixed)"] += 1

        # --- 7. Standardize Count Units ---
        if unit == "10^3/µL" and code in (
            "BASO#",
            "EO#",
            "LYM#",
            "MONO#",
            "NEU#",
            "PLCC",
            "PLT",
            "WBC",
            "NRBC#",
        ):
            fixed["unit"] = "10^9/L"
            item_mods.append(f"Standardised unit: '10^3/µL' -> '10^9/L'")
            category_counts[f"{code} (Count unit standardised)"] += 1
        elif unit == "10^6/µL" and code == "RBC":
            fixed["unit"] = "10^12/L"
            item_mods.append("Standardised unit: '10^6/µL' -> '10^12/L'")
            category_counts["RBC (Count unit standardised)"] += 1

        # --- 8. Consistent 4-decimal formatting ---
        fixed["result"] = format_decimal(fixed.get("result"))
        fixed["reference_min"] = format_decimal(fixed.get("reference_min"))
        fixed["reference_max"] = format_decimal(fixed.get("reference_max"))

        if item_mods:
            modifications += 1
            mod_details.append(
                {
                    "index": idx,
                    "test_id": test_id,
                    "at": at_time,
                    "code": code,
                    "name": name,
                    "changes": item_mods,
                }
            )

        fixed_data.append(fixed)

    # --- Print Report ---
    print("\n" + "=" * 85)
    print("           CLINICAL INTEGRITY & RECONCILIATION AUDIT REPORT (v2)")
    print("=" * 85)
    print(f"Total Records Analyzed    : {len(data)}")
    print(f"Total Records Corrected   : {modifications}")
    print("-" * 85)

    print("\n📊 Breakdown by Category of Change:")
    for cat, count in sorted(
        category_counts.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  • {cat:<48} : {count:>3} records")

    print("\n" + "-" * 85)

    if verbose:
        print(
            f"Detailed Change Log (All {len(mod_details)} records):\n"
        )
        for i, m in enumerate(mod_details, start=1):
            print(
                f"[{i:>2}/{len(mod_details)}] Test #{m['test_id']:<3} | Time: {m['at']} | Code: {m['code']:<8} | Name: {m['name']}"
            )
            for c in m["changes"]:
                print(f"       └─ {c}")
    else:
        print(
            f"Sample Change Log (First 10 records - use --verbose to view all {len(mod_details)}):\n"
        )
        for i, m in enumerate(mod_details[:10], start=1):
            print(
                f"[{i:>2}] Test #{m['test_id']:<3} | Time: {m['at']} | Code: {m['code']:<8}"
            )
            for c in m["changes"]:
                print(f"       └─ {c}")

    print("=" * 85)
    return fixed_data


def main():
    parser = argparse.ArgumentParser(
        description="Fix clinical and structural discrepancies in test_items.json"
    )
    parser.add_argument(
        "--file", default="test_items.json", help="Path to test_items.json"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply and write changes to file"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed, comprehensive logs for all modified records",
    )
    parser.add_argument(
        "--convert-tbil-bg",
        action="store_true",
        help="Convert TBIL-BG from µmol/L to mg/dL (/17.1) instead of keeping µmol/L",
    )

    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        print("Please provide --dry-run (preview) or --apply (write).")
        sys.exit(0)

    fixed = fix_dataset(
        file_path=args.file,
        convert_tbil_bg=args.convert_tbil_bg,
        verbose=args.verbose,
    )

    if args.apply:
        path = Path(args.file)
        backup_path = path.with_suffix(
            f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        shutil.copy(path, backup_path)
        print(f"\n💾 Backup created at: '{backup_path}'")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fixed, f, ensure_ascii=False, indent=2)
        print(f"✨ Successfully saved corrected records to: '{path}'\n")
    else:
        print(
            "\n🔍 Dry-run complete. No files modified. Run with --apply to commit these repairs."
        )


if __name__ == "__main__":
    main()