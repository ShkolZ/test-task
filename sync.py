import argparse
from pathlib import Path
from dataclasses import dataclass
import time
import sys
import shutil
import os
import logging
import stat
from enum import Enum
import hashlib

logger = logging.getLogger("sync")
BUFF_SIZE = 1024 * 1024


class FileKind(Enum):
    LINK = "link"
    FILE = "file"
    DIR = "dir"
    OTHER = "other"


@dataclass
class FileEntry:
    path: Path
    kind: FileKind | None


def setup_logger(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    for handler in (logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Syncer")
    parser.add_argument("source", type=str, help="Path to source folder")
    parser.add_argument("replica", type=str,
                        help="Path to replica folder")
    parser.add_argument("interval", type=int,
                        help="Interval between synchronizations(seconds)")
    parser.add_argument("sync_amount", type=int,
                        help="Amount of synchronizations")
    parser.add_argument("log", type=str, help="Path to log file")
    args = parser.parse_args()

    return args


def hash_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while data := f.read(BUFF_SIZE):
            h.update(data)
    return h.hexdigest()


def files_dif(src: Path, dst: Path) -> bool:
    if hash_file(src) != hash_file(dst):
        return True
    return False


def validate_dirs(src: Path, replica: Path) -> None:
    if not src.is_dir():
        raise Exception("Source is not a directory")
    if src == replica:
        raise Exception("Source and replica can't be the same directory")
    if src.is_relative_to(replica) or replica.is_relative_to(src):
        raise Exception("Directories can't nested in each other")


def remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, True)
        logger.info(f"Directory at '{path}' was deleted")
    else:
        path.unlink()
        logger.info(f"File at '{path}' was deleted")


def get_kind(file: Path) -> FileKind:
    mode = file.lstat().st_mode
    if stat.S_ISLNK(mode):
        return FileKind.LINK
    if stat.S_ISDIR(mode):
        return FileKind.DIR
    if stat.S_ISREG(mode):
        return FileKind.FILE
    return FileKind.OTHER


def sync_files(src: Path, dst: Path) -> None:
    """Recursively sync files"""
    src_names = {p.name for p in src.iterdir()}

    for dst_entry in dst.iterdir():
        if dst_entry.name not in src_names:
            try:
                remove(dst_entry)
            except Exception as e:
                logger.error(str(e))
    for name in sorted(src_names):
        try:
            s = FileEntry(src / name, get_kind(src / name))
            d = FileEntry(dst / name, get_kind(dst / name) if (dst /
                          name).exists() or (dst / name).is_symlink() else None)

            if d.kind is not None and d.kind != s.kind:
                remove(d.path)
                d.kind = None

            if s.kind == FileKind.DIR:
                if d.kind is None:
                    d.path.mkdir()
                    logger.info(f"Created directory at {d.path}")
                sync_files(s.path, d.path)
            elif s.kind == FileKind.FILE:
                if d.kind is None:
                    shutil.copy2(s.path, d.path)
                    logger.info(f"File created: {d.path}")
                elif files_dif(s.path, d.path):
                    shutil.copy2(s.path, d.path)
                    logger.info(f"File updated: {d.path}")

            elif s.kind == FileKind.LINK:
                target = os.readlink(s.path)
                if d.kind is None or os.readlink(d.path) != target:
                    if d.kind is not None:
                        d.path.unlink()
                    os.symlink(target, d.path)
                    logger.info(f"Created symlink '{d.path}' to '{target}'")
            else:
                raise TypeError(
                    "This syncer doesn't support this type of file")
        except Exception as e:
            logger.error(str(e))


def start_sync(source: Path, replica: Path, sync_amount: int, interval: int) -> None:
    for i in range(sync_amount):
        try:
            sync_files(source, replica)
        except Exception as e:
            logger.error(str(e))
        if not i == sync_amount - 1:
            time.sleep(interval)


def main():
    args = parse_args()
    source, replica = args.source.resolve(), args.replica.resolve()
    setup_logger(args.log.resolve())
    # clean_replica(replica)
    try:
        validate_dirs(source, replica)
        start_sync(source, replica, args.sync_amount, args.interval)
    except Exception as e:
        logger.error(str(e))


if __name__ == "__main__":
    main()
