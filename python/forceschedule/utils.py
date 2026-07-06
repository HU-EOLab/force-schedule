"""
General python utils to operate on the FORCE datacube
"""
import datetime
import inspect
import os
import re
import secrets
import shutil
import warnings
from pathlib import Path
from typing import Dict, Optional, Union, List, Any, Generator
from unittest import TestCase

# regex to match tile-ids
rx_tile_id = re.compile(r'^X\d{4}_Y\d{4}$')
rx_tile = re.compile(r'.*(?P<tileid>X\d{4}_Y\d{4}).*')

rx_level2_product = re.compile(
    r'(?P<date>\d{8})_LEVEL2_(?P<sensor>[^_. ]+)'
    r'_(?P<product>[^_. ]+)\.(?P<ext>tif|bsq|bil|bip|cog)$'
)

DATE = Union[str, datetime.datetime, datetime.date]
DATETIME = Union[str, datetime.datetime, datetime.date]


def to_datetime(
    input: Optional[DATETIME]
) -> Optional[datetime.datetime]:
    if input is None:
        return None
    elif isinstance(input, str):
        return datetime.datetime.fromisoformat(input)
    elif isinstance(input, datetime.datetime):
        return datetime.datetime(input.date())
    elif isinstance(input, datetime.datetime):
        return input
    else:
        raise TypeError(f"Invalid date type: {type(input)}")


def to_date(
    input: Optional[DATE]
) -> Optional[datetime.date]:
    if input is None:
        return None
    elif isinstance(input, str):
        return datetime.datetime.fromisoformat(input).date()
    elif isinstance(input, datetime.datetime):
        return input.date()
    elif isinstance(input, datetime.date):
        return input
    else:
        raise TypeError(f"Invalid date type: {type(input)}")


def find_tile_folders(path: Union[Path, str]) -> Generator[Path, Any, None]:
    """
    Returns a generator of FORCE tile folders in the given path.
    E.g., folders named like "X0045_Y0050", but not "mosaic" or "provenance".
    """
    path = Path(path)
    for e in os.scandir(path):
        if e.is_dir() and re.match(rx_tile_id, e.name):
            yield Path(e.path)


def find_git_root(path: str | Path) -> Path:
    """
    Find the root directory of the Git repository containing the given path.

    Args:
        path: A file or directory path.

    Returns:
        Path to the `.git` parent directory (i.e., the repo root),
        or None if not found.
    """
    path = Path(path).resolve()
    # Start from the given path and move upward
    for current in [path, *path.parents]:
        if (current / ".git").exists():
            return current
    raise ValueError(f"No Git root found for path: {path}")


class FORCEMonitorTestCase(TestCase):

    @classmethod
    def createTestOutputDirectory(cls,
                                  root: Union[Path, str] = 'test-outputs',
                                  subdir: Optional[Union[str, Path]] = None,
                                  cleanup: bool = False,
                                  max_length: int = 200) -> Path:
        """
        Returns the path to a test output directory.
        Defaults to: <repo>/<root>/<test module>/<test class>/<test method>

        :param max_length: the maximum length of the path.
            If the path exceeds this limit, it will be hashed
            and the has used for a directory <DIR_REPO>/<root>/<hash>.
        :param root: str, name of the folder for test output below the
        repository root. Defaults to <repo>/test-outputs.
        :param subdir: str or Path with subdirectories to append.
        :param cleanup: bool, set True to delete existing test ouptuts.
        :return: Path
        """
        """
        :return:
        """

        DIR_REPO = find_git_root(__file__)

        folders = []
        if isinstance(cls, type):
            folders.append(cls.__module__)
            folders.append(cls.__name__)

        else:
            if hasattr(cls, '__class__'):
                folders.append(cls.__class__.__module__)
                folders.append(cls.__class__.__name__)
            else:
                folders.append(cls.__name__)

        if hasattr(cls, '_testMethodName'):
            folders.append(cls._testMethodName)
        else:
            # add caller name
            frame_info = inspect.currentframe().f_back
            caller_name = frame_info.f_code.co_name
            folders.append(caller_name)

        if subdir:
            subdir = Path(subdir)
            folders.append(subdir)

        p = Path(DIR_REPO) / root / Path(*folders)

        if len(p.as_posix()) > max_length:
            p2 = Path(DIR_REPO) / root / secrets.token_urlsafe(8).upper()
            info = [f'Path exceeds max_length ({max_length}: {p}).',
                    f'Use random name instead: {p2}']
            warnings.warn('\n'.join(info), stacklevel=2)
            p = p2

        if cleanup and p.exists() and p.is_dir():
            shutil.rmtree(p)
        os.makedirs(p, exist_ok=True)
        return p


