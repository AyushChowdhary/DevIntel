from git import Repo
import os

def clone_repo(repo_url, clone_dir="repo"):
    if os.path.exists(clone_dir):
        return clone_dir
    Repo.clone_from(repo_url, clone_dir)
    return clone_dir


def load_code_files(repo_path):
    code_files = []

    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        code_files.append({
                            "path": path,
                            "content": f.read()
                        })
                except:
                    continue

    return code_files
