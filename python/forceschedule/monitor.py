import datetime
import re
from itertools import chain
from pathlib import Path
from typing import Union, Optional, Dict, Any, Generator, List

import duckdb
import pandas as pd
from tqdm import tqdm


class FORCEMonitor(object):
    TABLE_ARD_LOG = 'ard_log'  # collects ARD log files
    TABLE_CONFIG = 'config'

    C_DIR_ARD_LOG = 'DIR_ARD_LOG'

    def __init__(
        self,
        replace: Optional[Dict[str, str]] = None,
    ):

        if replace is None:
            replace = dict()

        self.con = duckdb.connect(database=':memory:')
        self.replace = replace

    def initDB(self):
        """
        Create a DuckDB database with the cube metadata
        """
        c = self.con
        c.execute("INSTALL spatial;")
        c.execute("LOAD spatial;")

        # table for datacube configuration
        c.execute(
            f"CREATE TABLE IF NOT EXISTS {self.TABLE_CONFIG} ("
            f"key VARCHAR PRIMARY KEY,"
            f"value VARCHAR,"
            f");"
        )

        # table for ARD log file information
        c.execute(
            f"CREATE TABLE IF NOT EXISTS {self.TABLE_ARD_LOG} ("
            "name VARCHAR PRIMARY KEY,"
            "sceneid VARCHAR,"
            "failed BOOLEAN,"
            "m_time TIMESTAMP,"
            "path VARCHAR UNIQUE,"
            ");"
        )

    def _config_value(self, key: str) -> str:
        c = self.con.cursor()

        result = c.execute(
            f"SELECT value FROM {self.TABLE_CONFIG} "
            f"WHERE key = ?", (key,)
        ).fetchone()

        if result:
            return str(result[0])
        else:
            raise KeyError(f"Key not found in config table: {key}")

    def load_config(self, path: Union[Path, str]):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r') as f:
            data = [l.strip() for l in f.read().split('\n')]
            data = [l.strip().split('=') for l in data if len(l) > 0]
            data = {kv[0].strip(): kv[1].strip() for kv in data}

        if isinstance(self.replace, dict):
            for k in list(data.keys()):
                if re.search(r'^(DIR|FILE)_', k):
                    v = data[k]
                    for k2, v2 in self.replace.items():
                        if v.startswith(k2):
                            data[k] = v2 + v.removeprefix(k2)

        to_insert = list(data.items())
        self.con.executemany(f"INSERT OR REPLACE INTO {self.TABLE_CONFIG} (key, value) VALUES (?, ?)", to_insert)
        s = ""

    def get_log_files(
        self,
        dir_path: Union[Path, str],
        patterns: Union[str, List[str]] = "*.log",

    ) -> Generator[Path, Any, None]:
        dir_path = Path(dir_path)
        if isinstance(patterns, str):
            patterns = [patterns]
        generators = (dir_path.rglob(p) for p in patterns)
        for p in chain.from_iterable(generators):
            if p.is_file():
                yield p

        #
        # for p in dir_path.rglob(pattern):
        #     if p.is_file():
        #         yield p

    def status(self) -> str:

        query = ("SELECT COUNT(*) FROM ard_log "
                 "WHERE failed = TRUE")
        n_failed = self.con.execute(query).fetchone()[0]
        query = ("SELECT COUNT(*) FROM ard_log "
                 "WHERE failed = FALSE")
        n_success = self.con.execute(query).fetchone()[0]

        query = ("SELECT MIN(m_time), MAX(m_time) FROM ard_log")
        min_date, max_date = self.con.execute(query).fetchone()

        info = [
            f'ARD log status: {self._config_value(self.C_DIR_ARD_LOG)}',
            f'Total:   {n_success + n_failed}',
            f'Success: {n_success}',
            f'Failed:  {n_failed}',
            f'Files created between: {min_date} and {max_date}',
        ]

        return '\n'.join(info)

    def _update_ard_tiles(self):
        pass

    def _update_ard_log(
        self,
        m_time_min: Optional[datetime.datetime] = None,
        m_time_max: Optional[datetime.datetime] = None,
    ):

        patterns = ["*.log", "*.fail"]
        files = list(
            self.get_log_files(
                self._config_value(self.C_DIR_ARD_LOG), patterns=patterns)
        )
        payload = []

        for f in tqdm(files, desc=f'Updating ARD log ("{patterns}")'):
            f: Path
            stat = f.stat()
            m_time = datetime.datetime.fromtimestamp(stat.st_mtime)

            if m_time_min and m_time_min > m_time:
                continue
            if m_time_max and m_time_max < m_time:
                continue

            payload.append(
                {'name': f.name,
                 'sceneid': f.name.split('.')[0],
                 'failed': f.name.endswith('.fail'),
                 'm_time': m_time,
                 'path': str(f),
                 }
            )
        if len(payload) == 0:
            print(f"No log files found for pattern '{patterns}' created between {m_time_min} and {m_time_max}")
            return

        df_staging = pd.DataFrame(payload)
        self.con.register("df_param", df_staging)
        # 3. Bulk insert using ON CONFLICT in a single query
        self.con.execute(
            f"""
            INSERT INTO {self.TABLE_ARD_LOG} (name, sceneid, failed, m_time, path) 
            SELECT name, sceneid, failed, m_time, path  
            FROM df_param  
            """
        )
        self.con.unregister("df_param")

    def update_db(
        self,
        min_time: Union[str, datetime.datetime, None] = None,
        max_time: Union[str, datetime.datetime, None] = None,
    ):
        """
        Updates the database with log files
        """
        query = f"SELECT MIN(m_time), MAX(m_time) FROM {self.TABLE_ARD_LOG}"

        if isinstance(min_time, str):
            min_time = datetime.datetime.fromisoformat(min_time)
        if isinstance(max_time, str):
            max_time = datetime.datetime.fromisoformat(max_time)

        m_time_min, m_time_max = self.con.execute(query).fetchone()

        # by default, update only files created after the last update
        if min_time is None:
            min_time = m_time_min

        # write *.log and *.fail files into the same table ard_log
        self._update_ard_log(m_time_min=min_time, m_time_max=max_time)

        # update the ARD tile table
        self._update_ard_tiles()

    def logfile_content(self, scene_id: str) -> Generator[Dict[str, Any], Any, None]:
        """
        Returns the content of the log file for a given sceneid or file path
        """

        query = (f"SELECT * FROM {self.TABLE_ARD_LOG} "
                 f"WHERE sceneid = '{scene_id}' OR path = '{scene_id}' OR name = '{scene_id}'")

        cursor = self.con.execute(query)
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            data = dict(zip(columns, row))
            if 'content' not in data:
                with open(data['path'], 'r') as f:
                    data['content'] = f.read()
            yield data

    @staticmethod
    def loadDB(path):
        path = Path(path)
        if not path.is_dir():
            raise NotADirectoryError(f"The path {path} is not a directory")

        monitor = FORCEMonitor()
        con = monitor.con
        con.execute(f"IMPORT DATABASE '{path}';")
        print(con.execute("SHOW TABLES;").fetchall())
        return monitor

    def saveDB(self, path):
        path = Path(path)

        self.con.execute(f"EXPORT DATABASE '{path}';")

    def closeDB(self):
        self.con.close()
