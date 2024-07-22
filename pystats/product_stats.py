import argparse
import datetime
import os
import re
import sys
from itertools import islice
from multiprocessing import Pool
from pathlib import Path
from typing import List, Optional, Union

from osgeo import ogr

ogr.UseExceptions()

drvMEM: ogr.Driver = ogr.GetDriverByName('Memory')
drvGPKG: ogr.Driver = ogr.GetDriverByName('GPKG')

rx_tileid = re.compile(r'X\d{4}_Y\d{4}')
rx_boafile = re.compile(r'^(?P<date>\d{8})_LEVEL2_(?P<sensor>[^_]+)_BOA\.tif$')


def read_config(path_config):
    raise NotImplementedError()


def parse_tile_ids(text) -> List[str]:
    return list(rx_tileid.findall(text))


def read_tile_ids(path_tile_ids) -> List[str]:
    path_tile_ids = Path(path_tile_ids)
    assert path_tile_ids.is_file()

    ids = []
    with open(path_tile_ids, 'r') as f:
        for line in f.readlines():
            ids.extend(parse_tile_ids(line))
    return ids


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


def collect_tilestats(tile_dirs: List[Path]) -> list[tuple[str, list[dict]]]:
    """

    :param tile_dirs:
    :return:
    """
    if not isinstance(tile_dirs, list):
        tile_dirs = [tile_dirs]
    results = []
    for tile_dir in tile_dirs:
        tile_dir: Path
        assert tile_dir.is_dir()
        tile_id: str = tile_dir.name
        tile_results = list()
        for p in os.scandir(tile_dir):
            if m := rx_boafile.match(p.name):
                bn = re.sub(r'_BOA\.tif$', '', p.path)
                date_created = datetime.date.fromtimestamp(os.path.getctime(p.path))
                date_modified = datetime.date.fromtimestamp(os.path.getmtime(p.path))

                info = {'name': p.name,
                        'sensor': m.group('sensor'),
                        'date': datetime.datetime.strptime(m.group('date'), '%Y%m%d'),
                        'created': date_created,
                        'modified': date_modified,
                        'OVR': os.path.isfile(bn + '_OVR.tif'),
                        'QAI': os.path.isfile(bn + '_QAI.tif'),
                        'VZN': os.path.isfile(bn + '_VZN.tif'),
                        'HOT': os.path.isfile(bn + '_HOT.tif'),
                        'OVV': os.path.isfile(bn + '_OVV.jpg'),
                        'path': p.path,
                        }
                tile_results.append(info)

        results.append((tile_id, tile_results))
    return results


def error_callback(*args, **kwds):
    print(f'Error: {args}\n{kwds}', file=sys.stderr)
    s = ""


