import os
import glob
import datetime
import re
from itertools import islice
from pathlib import Path
from typing import List, Union

from osgeo import ogr, osr

ogr.UseExceptions()

rx_tileid = re.compile(r'X\d{4}_Y\d{4}')
rx_boafile = re.compile(r'^(?P<date>\d{8})_LEVEL2_(?P<sensor>[^_]+)_BOA\.tif$')


def read_config(path_config):
    raise NotImplementedError()


def batched(iterable, chunk_size):
    iterator = iter(iterable)
    while chunk := list(islice(iterator, chunk_size)):
        yield chunk


def collect_image_data(base_path):
    images = []
    for root, _, files in os.walk(base_path):
        for file_name in files:
            if file_name.endswith('.BOA'):
                tileid = os.path.basename(root)
                filepath = os.path.join(root, file_name)
                date_obs = datetime.datetime.strptime(file_name.split('_')[2], '%Y%m%d').date()
                date_created = datetime.date.fromtimestamp(os.path.getctime(filepath))
                qai_exists = os.path.exists(filepath.replace('.BOA', '.QAI'))

                images.append({
                    'tileid': tileid,
                    'filename': file_name,
                    'filepath': filepath,
                    'date_obs': date_obs,
                    'date_created': date_created,
                    'qai_exists': 1 if qai_exists else 0
                })
    return images


def add_table_features(layer, images):
    for image in images:
        feature_defn = layer.GetLayerDefn()
        feature = ogr.Feature(feature_defn)

        feature.SetField('tileid', image['tileid'])
        feature.SetField('filename', image['filename'])
        feature.SetField('filepath', image['filepath'])
        feature.SetField('date_obs', image['date_obs'].strftime('%Y-%m-%d'))
        feature.SetField('date_created', image['date_created'].strftime('%Y-%m-%d'))
        feature.SetField('qai_exists', image['qai_exists'])

        layer.CreateFeature(feature)
        feature = None


def collect_tilestats(tiledirs: List[Path]):
    """

    :param tiledir:
    :return:
    """
    if not isinstance(tiledirs, list):
        tiledirs = [tiledirs]
    results = []
    for tiledir in tiledirs:
        assert tiledir.is_dir()
        tileid = tiledir.name
        tile_results = list()
        for p in os.scandir(tiledir):
            if m := rx_boafile.match(p.name):
                bn = re.sub(r'_BOA\.tif$', '', p.path)
                date_created = datetime.date.fromtimestamp(os.path.getctime(p.path))
                date_modified = datetime.date.fromtimestamp(os.path.getmtime(p.path))

                info = {'path': p.path,
                        'name': p.name,
                        'sensor': m.group('sensor'),
                        'date': datetime.datetime.strptime(m.group('date'), '%Y%m%d'),
                        'created': date_created,
                        'modified': date_modified,
                        'OVR': os.path.isfile(bn + '_OVR.tif'),
                        'QAI': os.path.isfile(bn + '_QAI.tif'),
                        'VZN': os.path.isfile(bn + '_VZN.tif'),
                        'HOT': os.path.isfile(bn + '_HOT.tif'),
                        'OVV': os.path.isfile(bn + '_OVV.jpg')
                        }
                tile_results.append(info)

        results.append((tileid, tile_results))
    return results


