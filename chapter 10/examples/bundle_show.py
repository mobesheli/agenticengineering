"""Print the release bundle, its digest, and the pointers the pipeline checks.

python -m examples.bundle_show
"""

from __future__ import annotations

from chapter10.bundle import TEMPLATE, broken_references, bundle_digest, load_bundle


def main() -> list[str]:
    bundle = load_bundle()
    lines = (TEMPLATE / "bundle.yaml").read_text().splitlines()
    lines.append("")
    lines.append(f"release digest  sha256:{bundle_digest(bundle)[:12]}")
    problems = broken_references(bundle)
    lines.append(
        f"pointers        {'; '.join(problems) or 'all match the files they name'}"
    )
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    main()
