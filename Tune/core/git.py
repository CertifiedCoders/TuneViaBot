import asyncio
import shlex
from typing import Tuple

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config

from ..logging import LOGGER


def install_req(cmd: str) -> Tuple[str, str, int, int]:
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

    return asyncio.get_event_loop().run_until_complete(install_requirements())


def git():
    REPO_LINK = config.UPSTREAM_REPO

    # Validate the repository URL.
    if not REPO_LINK.startswith("https://"):
        LOGGER(__name__).error(f"Invalid repository URL: {REPO_LINK}. URL must start with 'https://'.")
        return

    if "github.com" not in REPO_LINK:
        LOGGER(__name__).warning(f"Repository URL may be incorrect: {REPO_LINK}. Expected 'github.com' in the URL.")

    # Build an authenticated URL if a Git token is provided.
    if config.GIT_TOKEN:
        try:
            # Expecting format: https://github.com/username/repo_name
            parts = REPO_LINK.split("github.com/")
            if len(parts) != 2:
                raise ValueError("Unexpected repository URL format.")
            remainder = parts[1]
            # Insert the token into the URL
            UPSTREAM_REPO = f"https://{remainder.split('/')[0]}:{config.GIT_TOKEN}@github.com/{remainder}"
        except Exception as e:
            LOGGER(__name__).error(f"Failed to construct authenticated URL: {e}")
            UPSTREAM_REPO = REPO_LINK
    else:
        UPSTREAM_REPO = REPO_LINK

    try:
        # Try to open the current directory as a Git repository.
        repo = Repo()
        LOGGER(__name__).info("Git repository found. Using existing repository.")
    except InvalidGitRepositoryError:
        LOGGER(__name__).info("No valid Git repository found. Initializing new repository.")
        repo = Repo.init()
        # Check for an existing 'origin' remote; if not present, create it.
        remote_names = [remote.name for remote in repo.remotes]
        if "origin" in remote_names:
            origin = repo.remote("origin")
        else:
            origin = repo.create_remote("origin", UPSTREAM_REPO)
        try:
            origin.fetch()
        except GitCommandError as e:
            LOGGER(__name__).error(f"Error during fetch from origin: {e}")
            return

        # Create and checkout the branch from the upstream repository.
        try:
            repo.create_head(config.UPSTREAM_BRANCH, origin.refs[config.UPSTREAM_BRANCH])
        except GitCommandError as e:
            LOGGER(__name__).warning(f"Branch '{config.UPSTREAM_BRANCH}' may already exist: {e}")
        try:
            repo.heads[config.UPSTREAM_BRANCH].set_tracking_branch(origin.refs[config.UPSTREAM_BRANCH])
        except Exception as e:
            LOGGER(__name__).error(f"Error setting tracking branch: {e}")
        try:
            repo.heads[config.UPSTREAM_BRANCH].checkout(force=True)
        except GitCommandError as e:
            LOGGER(__name__).error(f"Error during checkout of branch '{config.UPSTREAM_BRANCH}': {e}")

        # Optionally re-create the 'origin' remote using the unmodified repository URL.
        try:
            repo.create_remote("origin", REPO_LINK)
        except Exception:
            pass

        nrs = repo.remote("origin")
        try:
            nrs.fetch(config.UPSTREAM_BRANCH)
        except GitCommandError as e:
            LOGGER(__name__).error(f"Error fetching branch {config.UPSTREAM_BRANCH} from origin: {e}")
        try:
            nrs.pull(config.UPSTREAM_BRANCH)
        except GitCommandError as e:
            LOGGER(__name__).warning(f"Pull failed for branch '{config.UPSTREAM_BRANCH}', resetting to FETCH_HEAD. Error: {e}")
            repo.git.reset("--hard", "FETCH_HEAD")

        # Install updated requirements
        install_req("pip3 install --no-cache-dir -r requirements.txt")
        LOGGER(__name__).info("Fetching updates from upstream repository...")
    except GitCommandError as e:
        LOGGER(__name__).error(f"Git command error encountered: {e}")
