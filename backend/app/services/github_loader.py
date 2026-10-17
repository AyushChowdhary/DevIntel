from git import Repo
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2] / ".cache" / "repositories"
SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb", ".php", ".cs"}
SKIPPED_DIRECTORIES = {".git", ".github", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", "coverage"}
MAX_FILE_BYTES = 512 * 1024


def normalize_repo_url(repo_url: str) -> str:
    """Accept a public GitHub repository URL and return its canonical clone URL."""
    parsed = urlparse(repo_url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Enter a public HTTPS GitHub repository URL.")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2 or not all(parts):
        raise ValueError("Repository URLs must have the form https://github.com/owner/repository.")

    owner, repository = parts
    repository = repository.removesuffix(".git")
    if not repository:
        raise ValueError("Repository name is missing.")
    return f"https://github.com/{owner}/{repository}.git"


def clone_repo(repo_url: str) -> tuple[str, str]:
    canonical_url = normalize_repo_url(repo_url)
    repository_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
    clone_path = REPOSITORY_ROOT / repository_id

    if not clone_path.exists():
        REPOSITORY_ROOT.mkdir(parents=True, exist_ok=True)
        Repo.clone_from(canonical_url, clone_path, depth=1)
    return str(clone_path), canonical_url


def load_code_files(repo_path):
    code_files = []
    root_path = Path(repo_path)

    for root, directories, files in os.walk(root_path):
        directories[:] = [directory for directory in directories if directory not in SKIPPED_DIRECTORIES]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            code_files.append({"path": str(path.relative_to(root_path)), "content": content})

    return code_files
