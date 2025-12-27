# Authored By Certified Coders © 2025
import asyncio
import shlex
from typing import Tuple
from urllib.parse import urlparse, urlunparse

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config
from Tune.logging import LOGGER


def install_req(cmd: str) -> Tuple[str, str, int, int]:
    try:
        asyncio.get_running_loop()
        raise RuntimeError("install_req cannot be called from an async context")
    except RuntimeError as e:
        if "cannot be called from an async context" in str(e):
            raise

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def install_requirements():
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return loop.run_until_complete(install_requirements())


def _build_upstream_url(repo_url: str, token: str = None) -> str:
    if not token:
        return repo_url

    try:
        parsed = urlparse(repo_url)
        if not parsed.netloc or not parsed.path:
            LOGGER(__name__).warning(f"Invalid repository URL format: {repo_url}")
            return repo_url

        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if not path_parts:
            LOGGER(__name__).warning(f"Could not extract username from URL: {repo_url}")
            return repo_url

        username = path_parts[0]
        netloc = f"{username}:{token}@{parsed.netloc}"
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    except Exception as e:
        LOGGER(__name__).warning(f"Error building upstream URL: {e}, using original URL")
        return repo_url


def _setup_remote(repo: Repo, upstream_url: str):
    if "origin" in repo.remotes:
        origin = repo.remote("origin")
        if origin.url != upstream_url:
            origin.set_url(upstream_url)
    else:
        origin = repo.create_remote("origin", upstream_url)
    return origin


def _setup_branch(repo: Repo, origin, branch_name: str):
    if branch_name not in origin.refs:
        LOGGER(__name__).error(f"Branch {branch_name} not found in remote")
        return False

    if branch_name not in repo.heads:
        repo.create_head(branch_name, origin.refs[branch_name])
    else:
        repo.heads[branch_name].set_tracking_branch(origin.refs[branch_name])

    repo.heads[branch_name].checkout(True)
    return True


def git():
    UPSTREAM_REPO = _build_upstream_url(config.UPSTREAM_REPO, config.GIT_TOKEN)

    try:
        repo = Repo()
        LOGGER(__name__).info("Git Client Found [VPS DEPLOYER]")
    except GitCommandError as e:
        LOGGER(__name__).error(f"Invalid Git Command: {e}")
        return
    except InvalidGitRepositoryError:
        try:
            repo = Repo.init()
            LOGGER(__name__).info("Initializing new Git repository")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to initialize Git repository: {e}")
            return

        try:
            origin = _setup_remote(repo, UPSTREAM_REPO)
            origin.fetch()
        except Exception as e:
            LOGGER(__name__).error(f"Failed to setup remote origin: {e}")
            return

        if not _setup_branch(repo, origin, config.UPSTREAM_BRANCH):
            return

    try:
        origin = _setup_remote(repo, UPSTREAM_REPO)
        origin.fetch(config.UPSTREAM_BRANCH)
    except Exception as e:
        LOGGER(__name__).error(f"Failed to fetch updates: {e}")
        return

    try:
        origin.pull(config.UPSTREAM_BRANCH)
    except GitCommandError:
        try:
            repo.git.reset("--hard", "FETCH_HEAD")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to reset repository: {e}")
            return

    stdout, stderr, returncode, _ = install_req("pip3 install --no-cache-dir -r requirements.txt")
    if returncode != 0:
        LOGGER(__name__).warning(f"Requirements installation had issues: {stderr}")
    else:
        LOGGER(__name__).info("Requirements installed successfully")