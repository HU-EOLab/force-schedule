from pathlib import Path

from forceschedule.utils import FORCEMonitorTestCase, FORCEConfig

PATH_SETTINGS = "~/Mount/Aldhani/dc/force-schedule/config/config.txt"
PATH_SETTINGS = Path(PATH_SETTINGS).expanduser()
replace = {'/data/Aldhani': '/home/jakimowb/Mount/Aldhani'}


class MyTestCase(FORCEMonitorTestCase):

    def test_config(self):
        config = FORCEConfig(PATH_SETTINGS, replace=replace)
        errors = config.sanity_check()
        self.assertTrue(len(errors) == 0, msg=f"Errors: {errors}")