def create_force_product_stats_db(path_product: Union[str, Path],
                                  path_stats_db: Union[str, Path],
                                  path_grid: Union[str, Path, None] = None,
                                  n_processes: int = 10,
                                  tile_ids: Optional[List[str]] = None,
                                  n_tiles_max: int = None):
    path_product = Path(path_product)
    path_stats_db = Path(path_stats_db)

    assert not path_stats_db.is_file(), f'{path_stats_db} already exists.'

    if path_grid is None:
        path_grid = path_product.parents[0] / 'vector' / 'datacube-grid.gpkg'
    else:
        path_grid = Path(path_grid)
    assert path_grid.is_file()

    tile_folders = []
    for p in os.scandir(path_product):
        if p.is_dir() and rx_tileid.match(p.name):
            if tile_ids and p.name not in tile_ids:
                continue
            tile_folders.append(Path(p.path))

    if n_tiles_max and len(tile_folders) > n_tiles_max:
        tile_folders = tile_folders[0:n_tiles_max]

    coptions = [] #  ['VERSION=1.4']
    ds: ogr.DataSource = drvGPKG.CreateDataSource(path_stats_db.as_posix(), coptions)
    assert isinstance(ds, ogr.DataSource), f'unable to create {path_stats_db}'

    prefix = path_product.name
    lyrname_data = prefix + '_data'
    lyrname_tiles = prefix + '_tiles'

    TILEIDS = set()

    n_total = len(tile_folders)
    n_done = 0
    chunksize = max(1, int(n_total / n_processes))
    tasks = list(batched(tile_folders, chunksize))

    # init tiles layer
    def addToDatabase(results: list):

        lyr = ds.GetLayerByName(lyrname_data)
        if not isinstance(lyr, ogr.Layer):
            lyr: ogr.Layer = ds.CreateLayer(lyrname_data, geom_type=ogr.wkbNone)
            lyr.CreateField(ogr.FieldDefn('tileid', ogr.OFTString))
            tile_id, filedata = results[0]

            for k, v in filedata[0].items():

                if isinstance(v, float):
                    field_type = ogr.OFTReal
                elif isinstance(v, int):
                    field_type = ogr.OFTInteger
                elif isinstance(v, datetime.date):
                    field_type = ogr.OFTDate
                elif isinstance(v, datetime.datetime):
                    field_type = ogr.OFTDateTime
                elif isinstance(v, bool):
                    field_type = ogr.OFTBinary
                elif isinstance(v, str):
                    field_type = ogr.OFTString
                else:
                    raise NotImplementedError()
                lyr.CreateField(ogr.FieldDefn(k, field_type))
        ldefn = lyr.GetLayerDefn()

        for (tile_id, file_infos) in results:
            TILEIDS.add(tile_id)
            for fileinfoDict in file_infos:
                feature: ogr.Feature = ogr.Feature(ldefn)
                feature.SetField('tileid', tile_id)
                for k, v in fileinfoDict.items():
                    if isinstance(v, (datetime.date, datetime.datetime)):
                        v = str(v)
                    feature.SetField(k, v)
                lyr.CreateFeature(feature)
            nonlocal n_done
            n_done += 1

            print(
                'Search {}/{} {:0.2f}%: Found {} in {}'.format(n_done, n_total, 100 * n_done / n_total, len(file_infos),
                                                               tile_id), end='\r')
        # s = ""

    print('Search started...')

    pool = Pool(processes=n_processes)
    for job in tasks:
        pool.apply_async(collect_tilestats, args=(job,), callback=addToDatabase, error_callback=error_callback)
    pool.close()
    pool.join()

    dsGridAll: ogr.DataSource = ogr.Open(path_grid.as_posix())
    lyrGridAll: ogr.Layer = dsGridAll.GetLayer(0)

    lyrGrid: ogr.Layer = ds.CreateLayer(lyrname_tiles, geom_type=ogr.wkbPolygon, srs=lyrGridAll.GetSpatialRef())
    fDefn = ogr.FieldDefn('tileid', ogr.OFTString)
    fDefn.SetNullable(False)
    fDefn.SetUnique(True)
    lyrGrid.CreateField(fDefn)
    ldefn = lyrGrid.GetLayerDefn()
    for f in lyrGridAll:
        f: ogr.Feature
        tileid = f.GetField('Tile_ID')
        if tileid in TILEIDS:
            f2: ogr.Feature = ogr.Feature(ldefn)
            f2.SetGeometry(f.GetGeometryRef())
            f2.SetField('tileid', tileid)
            lyrGrid.CreateFeature(f2)

    del lyrGrid

    # dsGPKG: ogr.DataSource = drvGPKG.CopyDataSource(ds, path_stats_db.as_posix())
    print('Create indices...')

    r = ds.ExecuteSQL(f'CREATE UNIQUE INDEX idx_tileid1 ON {lyrname_tiles}(tileid)')
    r = ds.ExecuteSQL(f'CREATE INDEX idx_tileid2 ON {lyrname_data}(tileid)')
    s = ""

    print('Create data views...')
    create_spatial_views(ds, name_tiles=lyrname_tiles, name_data=lyrname_data)

    print('Set PRAGMAS')
    print_layer_definition(ds.ExecuteSQL('PRAGMA quick_check;'), print_features=True)
    ds.ExecuteSQL('PRAGMA query_only=True;')
    print_layer_definition(ds.ExecuteSQL('PRAGMA pragma_list;'), print_features=True)

    print('Done!')


