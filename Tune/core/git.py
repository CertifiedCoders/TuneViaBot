# Authored By Certified Coders © 2025
import asyncio
import shlex
from typing import Tuple
from urllib.parse import urlparse, urlunparse

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config
from Tune.logging import LOGGER


class _AsyncContextError(RuntimeError):
    """Custom exception to indicate we're in an async context"""
    pass


def install_req(cmd: str) -> Tuple[str, str, int, int]:
    try:
        asyncio.get_running_loop()
        raise _AsyncContextError("Cannot use run_until_complete in async context")
    except _AsyncContextError:
        # We're in an async context, cannot use run_until_complete
        raise RuntimeError("install_req cannot be called from an async context")
    except RuntimeError:
        # No running loop, safe to proceed
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

        if "com/" in parsed.path:
            username = parsed.path.split("com/")[1].split("/")[0]
        else:
            username = parsed.path.strip("/").split("/")[0] if parsed.path else ""

        if not username:
            LOGGER(__name__).warning(f"Could not extract username from URL: {repo_url}")
            return repo_url

        netloc = f"{username}:{token}@{parsed.netloc}"
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    except Exception as e:
        LOGGER(__name__).warning(f"Error building upstream URL: {e}, using original URL")
        return repo_url


def git():
    repo = None
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
            if "origin" in repo.remotes:
                origin = repo.remote("origin")
                origin.set_url(UPSTREAM_REPO)
            else:
                origin = repo.create_remote("origin", UPSTREAM_REPO)

            origin.fetch()
        except Exception as e:
            LOGGER(__name__).error(f"Failed to setup remote origin: {e}")
            return

        try:
            branch_name = config.UPSTREAM_BRANCH
            if branch_name not in origin.refs:
                LOGGER(__name__).error(f"Branch {branch_name} not found in remote")
                return

            if branch_name not in repo.heads:
                repo.create_head(branch_name, origin.refs[branch_name])
            else:
                repo.heads[branch_name].set_tracking_branch(origin.refs[branch_name])

            repo.heads[branch_name].checkout(True)
        except Exception as e:
            LOGGER(__name__).error(f"Failed to checkout branch {config.UPSTREAM_BRANCH}: {e}")
            return

    if repo is None:
        LOGGER(__name__).error("Repository object is None")
        return

    try:
        origin = repo.remote("origin")
        if origin.url != UPSTREAM_REPO:
            origin.set_url(UPSTREAM_REPO)

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

    LOGGER(__name__).info("Fetching updates from upstream repository...")
