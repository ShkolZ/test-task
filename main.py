import argparse
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import time
import sys
import shutil
import os


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Syncer")
    parser.add_argument("source_path", type=str, help="Path to source folder")
    parser.add_argument("replica_path", type=str,
                        help="Path to replica folder")
    parser.add_argument("interval", type=int,
                        help="Interval between synchronizations(seconds)")
    parser.add_argument("sync_amount", type=int,
                        help="Amount of synchronizations")
    parser.add_argument("log_path", type=str, help="Path to log file")
    args = parser.parse_args()

    return args


@dataclass
class FileInfo:
    name: str
    mod_date: datetime
    was_seen: bool
    copy_path: Path


class Syncer:
    class SyncLogger:

        def __init__(self, log_file: Path):
            self._log_file = log_file

        def log(self, msg: str):
            print(f"[LOG MESSAGE] {msg}")
            with self._log_file.open("w") as f:
                f.write(f"[LOG MESSAGE] {msg}")

        def log_create(self, name: str):
            fmt_msg = f"file: '{name}' was created"
            self.log(fmt_msg)

        def log_copy(self, name: str):
            fmt_msg = f"contents were copied to file: '{name}'"
            self.log(fmt_msg)

        def log_remove(self, name: str):
            fmt_msg = f"file: '{name}' was removed"
            self.log(fmt_msg)

        def log_exception(self, e: Exception):
            sys.stderr.write(f"[ERROR MESSAGE] Some error occured: {e}")

    def __init__(self, source: Path, replica: Path, log_file: Path):
        self._source = source
        self._replica = replica
        self._file_dict: dict[Path, FileInfo] = {}
        self._logger = Syncer.SyncLogger(log_file)
        self._counter = 1

    def sync(self):
        self._logger.log(f"Sync N: {self._counter}")
        for path in self._source.iterdir():
            file_info = self._file_dict.get(path)
            if file_info is None:
                self._add_file(path)
            else:
                if file_info.mod_date < datetime.fromtimestamp(path.stat().st_mtime):
                    self._edit_file(path, file_info)
                file_info.was_seen = True
        self._remove_files()
        self._counter += 1

    def _add_file(self, source_filepath: Path) -> None:
        rep_filepath = self._replica.joinpath(source_filepath.name)
        source_filepath.copy(rep_filepath)
        self._file_dict[source_filepath] = FileInfo(
            source_filepath.name,
            datetime.fromtimestamp(source_filepath.stat().st_mtime),
            True,
            rep_filepath
        )
        self._logger.log_create(rep_filepath.name)
        self._logger.log_copy(rep_filepath.name)

    def _edit_file(self, source_filepath: Path, file_info: FileInfo) -> None:
        source_filepath.copy(file_info.copy_path)
        file_info.mod_date = datetime.fromtimestamp(
            source_filepath.stat().st_mtime)
        self._logger.log_copy(file_info.name)

    def _remove_files(self):
        for k, v in self._file_dict.items():
            if not v.was_seen:
                shutil.rmtree(v.copy_path, True)
                self._file_dict.pop(k, None)
                self._logger.log_remove(v.name)

            else:
                v.was_seen = False


def main():
    args = parse_args()
    source = Path(os.path.abspath(args.source_path))
    replica = Path(os.path.abspath(args.replica_path))
    logfile = Path(os.path.abspath(args.log_path))
    syncer = Syncer(source, replica, logfile)
    for _ in range(args.sync_amount):
        syncer.sync()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
