import unittest
from pathlib import Path

from tqdm.auto import tqdm

from forceschedule.monitor import FORCEMonitor
from forceschedule.utils import FORCEMonitorTestCase

PATH_SETTINGS = "~/Mount/Aldhani/dc/force-schedule/config/config.txt"
PATH_SETTINGS = Path(PATH_SETTINGS).expanduser()

replace = {'/data/Aldhani': '/home/jakimowb/Mount/Aldhani'}


def test_output_dir() -> Path:
    d = Path(__file__).parent / 'outputs'
    d.mkdir(exist_ok=True)
    return d


class MyTestCase(FORCEMonitorTestCase):

    def test_monitor_update(self):

        tmp = self.createTestOutputDirectory()
        path_save = tmp / 'monitor.duckdb'
        path_save.mkdir(exist_ok=True)

        monitor = FORCEMonitor(replace=replace)
        monitor.initDB()
        monitor.load_config(PATH_SETTINGS)

        min_time = '2026-01-01 00:00:00'
        max_time = '2026-03-01 23:59:59'

        monitor.update_db(min_time=min_time, max_time=max_time)
        print(monitor.status())
        monitor.update_db(min_time=max_time)
        print(monitor.status())
        monitor.saveDB(path_save)

    def test_monitor(self):
        tmp = self.createTestOutputDirectory()
        path_save = tmp / 'monitor.duckdb'

        if not path_save.is_dir():
            path_save.mkdir(exist_ok=True)
            monitor = FORCEMonitor(replace=replace)
            monitor.initDB()
            monitor.load_config(PATH_SETTINGS)
            monitor.update_db()
            print(monitor.status())
            monitor.saveDB(path_save)

        monitor = FORCEMonitor.loadDB(path_save)
        monitor.status()
        monitor._update_ard_tiles()

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
        tmp = self.createTestOutputDirectory()
        path_save = tmp / 'monitor.duckdb'
        path_save.mkdir(exist_ok=True)
        monitor = FORCEMonitor(config=PATH_SETTINGS, replace=replace)
        monitor.initDB()
        monitor._update_ard_tiles()


if __name__ == '__main__':
    unittest.main()
