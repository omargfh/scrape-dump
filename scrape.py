"""
Script to scrape all files (mainly code) in a given directory
and output a JSON file with the following structure:
{
    "files": [
        {
            "name": "filename",
            "directory": "directory",
            "content": "file content"
        }
    ],
    "total_size": total_size,
    "file_count": file_count
}

Usage:
    python scrape.py [--extensions EXTENSIONS] [--max-size MAX_SIZE] [--max-total-size MAX_TOTAL_SIZE] [--ignore-dirs IGNORE_DIRS] DIRS OUTPUT
"""

import argparse as ap
import os
import json
from typing import Optional, Set, List
import dataclasses
from datetime import datetime

from printer import PrintUtils, FormattedText

# https://stackoverflow.com/a/51286749
class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)

def parse_args() -> ap.Namespace:
    parser = ap.ArgumentParser(description="Scrape all files in a given directory")
    parser.add_argument("--extensions", type=str, default="py", help="Comma separated list of file extensions to scrape")
    parser.add_argument("--max-size", type=int, default=1000000, help="Maximum file size to scrape in bytes")
    parser.add_argument("--max-total-size", type=int, default=100000000, help="Maximum total size of all files to scrape in bytes")
    parser.add_argument("--ignore-dirs", type=str, default="", help="Comma separated list of directories to ignore")
    parser.add_argument("dirs", type=str, help="Comma separated list of directories to scrape")
    parser.add_argument("output", type=str, help="Output JSON file")
    return parser.parse_args()

def get_file_extension(filename: str) -> str:
    """
    Get the extension of a file
    """
    parts = filename.split(".")
    if len(parts) > 1:
        return parts[-1]
    return ""

def get_file_size(filename: str) -> int:
    """
    Get the size of a file
    """
    try:
        return os.path.getsize(filename)
    except Exception as e:
        PrintUtils.error(f"{e}")
        return 0

def get_file_content(filename: str) -> Optional[str]:
    """
    Get the content of a file
    """
    try:
        with open(filename, "r") as f:
            return f.read()
    except Exception as e:
        PrintUtils.error(f"{e}")
        return None

def confirm_extension(filename: str, extensions: Set[str]):
    """
    Check if a file has the specified extension
    """
    return get_file_extension(filename) in extensions

@dataclasses.dataclass
class ScrapeFile:
    name: str
    directory: str
    content: str
    size: int
    scraped_at: Optional[str] = None

def file_in_ignore_dirs(filename: str, ignore_dirs: List[str]) -> bool:
    """
    Check if a file is in the ignore directories
    """
    for ignore_dir in ignore_dirs:
        if ignore_dir in filename:
            return True
    return False

def scrape_file(filename: str, extensions: Set[str], max_size: int) -> Optional[dict]:
    """
    Scrape a single file with the specified extension and maximum size
    and return a dictionary with the ScraperFile dataclass
    """
    if not confirm_extension(filename, extensions):
        return None
    size = get_file_size(filename)
    if not size or size <= 0 or size > max_size:
        return None
    content = get_file_content(filename)
    if not content:
        return None
    return ScrapeFile(
        name=os.path.basename(filename),
        directory=os.path.dirname(filename),
        content=content,
        size=size,
        scraped_at=datetime.now().isoformat()
    )

def scrape_directory(
    directory: str,
    extensions: Set[str],
    max_size: int,
    max_total_size: int,
    ignore_dirs: List[str] = []
) -> List[ScrapeFile]:
    """
    Scrape all files in a given directory with the specified extensions
    and return a list of dictionaries with the ScraperFile dataclass
    """
    files = []
    total_size = 0
    file_count = 0
    try:
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                if file_in_ignore_dirs(filepath, ignore_dirs):
                    continue
                file = scrape_file(filepath, extensions, max_size)
                if file:
                    files.append(file)
                    total_size += get_file_size(filepath)
                    if total_size > max_total_size:
                        break
                    file_count += 1

    except Exception as e:
        PrintUtils.error(f"{e}")

    finally:
        return files, total_size, file_count

def scrape_directories(directories: List[str], extensions: Set[str], max_size: int, max_total_size: int, ignore_dirs: List[str] = []) -> List[ScrapeFile]:
    """
    Scrape all files in a given list of directories with the specified extensions
    and return a list of dictionaries with the ScraperFile dataclass
    """
    files = []
    total_size = 0
    file_count = 0
    len_dirs = len(directories)
    for i, directory in enumerate(directories):
        PrintUtils.info(FormattedText.progress(i+1, len_dirs), f" Scraping directory: {directory}")
        directory_files, directory_size, directory_file_count = \
            scrape_directory(directory, extensions, max_size, max_total_size, ignore_dirs)
        files.extend(directory_files)
        total_size += directory_size
        file_count += directory_file_count
        if total_size > max_total_size:
            break
    return files, total_size, file_count

def remove_dot_from_extension(extension: str) -> str:
    """
    Remove the dot from the extension
    """
    if extension[0] == ".":
        return extension[1:]
    return extension

def remove_duplicate_paths(paths: List[str]) -> List[str]:
    """
    Remove duplicate paths in a list
    """
    paths_os_normalized = set()
    paths_filtered = []
    for path in paths:
        path_normalized = os.path.normpath(path)
        if path_normalized in paths_os_normalized:
            continue
        paths_filtered.append(path)
        paths_os_normalized.add(path_normalized)

    return paths_filtered



def main():
    # Parse arguments
    args = parse_args()
    extensions = set([remove_dot_from_extension(arg) for arg in args.extensions.split(",")])
    directories = args.dirs.split(",")

    # Ignore directories
    ignore_dirs = args.ignore_dirs.split(",")
    ignore_dirs = remove_duplicate_paths(ignore_dirs)
    ignore_dirs = [os.path.normpath(ignore_dir) for ignore_dir in ignore_dirs]

    # Validate input
    directories = remove_duplicate_paths(directories)
    if not directories:
        PrintUtils.error("No directories provided")
        exit(1)
    if not extensions:
        PrintUtils.error("No extensions provided")
        exit(1)

    files, total_size, file_count = scrape_directories(directories, extensions, args.max_size, args.max_total_size, ignore_dirs)
    PrintUtils.success(f"Scraped {file_count} files with total size {total_size} bytes")
    with open(args.output, "w") as f:
        json.dump({"files": files, "total_size": total_size, "file_count": file_count}, f, cls=EnhancedJSONEncoder)
    PrintUtils.success(f"Output written to {args.output}")

if __name__ == "__main__":
    main()