class FORCEConfig(object):
    """
    Provides access to basic config variables of a FORCE datacube.
    """

    def __init__(
        self,
        path: Union[None, Path, str] = None,
        replace: Optional[Dict[str, str]] = None

    ):

        self.FORCE_IMAGE: str = ''
        self.USER_GROUP: str = ''

        self.DIR_CSD_META: Path = Path()
        self.DIR_CREDENTIALS: Path = Path()
        self.DIR_WVP: Path = Path()

        self.DIR_LANDSAT_IMAGES: Path = Path()
        self.DIR_LANDSAT_LINKS: Path = Path()
        self.FILE_LANDSAT_QUEUE: Path = Path()
        self.FILE_LANDSAT_AOI: Path = Path()

        self.DIR_SENTINEL2_IMAGES: Path = Path()
        self.FILE_SENTINEL2_QUEUE: Path = Path()
        self.FILE_SENTINEL2_AOI: Path = Path()

        self.FILE_ARD_SENTINEL2_PARAM: Path = Path()
        self.FILE_ARD_LANDSAT_OLI_PARAM: Path = Path()
        self.FILE_ARD_LANDSAT_TM_PARAM: Path = Path()
        self.FILE_BASE_PARAM: Path = Path()

        self.DIR_ARD_CUBE: Path = Path()
        self.DIR_ARD_LOG: Path = Path()
        self.DIR_ARD_REPORT: Path = Path()

        if path is not None:
            self.loadFromPath(path, replace)

    def loadFromPath(
        self,
        path: Union[Path, str],
        replace: Optional[Dict[str, str]] = None
    ):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r') as f:
            data = [line.strip() for line in f.read().split('\n')]
            data = [line.strip().split('=') for line in data if len(line) > 0]
            data = {kv[0].strip(): kv[1].strip() for kv in data}

        if isinstance(replace, dict):
            for k in list(data.keys()):
                if re.search(r'^(DIR|FILE)_', k):
                    v = data[k]
                    for k2, v2 in replace.items():
                        if v.startswith(k2):
                            data[k] = v2 + v.removeprefix(k2)

        def get_path(key: str) -> Path:
            if key not in data:
                raise KeyError(f"Key {key} not found in config file")
            return Path(data[key])

        self.FORCE_IMAGE = data['FORCE_IMAGE']
        self.USER_GROUP = data['USER_GROUP']

        self.DIR_CSD_META = get_path("DIR_CSD_META")
        self.DIR_CREDENTIALS = get_path("DIR_CREDENTIALS")
        self.DIR_WVP = get_path("DIR_WVP")

        self.DIR_LANDSAT_IMAGES = get_path("DIR_LANDSAT_IMAGES")
        self.DIR_LANDSAT_LINKS = get_path("DIR_LANDSAT_LINKS")
        self.FILE_LANDSAT_QUEUE = get_path("FILE_LANDSAT_QUEUE")
        self.FILE_LANDSAT_AOI = get_path("FILE_LANDSAT_AOI")

        self.DIR_SENTINEL2_IMAGES = get_path("DIR_SENTINEL2_IMAGES")
        self.FILE_SENTINEL2_QUEUE = get_path("FILE_SENTINEL2_QUEUE")
        self.FILE_SENTINEL2_AOI = get_path("FILE_SENTINEL2_AOI")

        self.FILE_ARD_SENTINEL2_PARAM = get_path("FILE_ARD_SENTINEL2_PARAM")
        self.FILE_ARD_LANDSAT_OLI_PARAM = get_path(
            "FILE_ARD_LANDSAT_OLI_PARAM")
        self.FILE_ARD_LANDSAT_TM_PARAM = get_path("FILE_ARD_LANDSAT_TM_PARAM")
        self.FILE_BASE_PARAM = get_path("FILE_BASE_PARAM")

        self.DIR_ARD_CUBE = get_path("DIR_ARD_CUBE")
        self.DIR_ARD_LOG = get_path("DIR_ARD_LOG")
        self.DIR_ARD_REPORT = get_path("DIR_ARD_REPORT")

        self._data = data
        self._replace = replace

    def sanity_check(self) -> List[str]:
        errors = []

        for k, v in self.__dict__.items():
            if k.startswith('DIR') or k.startswith('FILE'):
                if not isinstance(v, Path):
                    errors.append(f"{k} is not a Path object: {v}")
                    continue
            if k.startswith('FILE') and 'QUEUE' not in k:
                v: Path
                if not v.is_file():
                    errors.append(f"Not a file: {k}={v}")
            elif k.startswith('DIR'):
                v: Path
                if not v.is_dir():
                    errors.append(f"Not a dir: {k}={v}")
        return errors
