import requests
import os
import sys
import time
import logging
import math
from datetime import datetime, timezone
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Ensure local modules importable
sys.path.insert(0, os.path.dirname(__file__))

from directory_manager import CLONED_PROJECTS_DIR, REPOSITORIES
from get_github_token import get_github_token

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Configuration
BASE_API_URL = "https://api.github.com/repos"
RAW_BASE = "https://raw.githubusercontent.com"
DEFAULT_TIMEOUT = 10  # seconds for HTTP requests
MAX_WORKERS = int(os.getenv('DOWNLOAD_WORKERS', '4'))
REPO_CONCURRENCY = int(os.getenv('REPO_CONCURRENCY', '3'))
RETRY_TOTAL = 3
RETRY_BACKOFF = 1


def create_session(token: str) -> requests.Session:
    session = requests.Session()
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'repo-miner/1.0'
    }
    session.headers.update(headers)

    retries = Retry(total=RETRY_TOTAL, backoff_factor=RETRY_BACKOFF,
                    status_forcelist=(500, 502, 503, 504), allowed_methods=frozenset(['GET', 'POST']))
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def parse_rate_limit_headers(headers):
    try:
        remaining = int(headers.get('X-RateLimit-Remaining', '0'))
        reset = int(headers.get('X-RateLimit-Reset', '0'))
        return remaining, reset
    except Exception:
        return None, None


def wait_for_rate_limit(reset_ts):
    now = int(time.time())
    wait = max(0, reset_ts - now)
    if wait > 0:
        LOGGER.warning('Rate limit reached, sleeping %d seconds until reset', wait)
        time.sleep(wait + 1)


def extract_repo_info(repo_link: str):
    parsed_url = urlparse(repo_link)
    path = parsed_url.path.strip('/')
    parts = path.split('/')
    if len(parts) >= 2:
        repo_owner, repo_name = parts[0], parts[1]
        LOGGER.debug('Extracted repository info - Owner: %s, Repository: %s', repo_owner, repo_name)
        return repo_owner, repo_name
    else:
        raise ValueError('The URL is not in the expected format.')


def get_default_branch(session: requests.Session, owner: str, repo: str):
    url = f"{BASE_API_URL}/{owner}/{repo}"
    resp = session.get(url, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 200:
        data = resp.json()
        return data.get('default_branch')
    else:
        LOGGER.debug('Could not get repo info %s/%s: %s', owner, repo, resp.status_code)
        return None


def try_get_repo_tree(session: requests.Session, owner: str, repo: str, branch: str):
    # Use git trees recursive which can return the whole tree in one call
    url = f"{BASE_API_URL}/{owner}/{repo}/git/trees/{branch}?recursive=1"
    resp = session.get(url, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 200:
        data = resp.json()
        if 'tree' in data:
            return data['tree']
    else:
        LOGGER.debug('git/trees failed for %s/%s (branch=%s): %s', owner, repo, branch, resp.status_code)
    return None


def download_blob(session: requests.Session, owner: str, repo: str, branch: str, path: str, dest_root: str):
    raw_url = f"{RAW_BASE}/{owner}/{repo}/{branch}/{path}"
    local_path = os.path.join(dest_root, path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    if os.path.exists(local_path):
        LOGGER.debug('File exists, skipping: %s', local_path)
        return
    try:
        r = session.get(raw_url, timeout=DEFAULT_TIMEOUT)
        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(r.content)
            LOGGER.info('Downloaded %s', local_path)
        else:
            LOGGER.warning('Failed to download %s: status %s', raw_url, r.status_code)
    except requests.RequestException as e:
        LOGGER.warning('Request failed for %s: %s', raw_url, e)


def get_files_via_contents_api(session: requests.Session, owner: str, repo: str, base_path: str, repo_dir: str):
    # Iterative traversal using /contents endpoint
    stack = ['']
    while stack:
        path = stack.pop()
        api_url = f"{BASE_API_URL}/{owner}/{repo}/contents/{path}" if path else f"{BASE_API_URL}/{owner}/{repo}/contents"
        try:
            resp = session.get(api_url, timeout=DEFAULT_TIMEOUT)
            remaining, reset = parse_rate_limit_headers(resp.headers)
            if resp.status_code == 403 and reset:
                wait_for_rate_limit(reset)
                stack.append(path)
                continue
            if resp.status_code != 200:
                LOGGER.warning('Non-200 listing %s: %s', api_url, resp.status_code)
                continue
            contents = resp.json()
            for item in contents:
                if item.get('type') == 'file' and item.get('name', '').endswith('.c'):
                    # download via raw URL
                    download_blob(session, owner, repo, base_path, item['path'], repo_dir)
                elif item.get('type') == 'dir':
                    stack.append(item['path'])
        except requests.RequestException as e:
            LOGGER.warning('Error accessing %s: %s', api_url, e)


def process_repository(session: requests.Session, repo_link: str, dest_root: str):
    owner, name = extract_repo_info(repo_link)
    repo_dir = os.path.join(dest_root, name)
    if os.path.exists(repo_dir):
        LOGGER.info('Repository exists, skipping: %s', repo_dir)
        return
    os.makedirs(repo_dir, exist_ok=True)

    # Try tree-based approach first (more efficient)
    branch = get_default_branch(session, owner, name) or 'master'
    tree = try_get_repo_tree(session, owner, name, branch)
    if tree is not None:
        LOGGER.info('Using git/trees for %s/%s', owner, name)
        for entry in tree:
            if entry.get('type') == 'blob' and entry.get('path', '').endswith('.c'):
                download_blob(session, owner, name, branch, entry['path'], repo_dir)
    else:
        LOGGER.info('Falling back to contents API for %s/%s', owner, name)
        get_files_via_contents_api(session, owner, name, branch, repo_dir)


def download_repositories(limit: int = None):
    token = get_github_token()
    session = create_session(token)

    with open(REPOSITORIES, 'r') as f:
        repos = [r.strip() for r in f if r.strip()]

    if limit:
        repos = repos[:limit]

    LOGGER.info('Starting download for %d repositories (workers=%d)', len(repos), REPO_CONCURRENCY)
    with ThreadPoolExecutor(max_workers=REPO_CONCURRENCY) as executor:
        futures = {executor.submit(process_repository, session, link, CLONED_PROJECTS_DIR): link for link in repos}
        for fut in as_completed(futures):
            link = futures[fut]
            try:
                fut.result()
            except Exception as e:
                LOGGER.error('Processing failed for %s: %s', link, e)


# Backwards-compat wrapper used by main.py
def download_repositories_entry():
    limit = None
    env_limit = os.getenv('DOWNLOAD_LIMIT')
    if env_limit:
        try:
            limit = int(env_limit)
        except Exception:
            LOGGER.warning('Invalid DOWNLOAD_LIMIT value: %s', env_limit)
    download_repositories(limit=limit)


# if __name__ == '__main__':
#     download_repositories_entry()