def create_spatial_views(path_gpkg: Path,
                         name_tiles: str = 'ard_tiles',
                         name_data: str = 'ard_data',
                         as_view: bool = True):
    if isinstance(path_gpkg, ogr.DataSource):
        ds: ogr.DataSource = path_gpkg
    else:
        path_gpkg = Path(path_gpkg)
        ds: ogr.DataSource = ogr.Open(path_gpkg.as_posix(), True)

    name_view = f'{name_data}'

    sql = """SELECT * FROM gpkg_geometry_columns WHERE table_name = \"{}\" """.format(name_tiles)
    for f in ds.ExecuteSQL(sql):
        f: ogr.Feature
        # col_geom = f.GetField('column_name')
        geom_type = f.GetField('geometry_type_name')
        srs_id = f.GetField('srs_id')
        has_z = f.GetField('z')
        has_m = f.GetField('m')
        break

    # see https://gis.stackexchange.com/questions/438574/create-view-and-display-in-qgis-of-a-spatial-table-in-geopackage-or-spatialite
    # see https://gdal.org/drivers/vector/gpkg.html
    sql1 = """SELECT 
    T.fid AS OGC_FID,
    T.geom AS geom,
    T.tileid AS tileid"""

    sql2 = """      COUNT(*) as n,
    SUM(D.QAI) as n_qai,
    SUM(D.OVR) as n_ovr,
    DATE(MIN(D.date)) as obs_first,
    DATE(MAX(D.date)) as obs_last,
    DATE(MIN(D.created)) as created_first,
    DATE(MAX(D.created)) as created_last """

    sql3 = f"FROM {name_data} as D JOIN {name_tiles} as T\nON D.tileid = T.tileid "

    def derive_table(view_name: str, view_definition: str, as_view: bool):
        if as_view:
            sql1 = f"CREATE VIEW {view_name} AS\n{view_definition};"
            sql2 = f"INSERT INTO gpkg_contents (table_name, identifier, data_type, srs_id) VALUES ( '{view_name}', '{view_name}', 'features', {srs_id});"
            sql3 = f"INSERT INTO gpkg_geometry_columns (table_name, column_name, geometry_type_name, srs_id, z, m) values ('{view_name}', 'geom', '{geom_type}', {srs_id}, {has_z}, {has_m});"
            ds.ExecuteSQL(sql1)
            ds.ExecuteSQL(sql2)
            ds.ExecuteSQL(sql3)
        else:
            with ds.ExecuteSQL(sql) as lyr:
                lyr2: ogr.Layer = ds.CopyLayer(lyr, view_name)
                print_layer_definition(lyr2)

    derive_table(f'{name_view}_byTile',
                 f"{sql1},\n{sql2}\n{sql3}\nGROUP BY D.tileid", as_view=as_view)
    derive_table(f'{name_view}_byTileYear',
                 f"{sql1},\nstrftime('%Y', D.date) as year,\n{sql2}\n{sql3}\nGROUP BY D.tileid, strftime('%Y', D.date)",
                 as_view=as_view)


def print_layer_definition(layer: ogr.Layer, print_features: bool = False):
    ldef: ogr.FeatureDefn = layer.GetLayerDefn()
    print(f'Layer {layer.GetName()}:')
    print(f'Geometry Field(s): {ldef.GetGeomFieldCount()}')
    for i in range(ldef.GetGeomFieldCount()):
        fdef: ogr.GeomFieldDefn = ldef.GetGeomFieldDefn(i)
        print(f'{i + 1:1}: {fdef.GetName()}: {fdef.GetType()}')

    print(f'Field(s): {ldef.GetFieldCount()}')
    for i in range(ldef.GetFieldCount()):
        fdef: ogr.FieldDefn = ldef.GetFieldDefn(i)
        print(f'{i + 1:2}: {fdef.GetName()}: {fdef.GetTypeName()}')
        s = ""
    if print_features:
        for i, f in enumerate(layer):
            f: ogr.Feature
            values = ', '.join([str(f.GetField(n)) for n in range(ldef.GetFieldCount())])
            print(f'Feature {f.GetFID()}: {values}')


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Create a GeoPackage full of stats on a FORCE datacube product',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('product', type=str, help='Path to FORCE folder that contains tile subfolders')
    parser.add_argument('stats_db', type=str, help='Output path of *.gpkg database with statistics')
    parser.add_argument('--grid_db', type=str, help='Output path of *.gpkg database with statistics')
    parser.add_argument('-i', '--tile_ids', type=str, help='List with tile ids or path to textfile with tile ids',
                        default=None)
    parser.add_argument('-p', '--n_processes', type=int, help='Number of parallel search processes', default=5)
    parser.add_argument('-t', '--max_tiles', type=int, help='Max. number of tiles to search in (for testing)',
                        default=None)
    parser.add_argument('--overwrite', help='Overwrites an existing stats_db',
                        default=False, action='store_true')

    args = parser.parse_args()
    args.product = Path(args.product).resolve()
    args.stats_db = Path(args.stats_db).resolve()
    print(f'Run {Path(__file__).name} with:')
    for k, v in args.__dict__.items():
        print(f'{k}={v}')

    if args.overwrite and args.stats_db.is_file():
        assert ogr.OGRERR_NONE == drvGPKG.DeleteDataSource(args.stats_db.as_posix())

    tile_ids = None
    if args.tile_ids:
        for t in [Path(args.tile_ids),
                  Path(args.tile_ids).resolve(),
                  args.tile_ids]:
            if isinstance(t, Path) and t.is_file():
                tile_ids = read_tile_ids(t)
                break
            if isinstance(t, str):
                tile_ids = parse_tile_ids(t)

    if isinstance(tile_ids, list):
        tile_ids = sorted(set(tile_ids))
        # print(f'Tile ids: {tile_ids}')

    create_force_product_stats_db(args.product,
                                  args.stats_db,
                                  path_grid=args.grid_db,
                                  n_tiles_max=args.max_tiles,
                                  n_processes=args.n_processes)

    if True:
        ds: ogr.DataSource = ogr.Open(args.stats_db.as_posix())
        print_layer_definition(ds.GetLayerByName('ard_tiles'))
        print_layer_definition(ds.GetLayerByName('ard_data'))
        print_layer_definition(ds.GetLayerByName('ard_data_byTile'))
