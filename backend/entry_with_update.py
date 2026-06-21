import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.append(str(root))
os.chdir(root)

help_requested = any(arg in ("-h", "--help") for arg in sys.argv)
explicit_offline = os.environ.get("RF_OFFLINE") == "1" or "--offline" in sys.argv
self_update_enabled = os.environ.get("DREAMFORGE_AUTO_UPDATE") == "1"

if help_requested:
    os.environ.setdefault("RF_OFFLINE", "1")

if self_update_enabled and not explicit_offline and not help_requested:
    from modules.launch_util import (run, python)

    requirements_file = "requirements_versions.txt"
    run(
        f'"{python}" -m pip install -r "{requirements_file}"',
        "Check pre-requirements",
        "Couldn't check pre-reqs",
        live=False,
    )

    bupdated = False
    try:
        import pygit2
    
        pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)
    
        repo_path = Path(__file__).resolve().parent
        repo = pygit2.Repository(str(repo_path))
    
        branch_name = repo.head.shorthand
    
        remote_name = "origin"
        remote = repo.remotes[remote_name]
    
        remote.fetch()
    
        local_branch_ref = f"refs/heads/{branch_name}"
        local_branch = repo.lookup_reference(local_branch_ref)
    
        remote_reference = f"refs/remotes/{remote_name}/{branch_name}"
        remote_commit = repo.revparse_single(remote_reference)
    
        merge_result, _ = repo.merge_analysis(remote_commit.id)
    
        if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
            print("You have the latest version")
        elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
            local_branch.set_target(remote_commit.id)
            repo.head.set_target(remote_commit.id)
            repo.checkout_tree(repo.get(remote_commit.id))
            repo.reset(local_branch.target, pygit2.GIT_RESET_HARD)
            print("Updating Files")
            bupdated = True
        elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
            print("Update failed,  Did you modify any files?")
    except Exception as e:
        print("Update failed...")
        print(str(e))
    if bupdated:
        print("Update succeeded!!")
elif explicit_offline:
    print("Offline mode. No update.")
from launch import *