def create_force_product_stats_db(path_product: Union[str, Path],
                                  path_stats_db: Union[str, Path],
                                  path_grid: Union[str, Path, None] = None,
                                  n_processes: int = 10,
                                  n_tiles_max: int = None):
    path_product = Path(path_product)
    path_stats_db = Path(path_stats_db)

    if path_grid is None:
        path_grid = path_product.parents[0] / 'vector' / 'datacube-grid.gpkg'
    else:
        path_grid = Path(path_grid)
    assert path_grid.is_file()

    tile_folders = []
    for p in os.scandir(path_product):
        if p.is_dir() and rx_tileid.match(p.name):
            tile_folders.append(Path(p.path))

    if n_tiles_max and len(tile_folders) > n_tiles_max:
        tile_folders = tile_folders[0:n_tiles_max]

    drvMEM: ogr.Driver = ogr.GetDriverByName('Memory')
    drvGPKG: ogr.Driver = ogr.GetDriverByName('GPKG')

    ds: ogr.DataSource = drvMEM.CreateDataSource('')

    prefix = path_product.name
    prefix_data = prefix + '_data'
    prefix_tiles = prefix + '_tiles'

    TILEIDS = set()

    # init tiles layer
    def addToDatabase(results: list):

        lyr = ds.GetLayerByName(prefix_data)
        if not isinstance(lyr, ogr.Layer):
            lyr: ogr.Layer = ds.CreateLayer(prefix_data, geom_type=ogr.wkbNone)
            lyr.CreateField(ogr.FieldDefn('tileid', ogr.OFTString))
            tileid, filedata = results[0]

            for k, v in filedata[0].items():

                if isinstance(v, float):
                    fieldType = ogr.OFTReal
                elif isinstance(v, int):
                    fieldType = ogr.OFTInteger
                elif isinstance(v, datetime.date):
                    fieldType = ogr.OFTDate
                elif isinstance(v, datetime.datetime):
                    fieldType = ogr.OFTDateTime
                elif isinstance(v, bool):
                    fieldType = ogr.OFTBinary
                elif isinstance(v, str):
                    fieldType = ogr.OFTString
                else:
                    raise NotImplementedError()
                lyr.CreateField(ogr.FieldDefn(k, fieldType))
        ldefn = lyr.GetLayerDefn()
        for (tileid, fileinfos) in results:
            print(f'Tile: {tileid} found {len(fileinfos)} items')
            TILEIDS.add(tileid)
            for fileinfoDict in fileinfos:
                feature: ogr.Feature = ogr.Feature(ldefn)
                feature.SetField('tileid', tileid)
                for k, v in fileinfoDict.items():
                    if isinstance(v, (datetime.date, datetime.datetime)):
                        v = str(v)
                    feature.SetField(k, v)
                lyr.CreateFeature(feature)
        s = ""

    n_total = len(tile_folders)
    chunksize = max(1, int(n_total / n_processes))

    n_tiles_done = 0
    for batch in batched(tile_folders, chunksize):
        addToDatabase(collect_tilestats(batch))
        n_tiles_done += len(batch)

    dsGridAll: ogr.DataSource = ogr.Open(path_grid.as_posix())
    lyrGridAll: ogr.Layer = dsGridAll.GetLayer(0)

    lyrGrid: ogr.Layer = ds.CreateLayer(prefix_tiles, geom_type=ogr.wkbPolygon, srs=lyrGridAll.GetSpatialRef())
    lyrGrid.CreateField(ogr.FieldDefn('tileid', ogr.OFTString))
    ldefn = lyrGrid.GetLayerDefn()
    for f in lyrGridAll:
        f: ogr.Feature
        tileid = f.GetField('Tile_ID')
        if tileid in TILEIDS:
            f2: ogr.Feature = ogr.Feature(ldefn)
            f2.SetGeometry(f.GetGeometryRef())
            f2.SetField('tileid', tileid)
            lyrGrid.CreateFeature(f2)

    #
    # write in-memory database to GPKG
    drvGPKG.CopyDataSource(ds, path_stats_db.as_posix())
    # todo: create spatial views
    # overview, by tile
    # overview, by tile and year / decade


def create_spatial_views(path_gpkg: Path):
    path_gpkg = Path(path_gpkg)
    ds: ogr.DataSource = ogr.Open(path_gpkg.as_posix())

    # see https://gis.stackexchange.com/questions/438574/create-view-and-display-in-qgis-of-a-spatial-table-in-geopackage-or-spatialite
    """
SELECT T.geom, 
T.tileid as tileid,
COUNT(D.tileid) as n,
COUNT(D.QAI) as n_qai,
COUNT(D.OVR) as n_ovr,
MIN(D.date) as obs_first,
MAX(D.date) as obs_last,
MIN(D.created) as created_first,
MAX(D.created) as created_last
FROM  ard_data as D join ard_tiles as T 
ON D.tileid = T.tileid
GROUP BY T.tileid 
    """


# Base path to the directory generated by FORCE software
path_product = r'K:\dc\deu\ard'

root = Path(__file__).parents[1]
path_stats_db = root / 'tmp/ard_stats.gpkg'

create_force_product_stats_db(path_product, path_stats_db, n_tiles_max=10)
