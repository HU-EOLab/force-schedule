from pathlib import Path

from forceschedule.postprocess import rename_logs
from forceschedule.utils import FORCEMonitorTestCase, FORCEConfig

PATH_SETTINGS = "~/Mount/Aldhani/dc/force-schedule/config/config.txt"
PATH_SETTINGS = Path(PATH_SETTINGS).expanduser()

DIR_QUEUE = "~/Mount/Aldhani/dc/input/sentinel2"
DIR_QUEUE = Path(DIR_QUEUE).expanduser()

REPLACE = {'/data/Aldhani': '/home/jakimowb/Mount/Aldhani'}


class MyTestCase(FORCEMonitorTestCase):

    def test_rename_failed_logs(self):
        config = FORCEConfig(PATH_SETTINGS, replace=REPLACE)
        dir_log = config.DIR_ARD_LOG

        queue_files = list(sorted([Path(p) for p in DIR_QUEUE.glob(".queue*.txt")]))
        queue_file = Path('/home/jakimowb/Mount/Aldhani/dc/input/sentinel2/.test_queue-20260703150920-queue.txt')
        
        # failed_ref = []
        # for line in queue_file.read_text().splitlines():
        #     if line.endswith("FAIL"):
        #         file, err = line.split()
        #         failed_ref.append(Path(file))

        failed = rename_logs(dir_log, queue_file=queue_file, dry_run=True)

        for p in failed:
            self.assertIsInstance(p, Path)
            # self.assertTrue(p.is_file())
            self.assertTrue(p.suffix == ".fail")
