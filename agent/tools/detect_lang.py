import os
from pathlib import Path


def _has_python_indicators(root: Path) -> bool:
    if any(root.glob("*.py")):
        return True
    if (root / "pyproject.toml").is_file():
        return True
    if (root / "requirements.txt").is_file():
        return True
    return False


def _has_typescript_indicators(root: Path) -> bool:
    if (root / "package.json").is_file():
        return True
    if any(root.glob("*.ts")) or any(root.glob("*.tsx")):
        return True
    return False


def detect_lang(workspace: str) -> str:
    root = Path(workspace)

    has_python = _has_python_indicators(root)
    has_typescript = _has_typescript_indicators(root)

    if has_python and has_typescript:
        return "mixed"
    if has_python:
        return "python"
    if has_typescript:
        return "typescript"
    return "mixed"


def main() -> None:
    workspace = os.environ.get("WORKSPACE", os.getcwd())
    lang = detect_lang(workspace)

    output_line = f"lang={lang}"
    print(output_line)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(output_line + "\n")


if __name__ == "__main__":
    main()
