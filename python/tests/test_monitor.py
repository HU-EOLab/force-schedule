import unittest
from pathlib import Path

import duckdb
from _duckdb import InvalidInputException
from tqdm.auto import tqdm

from forceschedule.monitor import FORCEMonitor
from forceschedule.utils import FORCEMonitorTestCase

PATH_SETTINGS = "~/Mount/Aldhani/dc/force-schedule/config/config.txt"
PATH_SETTINGS = Path(PATH_SETTINGS).expanduser()

REPLACE = {'/data/Aldhani': '/home/jakimowb/Mount/Aldhani'}


def test_output_dir() -> Path:
    d = Path(__file__).parent / 'outputs'
    d.mkdir(exist_ok=True)
    return d


class MyTestCase(FORCEMonitorTestCase):

    @classmethod
    def setUpClass(cls):

        tmp = cls.createTestOutputDirectory()
        path_save = tmp / 'monitor.duckdb'
        if not path_save.is_file():
            # path_save.mkdir(exist_ok=True)
            monitor = FORCEMonitor(replace=REPLACE)
            monitor.initDB()
            monitor.load_config(PATH_SETTINGS)
            monitor.update_db()
            tile_ids = ['X0061_Y0059', 'X0062_Y0058']
            monitor._update_ard_tiles(tile_ids=tile_ids)
            print(monitor.status())
            monitor.saveDB(path_save)

        con = duckdb.connect(path_save, read_only=True)
        monitor = FORCEMonitor(replace=REPLACE, connection=con)
        cls.IMMUTABLE_MONITOR = monitor
        cls.IMMUTABLE_MONITOR_SRC = path_save

    def test_clone(self):

        m2 = self.IMMUTABLE_MONITOR.clone()
        m2.con.execute("CREATE TABLE test (a int);")
        self.assertIsInstance(m2.status(), str)
        s = ""

    def test_immutable_monitor(self):
        # create immutable monitor

        self.assertIsInstance(self.IMMUTABLE_MONITOR, FORCEMonitor)

        # try to add a table
        with self.assertRaises(InvalidInputException):
            self.IMMUTABLE_MONITOR.con.execute("CREATE TABLE test (a int);")

    def test_monitor_readlogs(self):

        monitor = self.IMMUTABLE_MONITOR

        query = ("SELECT path FROM ard_log "
                 "WHERE SCENEID LIKE 'S2%_MSIL1C_2026%' "
                 "AND failed = True "
                 "ORDER BY SCENEID"
                 "")

        for r in monitor.con.execute(query).fetchmany(10):
            p = Path(r[0])
            self.assertTrue(p.is_file())
            with open(p, 'r') as f:
                content = f.read()
                print(content)
                s = ""

        s = ""

    def test_monitor_update(self):

        tmp = self.createTestOutputDirectory()
        path_save = tmp / 'monitor.duckdb'
        path_save.mkdir(exist_ok=True)

        monitor = FORCEMonitor(replace=REPLACE)
        monitor.initDB()
        monitor.load_config(PATH_SETTINGS)

        min_time = '2026-01-01 00:00:00'
        max_time = '2026-03-01 23:59:59'

        monitor.update_db(min_time=min_time, max_time=max_time)
        print(monitor.status())
        monitor.update_db(min_time=max_time)
        print(monitor.status())
        monitor.saveDB(path_save)

    def load_log_db(self) -> FORCEMonitor:
        tmp = self.createTestOutputDirectory()
        path_save = tmp / 'monitor.duckdb'

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

        query = ("SELECT * FROM ard_log "
                 "WHERE failed = True")

        cursor = monitor.con.execute(query)
        columns = [col[0] for col in cursor.description]

        error = ('could not create image to image transformer. '
                 'Warping base failed! coregistration failed')

        for row in tqdm(cursor.fetchall(),
                        desc='Read content of failed log files'):
            data = dict(zip(columns, row))
            if 'content' not in data:
                with open(data['path'], 'r') as f:
                    data['content'] = f.read()
            content = data['content']
            if error not in content:
                print(f'DIFFERENT ERROR: {data["path"]}')
                print(content)

    def test_monitor_load_tiles(self):

        monitor = self.IMMUTABLE_MONITOR.clone()
        tile_ids = ['X0061_Y0059', 'X0062_Y0058']
        monitor._update_ard_tiles(tile_ids=tile_ids)
        print(monitor.status())
        monitor._update_ard_tiles(tile_ids=tile_ids)
        print(monitor.status())

    def test_monitor_load_all(self):
        tmp = self.createTestOutputDirectory()
        path_save = tmp / 'monitorAll2.duckdb'
        if not path_save.is_file():
            path_save.parent.mkdir(exist_ok=True)
            monitor = FORCEMonitor(replace=REPLACE, )
            monitor.initDB()
            monitor.load_config(PATH_SETTINGS)
            monitor.update_db(tiles=True)
            # monitor._update_ard_tiles(n_workers=10)
            # monitor._update_ard_tiles(n_workers=10,
            #                           mod_date=('2025-01-01', None))
            # monitor._update_ard_tiles(n_workers=10,
            #                           mod_date=['2024-01-01', '2025-01-01'])
            monitor.saveDB(path_save)
        else:
            monitor = FORCEMonitor.loadDB(path_save, replace=REPLACE, )

        print(monitor.status())


if __name__ == '__main__':
    unittest.main()
