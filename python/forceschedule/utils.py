"""
General python utils to operate on the FORCE datacube
"""
import os
import re
from pathlib import Path
from typing import Dict, Optional, Union

# regex to match tile-ids
rx_tile_id = re.compile(r'^X\d{4}_Y\d{4}$')
rx_tile = re.compile(r'.*(?P<tileid>X\d{4}_Y\d{4}).*')

rx_level2_product = re.compile(
    r'(?P<date>\d{8})_LEVEL2_(?P<sensor>[^_. ]+)_(?P<product>[^_. ]+)\.(?P<ext>tif|bsq|bil|bip|cog)$')

root = Path(__file__).parents[1]


class CubeConfig(object):

    def __init__(
        self,
        path: Union[Path, str],
        replace: Optional[Dict[str, str]] = None
    ):

        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file {path} not found")

        with open(path, 'r') as f:
            data = [l.strip() for l in f.read().split('\n')]
            data = [l.strip().split('=') for l in data if len(l) > 0]
            data = {kv[0].strip(): kv[1].strip() for kv in data}

        if replace is None and 'FORCETOOLS_REPLACEPATH' in os.environ:
            replace = dict()
            for line in os.environ['FORCETOOLS_REPLACEPATH'].split(','):
                line = line.strip()
                p1, p2 = line.split(':')
                replace[p1] = p2
        if replace is None:
            replace = dict()

        def get_path(key: str) -> Path:
            path = data[key]
            for k, v in replace.items():
                if path.startswith(k):
                    path = v + path.removeprefix(k)
            return Path(path)

        self.FORCE_IMAGE = data['FORCE_IMAGE']
        self.USER_GROUP = data['USER_GROUP']
        self.USER, self.GROUP = self.USER_GROUP.split(':')

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
        self.FILE_ARD_LANDSAT_OLI_PARAM = get_path("FILE_ARD_LANDSAT_OLI_PARAM")
        self.FILE_ARD_LANDSAT_TM_PARAM = get_path("FILE_ARD_LANDSAT_TM_PARAM")
        self.FILE_BASE_PARAM = get_path("FILE_BASE_PARAM")

        self.DIR_ARD_CUBE = get_path("DIR_ARD_CUBE")
        self.DIR_ARD_LOG = get_path("DIR_ARD_LOG")
        self.DIR_ARD_REPORT = get_path("DIR_ARD_REPORT")

        self._data = data

    def path_check(self):
        errors = []
        for k, v in self.__dict__.items():
            if k.startswith('FILE'):
                assert isinstance(v, Path) and v.is_file()
            elif k.startswith('DIR'):
                assert isinstance(v, Path) and v.is_dir()

    def map(self) -> Dict[str, str]:

        d = {}
        for k, v in self.__dict__.items():
            d[k] = str(v)
        return d


def cubeConfig() -> CubeConfig:
    """
    Read the config file and returns its variables
    :return: 
    """
    return CubeConfig()
