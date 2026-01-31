"""Load and inspect the Spider 2.0 text-to-SQL dataset from Hugging Face.

Spider 2.0-Lite (xlangai/spider2-lite) is a multi-dialect subset with 260 examples.
Full Spider 2.0 (632 tasks, execution) is at https://github.com/xlang-ai/Spider2
and requires BigQuery/Snowflake setup.
"""

import os

from datasets import load_dataset

# Use project-local cache so downloads work in restricted environments
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "HF_HOME" not in os.environ:
    os.environ["HF_HOME"] = os.path.join(_PROJECT_ROOT, ".cache", "huggingface")


def load_spider2_lite():
    """Load Spider 2.0-Lite from Hugging Face (260 train examples, multi-dialect)."""
    print("Loading Spider 2.0-Lite dataset...")
    ds = load_dataset("xlangai/spider2-lite")
    print("Spider 2.0-Lite loaded successfully!")
    print(ds)
    return ds


def main():
    return load_spider2_lite()


if __name__ == "__main__":
    ds = main()
