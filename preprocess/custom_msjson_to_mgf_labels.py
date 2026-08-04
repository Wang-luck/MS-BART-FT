# preprocess/custom_msjson_to_mgf_labels.py
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd


def parse_ms_file(ms_path: Path) -> Dict:
    """
    Parse a simple .ms file like:
    >compound ZGC01
    >formula C15H14O6
    >parentmass 291.0860
    >ionization [M+H]+
    >ms2peaks
    55.0162 0.0023
    ...
    """
    meta = {
        "identifier": ms_path.stem,
        "formula": None,
        "parentmass": None,
        "ionization": None,
        "peaks": [],
    }

    if not ms_path.exists():
        return meta

    in_ms2 = False
    with ms_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith(">"):
                in_ms2 = False
                lower = line.lower()

                if lower.startswith(">compound"):
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        meta["identifier"] = parts[1].strip()

                elif lower.startswith(">formula"):
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        meta["formula"] = parts[1].strip()

                elif lower.startswith(">parentmass"):
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        try:
                            meta["parentmass"] = float(parts[1].strip())
                        except ValueError:
                            pass

                elif lower.startswith(">ionization"):
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        meta["ionization"] = parts[1].strip()

                elif lower.startswith(">ms2peaks"):
                    in_ms2 = True

                continue

            if in_ms2:
                parts = re.split(r"\s+", line)
                if len(parts) >= 2:
                    try:
                        mz = float(parts[0])
                        inten = float(parts[1])
                        meta["peaks"].append((mz, inten))
                    except ValueError:
                        pass

    return meta


def parse_json_file(json_path: Path) -> Dict:
    """
    Parse your json like:
    {
      "cand_form": "C15H14O6",
      "cand_ion": "[M+H]+",
      "output_tbl": {
         "mz": [...],
         "ms2_inten": [...]
      }
    }
    """
    meta = {
        "identifier": json_path.stem,
        "formula": None,
        "parentmass": None,
        "ionization": None,
        "peaks": [],
    }

    if not json_path.exists():
        return meta

    with json_path.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    meta["formula"] = obj.get("cand_form")
    meta["ionization"] = obj.get("cand_ion")

    output_tbl = obj.get("output_tbl", {})
    mzs = output_tbl.get("mz", [])
    intens = output_tbl.get("ms2_inten", [])
    if len(mzs) == len(intens):
        meta["peaks"] = [(float(m), float(i)) for m, i in zip(mzs, intens)]

    return meta


def merge_sources(ms_meta: Dict, json_meta: Dict) -> Dict:
    """
    Prefer .ms as primary source for identifier/parentmass/peaks,
    fallback to .json for formula/ionization/peaks when needed.
    """
    identifier = ms_meta.get("identifier") or json_meta.get("identifier")
    formula = ms_meta.get("formula") or json_meta.get("formula")
    parentmass = ms_meta.get("parentmass") or json_meta.get("parentmass")
    ionization = ms_meta.get("ionization") or json_meta.get("ionization")
    peaks = ms_meta.get("peaks") or json_meta.get("peaks") or []

    if not peaks:
        raise ValueError(f"No peaks found for {identifier}")

    if formula is None:
        raise ValueError(f"No formula found for {identifier}")

    if ionization is None:
        raise ValueError(f"No ionization found for {identifier}")

    # parentmass is strongly recommended; if missing, try rough estimate from max mz
    if parentmass is None:
        parentmass = max(mz for mz, _ in peaks)

    return {
        "identifier": identifier,
        "formula": formula,
        "parentmass": float(parentmass),
        "ionization": ionization,
        "peaks": peaks,
    }


def build_mgf_entry(sample: Dict) -> str:
    rows = [
        "BEGIN IONS",
        f"PEPMASS={sample['parentmass']}",
        f"FEATURE_ID={sample['identifier']}",
        f"TITLE={sample['identifier']}",
        f"ADDUCT={sample['ionization']}",
        f"PARENTMASS={sample['parentmass']}",
    ]
    for mz, inten in sample["peaks"]:
        rows.append(f"{mz} {inten}")
    rows.append("END IONS")
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Convert .ms (+ optional .json) to MGF and labels TSV for MS-BART."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/cluster_test_ms"),
        help="Directory containing .ms and optional .json (default: data/custom_raw)",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/cluster_test_mgf"),
        help="Output directory for Custom.mgf and Custom_labels.tsv (default: data/Custom)",
    )
    args = parser.parse_args()

    raw_dir = args.raw_dir
    out_dir = args.dataset_dir
    mgf_path = out_dir / "cluster.mgf"
    labels_path = out_dir / "cluster_labels.tsv"

    out_dir.mkdir(parents=True, exist_ok=True)

    ms_files = {p.stem: p for p in raw_dir.glob("*.ms")}
    json_files = {p.stem: p for p in raw_dir.glob("*.json")}

    all_ids = sorted(set(ms_files) | set(json_files))
    if not all_ids:
        raise FileNotFoundError(f"No .ms or .json files found in {raw_dir}")

    samples: List[Dict] = []
    label_rows: List[Dict] = []

    for sid in all_ids:
        ms_meta = parse_ms_file(ms_files[sid]) if sid in ms_files else {
            "identifier": sid, "formula": None, "parentmass": None, "ionization": None, "peaks": []
        }
        json_meta = parse_json_file(json_files[sid]) if sid in json_files else {
            "identifier": sid, "formula": None, "parentmass": None, "ionization": None, "peaks": []
        }

        sample = merge_sources(ms_meta, json_meta)
        samples.append(sample)

        label_rows.append({
            "spec": sample["identifier"],
            "formula": sample["formula"],
            "ionization": sample["ionization"],
            "dataset": "Custom",
            "compound": sample["identifier"],
            "parentmass": sample["parentmass"],
            "instrument": "unknown",
        })

    mgf_text = "\n\n".join(build_mgf_entry(s) for s in samples)
    mgf_path.write_text(mgf_text, encoding="utf-8")

    labels_df = pd.DataFrame(label_rows)
    labels_df = labels_df[
        ["spec", "formula", "ionization", "dataset", "compound", "parentmass", "instrument"]
    ]
    labels_df.to_csv(labels_path, sep="\t", index=False)

    print(f"Saved MGF to: {mgf_path}")
    print(f"Saved labels to: {labels_path}")
    print(f"Num samples: {len(samples)}")


if __name__ == "__main__":
    main()
