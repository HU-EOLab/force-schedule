# create GPKG with table
from pathlib import Path
from osgeo.ogr import DataSource, FeatureDefn, FieldDefn, Open, UseExceptions

UseExceptions()
path_ard_stats = Path(__file__).parent / 'ard_stats.gpkg'

ds: DataSource = Open(path_ard_stats.as_posix())

from pystats.product_stats import print_layer_definition
print_layer_definition()

# print definition of data view "ard_data_byTile"
with ds.ExecuteSQL("SELECT sql FROM sqlite_schema WHERE name='ard_data_byTile'") as lyr:
    for f in lyr:
        print(f.GetField('sql'))

# read field  types using "SELECT * ... "
FIELD_TYPES = dict()
with ds.ExecuteSQL('SELECT * FROM ard_data_byTile') as lyr:
    lyrDefn: FeatureDefn = lyr.GetLayerDefn()
    for i in range(lyrDefn.GetFieldCount()):
        fDefn: FieldDefn = lyrDefn.GetFieldDefn(i)
        print(f'{i}: {fDefn.GetName()} {fDefn.GetTypeName()}')
        FIELD_TYPES[fDefn.GetName()] = fDefn.GetTypeName()

lyr = ds.GetLayerByName('ard_data_byTile')
lyrDefn: FeatureDefn = lyr.GetLayerDefn()
for i in range(lyrDefn.GetFieldCount()):
    fDefn: FieldDefn = lyrDefn.GetFieldDefn(i)
    print(f'{i}: {fDefn.GetName()} {fDefn.GetTypeName()}')


# read field types using .GetLayerByName ... and compare
lyr = ds.GetLayerByName('ard_data_byTile')
lyrDefn: FeatureDefn = lyr.GetLayerDefn()
differing_types = []
for i in range(lyrDefn.GetFieldCount()):
    fDefn: FieldDefn = lyrDefn.GetFieldDefn(i)
    fName = fDefn.GetName()
    type1 = FIELD_TYPES[fName]
    type2 = fDefn.GetTypeName()
    if type1 != type2:
        differing_types.append(fName)
    print(f'{i}: {fName} {type1} {type2}')


assert len(differing_types) == 0, f'Differing field types: {", ".join(differing_types)}'
