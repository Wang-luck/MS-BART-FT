"""
将 mytcm 格式的 CSV（mz1~mz100 + Intensity1~Intensity100）转为 MGF 格式

用法:
    python preprocess/convert_csv_to_mgf.py \\
        --input data/mytcm/test.csv \\
        --output data/mytcm/mytcm.mgf \\
        --id_col ID \\
        --precursor_col PrecursorMass

参数:
    --input      输入的 CSV 文件路径
    --output     输出的 MGF 文件路径
    --id_col     样本 ID 列名 (默认: ID)
    --precursor_col  前体质量列名 (默认: PrecursorMass)
    --mz_prefix  m/z 列前缀 (默认: mz)
    --intensity_prefix  强度列前缀 (默认: Intensity)
    --max_peaks  最多峰值数量 (默认: 100)
    --adduct     电离方式 (默认: [M+H]+)
"""

import pandas as pd
import argparse


def csv_to_mgf(input_path, output_path, id_col, precursor_col,
               mz_prefix, intensity_prefix, max_peaks, adduct):
    df = pd.read_csv(input_path)

    mgf_entries = []
    for _, row in df.iterrows():
        spec_id = row[id_col]

        # 提取 m/z 和强度对
        peaks = []
        for i in range(1, max_peaks + 1):
            mz = row.get(f"{mz_prefix}{i}")
            intensity = row.get(f"{intensity_prefix}{i}")
            if pd.notna(mz) and pd.notna(intensity) and float(mz) > 0 and float(intensity) > 0:
                peaks.append((float(mz), float(intensity)))

        if not peaks:
            print(f"警告: {spec_id} 没有有效质谱峰，跳过")
            continue

        # 组装 MGF 条目
        entry = "BEGIN IONS\n"
        entry += f"FEATURE_ID={spec_id}\n"
        entry += f"PEPMASS={row[precursor_col]}\n"
        entry += f"adduct={adduct}\n"
        entry += "collision_energy=20\n"
        for mz_val, int_val in peaks:
            entry += f"{mz_val} {int_val}\n"
        entry += "END IONS"
        mgf_entries.append(entry)

    with open(output_path, "w") as f:
        f.write("\n\n".join(mgf_entries))

    print(f"完成: 从 {input_path} 生成 {len(mgf_entries)} 条质谱到 {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CSV (mz+Intensity) 转 MGF 格式")
    parser.add_argument("--input", required=True, help="输入 CSV 文件路径")
    parser.add_argument("--output", required=True, help="输出 MGF 文件路径")
    parser.add_argument("--id_col", default="ID", help="样本 ID 列名")
    parser.add_argument("--precursor_col", default="PrecursorMass", help="前体质量列名")
    parser.add_argument("--mz_prefix", default="mz", help="m/z 列前缀")
    parser.add_argument("--intensity_prefix", default="Intensity", help="强度列前缀")
    parser.add_argument("--max_peaks", type=int, default=100, help="最多峰值数量")
    parser.add_argument("--adduct", default="[M+H]+", help="电离方式")
    args = parser.parse_args()

    csv_to_mgf(
        input_path=args.input,
        output_path=args.output,
        id_col=args.id_col,
        precursor_col=args.precursor_col,
        mz_prefix=args.mz_prefix,
        intensity_prefix=args.intensity_prefix,
        max_peaks=args.max_peaks,
        adduct=args.adduct,
    )
