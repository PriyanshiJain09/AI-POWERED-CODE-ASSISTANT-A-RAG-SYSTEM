# github_client.py — Thin wrapper around PyGithub

import os
import base64
from github import Github, GithubException
import httpx

_gh = None

def get_github_client() -> Github:
    global _gh
    if _gh is None:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN not set in .env")
        _gh = Github(token)
    return _gh


async def get_file_content(repo_full_name: str, file_path: str) -> str | None:
    """Fetch raw content of a single file from GitHub."""
    try:
        gh = get_github_client()
        repo = gh.get_repo(repo_full_name)
        file_obj = repo.get_contents(file_path)
        # get_contents returns a list if it's a directory
        if isinstance(file_obj, list):
            return None
        return base64.b64decode(file_obj.content).decode("utf-8", errors="replace")
    except GithubException as e:
        if e.status == 404:
            return None
        raise


async def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Fetch the unified diff for a pull request."""
    token = os.getenv("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        return resp.text


async def list_repo_files(repo_full_name: str, extensions: list[str] | None = None) -> list[dict]:
    """
    Walk the repo tree and return all files (optionally filtered by extension).
    Returns list of {path, sha, size} dicts.
    """
    gh = get_github_client()
    repo = gh.get_repo(repo_full_name)

    # Use git tree API — much faster than recursive get_contents
    tree = repo.get_git_tree(sha="HEAD", recursive=True)
    files = []
    for item in tree.tree:
        if item.type != "blob":
            continue
        if extensions:
            if not any(item.path.endswith(ext) for ext in extensions):
                continue
        files.append({"path": item.path, "sha": item.sha, "size": item.size or 0})
    return files


async def get_file_batch(repo_full_name: str, paths: list[str]) -> dict[str, str]:
    """Fetch multiple files concurrently. Returns {path: content}."""
    import asyncio

    async def _fetch_one(path):
        content = await get_file_content(repo_full_name, path)
        return path, content

    results = await asyncio.gather(*[_fetch_one(p) for p in paths], return_exceptions=True)
    out = {}
    for r in results:
        if isinstance(r, Exception):
            continue
        path, content = r
        if content:
            out[path] = content
    return out


async def create_pull_request(
    repo_full_name: str,
    branch_name: str,
    title: str,
    body: str,
    base_branch: str = "main",
) -> str:
    """Create a PR and return its HTML URL."""
    gh = get_github_client()
    repo = gh.get_repo(repo_full_name)
    pr = repo.create_pull(
        title=title,
        body=body,
        head=branch_name,
        base=base_branch,
    )
    return pr.html_url


async def create_branch_and_commit(
    repo_full_name: str,
    branch_name: str,
    file_changes: list[dict],   # [{path, content}]
    commit_message: str,
) -> None:
    """
    Create a new branch from HEAD and commit file changes to it.
    file_changes: list of {path: str, content: str}
    """
    gh = get_github_client()
    repo = gh.get_repo(repo_full_name)

    # Get HEAD SHA
    default_branch = repo.default_branch
    ref = repo.get_git_ref(f"heads/{default_branch}")
    head_sha = ref.object.sha

    # Create branch
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=head_sha)

    # Commit each changed file
    for change in file_changes:
        try:
            existing = repo.get_contents(change["path"], ref=branch_name)
            repo.update_file(
                path=change["path"],
                message=commit_message,
                content=change["content"],
                sha=existing.sha,
                branch=branch_name,
            )
        except GithubException:
            repo.create_file(
                path=change["path"],
                message=commit_message,
                content=change["content"],
                branch=branch_name,
            )
