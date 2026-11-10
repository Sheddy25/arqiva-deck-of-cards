"""Fail if the active environment contains an unpinned dependency."""

from importlib.metadata import distributions
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

IGNORED = frozenset({"arqiva-deck-of-cards", "pip"})


def constraint_pins(path: Path) -> dict[str, str]:
    """Read exact ``name==version`` pins from a constraints file."""
    pins: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        specifiers = list(requirement.specifier)
        if len(specifiers) != 1 or specifiers[0].operator != "==":
            raise ValueError(f"{path}:{number} is not an exact pin: {line}")
        pins[canonicalize_name(requirement.name)] = specifiers[0].version
    return pins


def installed_versions() -> dict[str, str]:
    """The named distributions installed in the active environment."""
    return {
        canonicalize_name(name): distribution.version
        for distribution in distributions()
        if (name := distribution.metadata["Name"]) is not None
    }


def main() -> int:
    pins = constraint_pins(Path("constraints.txt"))
    installed = installed_versions()
    problems = [
        f"{name}=={version} is installed but constraints.txt has {pins.get(name)!r}"
        for name, version in sorted(installed.items())
        if name not in IGNORED and pins.get(name) != version
    ]
    if problems:
        print("\n".join(problems))
        return 1
    checked = len(installed) - len(IGNORED & installed.keys())
    print(f"All {checked} dependencies are pinned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
