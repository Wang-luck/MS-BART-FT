# preprocess/custom_fp_to_tsv.py
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd

# =========================
# 关键：把项目根目录加入 sys.path
# 这样才能 import preprocess.fp_pred_main
# =========================
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from preprocess.fp_pred_main import MISTPredictor

# FP_CKPT = REPO_ROOT / "data" / "MassSpecGym" / "mist" / "mist.ckpt"
FP_CKPT = REPO_ROOT / "data" / "try_mist" / "mist.ckpt"
THRESHOLD = 0.11


def normalize_name(x: str) -> str:
    x = str(x)
    x = Path(x).name
    if x.endswith(".ms"):
        x = x[:-3]
    if x.endswith(".mgf"):
        x = x[:-4]
    return x


def main():
    parser = argparse.ArgumentParser(
        description="Run MIST fingerprint prediction on Custom.mgf + labels in a dataset directory."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=REPO_ROOT / "data" / "cluster_test_mgf",
        help="Directory with Custom.mgf and Custom_labels.tsv (default: data/Custom)",
    )
    args = parser.parse_args()

    dataset_dir = args.dataset_dir.resolve()
    mgf_input = dataset_dir / "cluster.mgf"
    labels_path = dataset_dir / "cluster_labels.tsv"
    res_dir = dataset_dir / "mist_pred"
    out_tsv = dataset_dir / "test" / "cluster_fps.tsv"

    if not FP_CKPT.exists():
        raise FileNotFoundError(f"MIST checkpoint not found: {FP_CKPT}")
    if not mgf_input.exists():
        raise FileNotFoundError(f"MGF not found: {mgf_input}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Labels not found: {labels_path}")

    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    print(f"REPO_ROOT = {REPO_ROOT}")
    print(f"MGF_INPUT = {mgf_input}")
    print(f"LABELS    = {labels_path}")
    print(f"FP_CKPT   = {FP_CKPT}")

    predictor = MISTPredictor(
        fp_ckpt=str(FP_CKPT),
        res_dir=str(res_dir),
        mgf_input=str(mgf_input),
        labels=str(labels_path),
    )

    print("Step 1/2: assign subformulae ...")
    predictor.assign_subformulae()

    print("Step 2/2: predict fingerprints ...")
    output_preds, output_names = predictor.predict()

    indices_list = [np.where(row > THRESHOLD)[0].tolist() for row in output_preds]
    name_to_fps = {
        normalize_name(name): fps_indices
        for name, fps_indices in zip(output_names, indices_list)
    }

    labels_df = pd.read_csv(labels_path, sep="\t")

    if "spec" not in labels_df.columns or "formula" not in labels_df.columns:
        raise ValueError(
            f"Labels file must contain columns ['spec', 'formula'], got: {list(labels_df.columns)}"
        )

    rows = []
    missing = []

    for _, row in labels_df.iterrows():
        identifier = normalize_name(row["spec"])
        formula = row["formula"]

        if identifier not in name_to_fps:
            missing.append(identifier)
            continue

        fps_indices = name_to_fps[identifier]
        fps_tokens = "".join([f"<fp{fp:04d}>" for fp in fps_indices])

        rows.append({
            "identifier": identifier,
            "fps": fps_tokens,
            "formula": formula,
        })

    out_df = pd.DataFrame(rows, columns=["identifier", "fps", "formula"])
    out_df.to_csv(out_tsv, sep="\t", index=False)

    print(f"Saved custom TSV to: {out_tsv}")
    print(f"Num rows: {len(out_df)}")

    if missing:
        print("Warning: these identifiers were in labels but not found in MIST outputs:")
        for x in missing:
            print("  -", x)


if __name__ == "__main__":
    main()
