#!/usr/bin/env python3
"""Expand bypass_variants.yaml using the HIT-CIR Chinese Thesaurus (同义词词林).

Strategy:
1. Read existing bypass_variants keys (Chinese-character entries only).
2. For each seed, look up its synonym group in the thesaurus.
3. Add all group members as new bypass variants pointing to the seed's
   replacement value (or to the first seed word if from rules).
4. Skip single-character entries (too high false-positive risk).
5. Skip entries already in bypass_variants.
"""

import yaml
from pathlib import Path
import re
import tempfile

BYPASS_PATH = Path("config/bypass_variants.yaml")
# Resolve the thesaurus path: on Linux/macOS it's /tmp/..., on Windows Git Bash
# maps /tmp to the system temp dir, but Windows Python doesn't follow that symlink.
# Use tempfile.gettempdir() to work cross-platform.
THESAURUS_REL = Path("funNLP/data/同义词库、反义词库、否定词库/同义词库.txt")
THESAURUS_PATH = Path(tempfile.gettempdir()) / THESAURUS_REL


def is_chinese(s: str) -> bool:
    """Check if string contains Chinese characters."""
    return bool(re.search(r"[一-鿿]", s))


def load_thesaurus(path: Path) -> dict[str, set[str]]:
    """Load the HIT-CIR thesaurus.

    Returns: {word: set_of_synonyms} — each word maps to all words in
    the same synset group(s).
    """
    word_to_synonyms: dict[str, set[str]] = {}
    synset_count = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or "=" not in line:
                continue
            # Format: "Aa01A01= 人 士 人物 人士 ..."
            synset_id, words_str = line.split("=", 1)
            words = [w.strip() for w in words_str.split() if w.strip()]
            if len(words) < 2:
                continue
            synset_count += 1
            for word in words:
                if word not in word_to_synonyms:
                    word_to_synonyms[word] = set()
                word_to_synonyms[word].update(w for w in words if w != word)

    print(f"Loaded {synset_count} synsets, {len(word_to_synonyms)} unique words")
    return word_to_synonyms


def main() -> None:
    if not THESAURUS_PATH.exists():
        raise FileNotFoundError(f"Thesaurus not found at {THESAURUS_PATH}")

    if not BYPASS_PATH.exists():
        raise FileNotFoundError(f"bypass_variants.yaml not found at {BYPASS_PATH}")

    # Load existing bypass variants
    with open(BYPASS_PATH, "r", encoding="utf-8") as f:
        existing_data = yaml.safe_load(f) or {}

    existing_keys = set(existing_data.keys())
    existing_values = set(existing_data.values())

    # Load thesaurus
    thesaurus = load_thesaurus(THESAURUS_PATH)

    # Collect seeds: Chinese-character keys from existing bypass variants
    seeds: dict[str, str] = {}
    for key, value in existing_data.items():
        key_str = str(key).strip()
        if is_chinese(key_str) and len(key_str) >= 2:
            seeds[key_str] = str(value)

    print(f"Found {len(seeds)} Chinese-character seed entries in bypass_variants")

    # Find new variants
    new_entries: dict[str, str] = {}
    for seed_word, target in seeds.items():
        if seed_word not in thesaurus:
            continue
        for synonym in thesaurus[seed_word]:
            # Skip single-character words
            if len(synonym) < 2:
                continue
            # Skip if already exists
            if synonym in existing_keys or synonym in new_entries:
                continue
            # Skip if the synonym IS the target word itself
            if synonym == target:
                continue
            # Skip if synonym is too common (single-char safe, but multi-char
            # that looks like normal vocabulary — check it's not just a normal
            # word that happens to be in a synset)
            # Don't add if it's a very common word (>3 chars often safe)
            if len(synonym) <= 4:
                new_entries[synonym] = target

    print(f"Found {len(new_entries)} new bypass variants from thesaurus")

    if not new_entries:
        print("No new entries to add, exiting")
        return

    # Write back: rebuild the YAML file preserving the original structure
    # Read the raw file content
    with open(BYPASS_PATH, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # Build the new section to append
    new_section_lines = [
        "",
        "# === 同音/同义变体（来自哈工大同义词词林 HIT-CIR）===",
    ]
    # Group by target for readability
    by_target: dict[str, list[str]] = {}
    for k, v in new_entries.items():
        by_target.setdefault(v, []).append(k)

    for target, variants in sorted(by_target.items()):
        new_section_lines.append(f"# → {target}")
        for variant in sorted(variants):
            new_section_lines.append(f"{variant}: {target}")

    new_section = "\n".join(new_section_lines) + "\n"

    with open(BYPASS_PATH, "a", encoding="utf-8") as f:
        f.write(new_section)

    print(f"Appended {len(new_entries)} entries to {BYPASS_PATH}")


if __name__ == "__main__":
    main()
