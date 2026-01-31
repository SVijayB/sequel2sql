"""Load and inspect the Spider text-to-SQL dataset from Hugging Face."""

import os

from datasets import load_dataset

# Use project-local cache so downloads work in restricted environments
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "HF_HOME" not in os.environ:
    os.environ["HF_HOME"] = os.path.join(_PROJECT_ROOT, ".cache", "huggingface")


def main() -> None:
    # Load the Spider dataset
    print("Loading Spider dataset...")
    ds = load_dataset("xlangai/spider")
    print("Dataset loaded successfully!")
    print(ds)
    return ds


if __name__ == "__main__":
    ds = main()
