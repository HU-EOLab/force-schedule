import os
import unittest
from pathlib import Path

import psycopg
from forceschedule.monitor import (
    FORCEMonitor,
    config_value,
    create_monitor_tables,
    update_ard_logfiles,
    update_config,
)
from forceschedule.utils import FORCEMonitorTestCase
from osgeo import gdal
from tqdm.auto import tqdm

PATH_SETTINGS = "~/Mount/Aldhani/dc/force-schedule/config/config.txt"
PATH_SETTINGS = Path(PATH_SETTINGS).expanduser()

REPLACE = {"/data/Aldhani": "/home/jakimowb/Mount/Aldhani"}
gdal.UseExceptions()

if not PATH_SETTINGS.is_file():
    raise FileNotFoundError(f"Settings file not found: {PATH_SETTINGS}")

database_uri = f"""
dbname={os.environ["DBNAME"]} 
 user={os.environ["DBUSER"]} 
 password={os.environ["DBPASSWORD"]} 
 port={os.environ["DBPORT"]} 
 host={os.environ["DBHOST"]} 
"""


def test_output_dir() -> Path:
    d = Path(__file__).parent / "outputs"
    d.mkdir(exist_ok=True)
    return d


class MyTestCase(FORCEMonitorTestCase):
    def test_connect_db(self):

        con = psycopg.connect(database_uri)

        cursor = con.cursor()
        cursor.execute("SELECT version();")
        pg_info: str = cursor.fetchone()[0]
        self.assertTrue(pg_info.startswith("PostgreSQL"))

        # Test PostGIS extension
        cursor.execute("SELECT PostGIS_Full_Version();")
        postgis_info = cursor.fetchone()[0]
        self.assertTrue(postgis_info.startswith("POSTGIS="))

        cursor.close()
        con.close()

        pass

    def test_create_schema(self):

        con = psycopg.connect(database_uri)
        create_monitor_tables(con)
        con.close()
        s = ""

    def test_update_config(self):

        con = psycopg.connect(database_uri)
        update_config(con, PATH_SETTINGS)
        con.close()

    def test_read_confi(self):

        con = psycopg.connect(database_uri)
        r = config_value(con, "DIR_LANDSAT_IMAGES")
        self.assertIsInstance(r, str)

        r = config_value(con, "foobar")
        self.assertTrue(r is None)
        con.close()

    def test_update_logfiles(self):

        con = psycopg.connect(database_uri)
        update_ard_logfiles(con, PATH_SETTINGS, replacements=REPLACE)
        con.close()

    def test_monitor_readlogs(self):

        monitor = self.IMMUTABLE_MONITOR

        query = (
            "SELECT path FROM ard_log "
            "WHERE SCENEID LIKE 'S2%_MSIL1C_2026%' "
            "AND failed = True "
            "ORDER BY SCENEID"
            ""
        )

        for r in monitor.con.execute(query).fetchmany(10):
            p = Path(r[0])
            self.assertTrue(p.is_file())
            with open(p, "r") as f:
                content = f.read()
                print(content)
                s = ""

        s = ""

    def test_monitor_update(self):

        tmp = self.createTestOutputDirectory()
        path_save = tmp / "monitor.duckdb"
        # path_save.mkdir(exist_ok=True)

        if path_save.is_file():
            monitor = FORCEMonitor.loadDB(path_save)
        else:
            monitor = FORCEMonitor(replace=REPLACE)
            monitor.initDB()

        print(monitor.status())
        monitor.update_config(PATH_SETTINGS)
        # print(monitor.status())
        monitor.update_config(PATH_SETTINGS)
        # print(monitor.status())

        min_time = "2026-01-01 00:00:00"
        max_time = "2026-03-01 23:59:59"

        monitor.update_db(
            mod_time=(min_time, max_time), update_ard_log=True, update_ard_tiles=False
        )
        print(monitor.status())
        monitor.update_db(
            mod_time=(min_time, max_time), update_ard_log=True, update_ard_tiles=False
        )
        print(monitor.status())
        monitor.saveDB(path_save)

    def load_log_db(self) -> FORCEMonitor:
        tmp = self.createTestOutputDirectory()
        path_save = tmp / "monitor.duckdb"

        if not path_save.is_dir():
            path_save.mkdir(exist_ok=True)
            monitor = FORCEMonitor(replace=REPLACE)
            monitor.initDB()
            monitor.load_config(PATH_SETTINGS)
            monitor.update_db()
            print(monitor.status())
            monitor.saveDB(path_save)

        monitor = FORCEMonitor(replace=REPLACE)
        monitor.initDB()
        monitor.load_config(PATH_SETTINGS)
        return monitor

    def test_read_error_messages(self):

        monitor = self.IMMUTABLE_MONITOR

        query = "SELECT * FROM ard_log WHERE failed = True"

        cursor = monitor.con.execute(query)
        columns = [col[0] for col in cursor.description]

        error = (
            "could not create image to image transformer. "
            "Warping base failed! coregistration failed"
        )

        for row in tqdm(cursor.fetchall(), desc="Read content of failed log files"):
            data = dict(zip(columns, row))
            if "content" not in data:
                with open(data["path"], "r") as f:
                    data["content"] = f.read()
            content = data["content"]
            if error not in content:
                print(f"DIFFERENT ERROR: {data['path']}")
                print(content)

    def test_monitor_load_tiles(self):

        monitor = self.IMMUTABLE_MONITOR.clone()
        tile_ids = ["X0061_Y0059", "X0062_Y0058"]
        monitor._update_ard_tiles(tile_ids=tile_ids)
        print(monitor.status())
        monitor._update_ard_tiles(tile_ids=tile_ids)
        print(monitor.status())

    def test_monitor_load_all(self):
        tmp = self.createTestOutputDirectory()
        path_save = tmp / "monitorAll2.duckdb"
        tile_ids = ["X0061_Y0059", "X0062_Y0058"]

        if not path_save.is_file():
            path_save.parent.mkdir(exist_ok=True)
            monitor = FORCEMonitor(
                replace=REPLACE,
            )
            monitor.initDB()
            monitor.load_config(PATH_SETTINGS)
            monitor.update_db(update_ard_tiles=True, tile_ids=tile_ids, n_workers=5)
            # monitor._update_ard_tiles(n_workers=10)
            # monitor._update_ard_tiles(n_workers=10,
            #                           mod_date=('2025-01-01', None))
            # monitor._update_ard_tiles(n_workers=10,
            #                           mod_date=['2024-01-01', '2025-01-01'])
            monitor.saveDB(path_save)
        else:
            monitor = FORCEMonitor.loadDB(
                path_save,
                replace=REPLACE,
            )

        print(monitor.status())


if __name__ == "__main__":
    unittest.main()
