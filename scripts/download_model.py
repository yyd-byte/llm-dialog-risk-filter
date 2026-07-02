#!/usr/bin/env python3
"""Download the semantic embedding model for content risk detection.

Downloads BAAI/bge-small-zh-v1.5 (24MB) by default, which provides
Chinese-optimized text embeddings used by SemanticDetector.

Usage:
    python scripts/download_model.py
    python scripts/download_model.py --model BAAI/bge-large-zh-v1.5
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="下载语义检测模型")
    parser.add_argument(
        "--model", "-m",
        default="BAAI/bge-small-zh-v1.5",
        help="HuggingFace 模型名称（默认: BAAI/bge-small-zh-v1.5）"
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
        from sentence_transformers import SentenceTransformer

        print("下载模型（首次运行会从 HuggingFace 下载，之后使用缓存）...")
        model = SentenceTransformer(
            args.model,
            cache_folder=args.cache_dir,
            trust_remote_code=True,
        )
        print(f"✓ 模型 '{args.model}' 已就绪，可以开始使用。")

        # Quick sanity check
        dim = model.get_sentence_embedding_dimension()
        print(f"  向量维度: {dim}")

    except ImportError:
        print("❌ 请先安装依赖: pip install sentence-transformers")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print("\n提示：")
        print("  1. 检查网络连接")
        print("  2. 尝试使用镜像站: set HF_ENDPOINT=https://hf-mirror.com")
        print("  3. 手动下载模型文件到本地后使用 --cache-dir 指定路径")
        sys.exit(1)


if __name__ == "__main__":
    main()