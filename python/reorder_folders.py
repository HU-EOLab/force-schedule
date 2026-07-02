import concurrent.futures
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from tqdm import tqdm

from python.forceschedule.utils import (
    FORCEConfig, rx_tile_id, rx_level2_product)


def check_subdirs(cube_root: Path):
    allowed_subdirs = ['provenance', 'mosaic']
    cube_root = Path(cube_root)
    assert cube_root.is_dir()

    with os.scandir(cube_root) as scan:
        for entry in scan:
            if (
                entry.is_dir() and entry.name
                not in allowed_subdirs and not rx_tile_id.match(entry.name)
            ):
                print(f'Wrong dir: {entry.path}')


def product_files(cube_root: Path,
                  pattern=rx_level2_product,
                  n_threads=4,
                  whitelist: List[str] = None) -> List[Tuple[str, dict]]:
    """Fast reading of file information, returned
    in a JSON-izable data structure"""

    tile_dirs = []
    with os.scandir(cube_root) as scan:
        for e in scan:
            if rx_tile_id.match(e.name):
                tile_dirs.append(e.path)
    if whitelist:
        tile_dirs = [t for t in tile_dirs if t in whitelist]

    # tile_dirs = tile_dirs[0:100]

    print(f'Read file infos from {len(tile_dirs)} tile dirs in {cube_root}')

    def read_file_information(tile_dir, pattern):
        _results = []
        with os.scandir(tile_dir) as scan:
            for e in scan:
                if e.is_file():
                    if match := pattern.match(e.name):
                        infos = {'path': e.path}
                        infos.update(
                            {k: match.group(k)
                             for k in pattern.groupindex.keys()}
                        )

                        stat = e.stat()
                        infos['t_c'] = datetime.fromtimestamp(
                            stat.st_ctime
                        ).isoformat()
                        infos['t_m'] = datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat()
                        _results.append(infos)
        return _results

    results = []
    t0 = datetime.now()
    n_folders = 0

    with tqdm(total=len(tile_dirs)) as pbar:
        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = {
                executor.submit(
                    read_file_information, tile_dir, pattern
                ): i for i, tile_dir in enumerate(tile_dirs)}

            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())
                n_folders += 1
                pbar.update()

    tdiff = datetime.now() - t0
    print(f'Reading finished: {len(results)} files in {tdiff}')
    return results


config = FORCEConfig()
path_l2_json = Path(__file__).parent / 'l2_products.json'
path_lnd071_json = Path(__file__).parent / 'l2_products_l71.json'
path_lnd072_json = Path(__file__).parent / 'l2_products_l72.json'

rx_relpath = re.compile(r'X\d+_Y\d+[\\/].+')


def make_relpath(data):
    for i in range(len(data)):
        d = data[i]
        d['path'] = rx_relpath.search(d['path']).group()


def product_json(path_json, root_dir) -> dict:
    path_json = Path(path_json)
    if path_json.is_file():
        with open(path_l2_json, 'r') as f:
            return json.load(f)
    else:
        l2_products = product_files(root_dir,
                                    pattern=rx_level2_product,
                                    n_threads=6,
                                    )
        with open(path_json, 'w') as f:
            json.dump(l2_products, f, indent=2)
        return l2_products


def compare_files(data_main, data_sub) -> Dict:
    # others = {rx_relpath.search(p['path']).group(): p for p in data_sub}
    # existing = {rx_relpath.search(p['path']).group(): p for p in data_main}

    results = dict()

    return results


prod_cube_l71 = product_json(
    path_lnd071_json,
    config.DIR_ARD_CUBE / 'LND07_2021'
)
prod_cube_l72 = product_json(
    path_lnd072_json,
    config.DIR_ARD_CUBE / 'LND07_2021' / 'LND07_2021'
)
prod_cube = product_json(path_l2_json, config.DIR_ARD_CUBE)

comp1 = compare_files(prod_cube, prod_cube_l71)
comp2 = compare_files(prod_cube, prod_cube_l72)

s = ""

# check_subdirs(config.DIR_ARD_CUBE)
