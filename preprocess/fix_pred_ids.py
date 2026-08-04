#!/usr/bin/env python3
"""将预测 JSONL 的 sample_id 格式从 0001_20 转为 ZGC0001-20。"""

import argparse
import json
import re
from pathlib import Path


def fix_sample_id(sample_id: str) -> str:
    """转换 sample_id: 0001_20 -> ZGC0001-20"""
    # 如果已经是 ZGC 开头 + 连字符格式，跳过
    if re.match(r'^ZGC\d', sample_id) and '-' in sample_id:
        return sample_id

    # 解析数字部分和后缀
    match = re.match(r'^(\d+)_(.+)$', sample_id)
    if not match:
        return sample_id  # 无法解析则原样返回

    num_part, suffix = match.groups()
    return f'ZGC{num_part.zfill(4)}-{suffix}'


def main():
    parser = argparse.ArgumentParser(
        description='修复预测 JSONL 的 sample_id 格式'
    )
    parser.add_argument('input', type=Path, help='输入 JSONL 路径')
    parser.add_argument('output', type=Path, help='输出 JSONL 路径')
    args = parser.parse_args()

    count = 0
    changed = 0
    with args.input.open(encoding='utf-8') as fin, \
         args.output.open('w', encoding='utf-8') as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            old_id = record.get('sample_id', '')
            new_id = fix_sample_id(old_id)
            if new_id != old_id:
                changed += 1
                record['sample_id'] = new_id
            fout.write(json.dumps(record, ensure_ascii=False) + '\n')
            count += 1

    print(f'处理完成: {count} 条记录, {changed} 条 ID 已修改')
    print(f'输出: {args.output}')


if __name__ == '__main__':
    main()
