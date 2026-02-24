import os


def get_github_token():
    """Return a GitHub token.

    Priority:
    1. Environment variable `GITHUB_TOKEN`
    2. File `github_token.txt` in the current working directory

    Raises FileNotFoundError when no token is found, and raises IOError
    for file read problems. Caller should handle exceptions appropriately.
    """
    # 1) Try environment variable first
    token = os.getenv("GITHUB_TOKEN")
    if token:
        token = token.strip()
        if token:
            return token

    # 2) Fallback to token file
    token_file = "github_token.txt"
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as file:
                token = file.read().strip()
                if not token:
                    raise ValueError(f"{token_file} is empty. Please add your GitHub token inside the file or set GITHUB_TOKEN.")
                return token
        except (IOError, OSError) as e:
            raise IOError(f"Error reading {token_file}: {e}")

    # Nothing found
    raise FileNotFoundError(
        "GitHub token not found. Set the GITHUB_TOKEN environment variable or create a github_token.txt file containing the token."
    )