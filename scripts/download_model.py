#!/usr/bin/env python3
"""Download pretrained semantic model for content risk detection.

Usage:
    python scripts/download_model.py
    python scripts/download_model.py --model shibing624/text2vec-base-chinese
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="下载语义检测模型")
    parser.add_argument(
        "--model", "-m",
        default="shibing624/text2vec-base-chinese",
        help="HuggingFace 模型名称（默认: shibing624/text2vec-base-chinese）"
    )
    parser.add_argument(
        "--cache-dir", "-c",
        default=None,
        help="模型缓存目录（默认: 系统默认）"
    )
    args = parser.parse_args()

    print(f"正在下载模型: {args.model}")
    print("这可能需要几分钟时间，取决于网络速度...\n")

    try:
        from transformers import AutoTokenizer, AutoModel

        print("下载 tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            args.model,
            cache_dir=args.cache_dir,
            trust_remote_code=True,
        )
        print("✓ Tokenizer 下载完成")

        print("下载模型权重...")
        model = AutoModel.from_pretrained(
            args.model,
            cache_dir=args.cache_dir,
            trust_remote_code=True,
        )
        print("✓ 模型下载完成")

        print(f"\n✅ 模型 '{args.model}' 已就绪，可以开始使用。")

    except ImportError:
        print("❌ 请先安装依赖: pip install transformers torch sentence-transformers")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print("\n提示：")
        print("  1. 检查网络连接")
        print("  2. 尝试使用镜像站: export HF_ENDPOINT=https://hf-mirror.com")
        print("  3. 手动下载模型文件到本地后使用 --cache-dir 指定路径")
        sys.exit(1)


if __name__ == "__main__":
    main()