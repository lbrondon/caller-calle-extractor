from pathlib import Path
import os
import logging
from typing import List, Tuple

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Determine repository root reliably based on this file's location
REPO_ROOT = Path(__file__).resolve().parent.parent

# Directory names (exported as strings for backwards compatibility)
PROJECTS_DIR_NAME = 'projects'
OUTPUT_DIR_NAME = 'output'
OUTPUT_CSV_FILE_NAME = 'function_call_graph.csv'

# Absolute paths (strings) used by other modules
PROJECTS_DIR = str(REPO_ROOT / PROJECTS_DIR_NAME)
CLONED_PROJECTS_DIR = PROJECTS_DIR
OUTPUT_DIR = str(REPO_ROOT / OUTPUT_DIR_NAME)
REPOSITORIES = str(REPO_ROOT / 'source' / 'repositories.txt')


def extract_relative_path(path: str) -> str:
    """Return the path segment after 'projects/'.

    If the given path does not contain 'projects/', returns an informative string.
    """
    try:
        return path.split(PROJECTS_DIR_NAME + os.sep, 1)[1]
    except Exception:
        return "The specified directory 'projects/' was not found in the path."


def get_projects_names() -> List[str]:
    """Return a sorted list of project folder names under `projects/`.

    Uses os.scandir for efficiency when the directory contains many entries.
    """
    projects_path = Path(CLONED_PROJECTS_DIR)
    if not projects_path.exists():
        LOGGER.info('Directory %s does not exist.', projects_path)
        return []

    names = []
    try:
        with os.scandir(projects_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        names.append(entry.name)
                except OSError:
                    LOGGER.debug('Skipping entry due to OSError: %s', entry.path)
        names.sort()
        return names
    except OSError as e:
        LOGGER.error('Error listing projects directory %s: %s', projects_path, e)
        return []


def get_project_dirs_and_output(create_output_dir: bool = True) -> Tuple[List[str], str]:
    """Return (project_dirs, output_csv_path).

    - `project_dirs` is a list of absolute paths (strings) for each project.
    - `output_csv_path` is the absolute path to the output CSV.

    If `create_output_dir` is True, the output directory will be created if missing.
    """
    project_names = get_projects_names()
    project_dirs = [str(Path(CLONED_PROJECTS_DIR) / name) for name in project_names]

    output_dir = Path(OUTPUT_DIR)
    if create_output_dir:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            LOGGER.error('Failed to create output directory %s: %s', output_dir, e)

    output_csv = str(output_dir / OUTPUT_CSV_FILE_NAME)
    return project_dirs, output_csv
