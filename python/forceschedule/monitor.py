import datetime
import os
from itertools import chain
from pathlib import Path
from typing import Union, Optional, Dict, Any, Generator, List

import duckdb
import pandas as pd
from tqdm import tqdm

from forceschedule.utils import FORCEConfig, find_tile_folders, rx_level2_product


class FORCEMonitor(object):
    TABLE_ARD_LOG = 'ard_log'  # collects ARD log files
    TABLE_CONFIG = 'config'

    C_DIR_ARD_LOG = 'DIR_ARD_LOG'

    def __init__(
        self,
        config: Union[None, FORCEConfig, str, Path] = None,
        replace: Optional[Dict[str, str]] = None,
        connection=None
    ):

        if replace is None:
            replace = dict()
        self.replace = replace

        self.config: Optional[FORCEConfig] = None

        if connection:
            self.con = connection
            # load config from database
            self.load_config_from_db()
        else:
            self.con = duckdb.connect(database=':memory:')

            if isinstance(config, (str, Path)):
                self.initDB()
                self.load_config(config)
            elif isinstance(config, FORCEConfig):
                self.initDB()
                self.config = config

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

        config = FORCEConfig(path, replace=self.replace)
        self.config = config
        to_insert = list(
            (k, str(v))
            for k, v in config.__dict__.items() if not k.startswith('_')
        )
        self.con.executemany(
            f"INSERT OR REPLACE INTO {self.TABLE_CONFIG} "
            f"(key, value) VALUES (?, ?)", to_insert
        )

    def load_config_from_db(self):

        config = FORCEConfig()

        for (k, v) in self.con.execute(
            f"SELECT * FROM {self.TABLE_CONFIG};"
        ).fetchall():
            if k in config.__dict__:
                setattr(config, k, type(config.__dict__[k])(v))
            else:
                raise KeyError(f"Key not found in config table: {k}")

        self.config = config

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

        if not self.config:
            raise ValueError("Config not loaded")

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

    def _update_ard_tiles(
        self,
        n_workers: int = 2,
        min_date: Optional[datetime.datetime] = None,
    ):
        """
        Loads the metadata of ARD files
        """
        tiles = list(find_tile_folders(self.config.DIR_ARD_CUBE))

        data = []
        for tile in tqdm(tiles, desc='Updating ARD tiles'):

            files = [e for e in os.scandir(tile) if e.is_file()]
            file_infos = []
            for f in files:
                if match := rx_level2_product.match(f.name):
                    date = match.group('date')
                    sensor = match.group('sensor')
                    product = match.group('product')
                    extension = match.group('ext')
                    p = Path(f)
                    stat = p.stat()
                    m_time = datetime.datetime.fromtimestamp(stat.st_mtime)

                    if min_date and m_time < min_date:
                        continue

                    info = {
                        'tile': tile
                        , 'date': datetime.date.fromisoformat(date)
                        , 'sensor': sensor
                        , 'product': product
                        , 'extension': extension
                        , 'path': str(p)
                        , 'm_time': m_time
                        , 'st_size': stat.st_size
                    }
                    file_infos.append(info)

        pass

    def _update_ard_log(
        self,
        m_time_min: Optional[datetime.datetime] = None,
        m_time_max: Optional[datetime.datetime] = None,
    ):

        patterns = ["*.log", "*.fail"]
        files = list(
            self.get_log_files(self.config.DIR_ARD_LOG, patterns=patterns)
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
            print(f"No log files found for pattern '{patterns}' "
                  f"created between {m_time_min} and {m_time_max}")
            return

        df_staging = pd.DataFrame(payload)
        self.con.register("df_param", df_staging)
        # 3. Bulk insert using ON CONFLICT in a single query
        self.con.execute(
            f"""
             INSERT INTO {self.TABLE_ARD_LOG}
              (name, sceneid, failed, m_time, path)
              SELECT name, sceneid, failed, m_time, path
              FROM df_param
            """
        )
        self.con.unregister("df_param")

    def update_db(
        self,
        min_time: Union[str, datetime.datetime, None] = None,
        max_time: Union[str, datetime.datetime, None] = None,
        tiles: bool = False,
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
        if tiles:
            self._update_ard_tiles()

    def logfile_content(
        self,
        scene_id: str
    ) -> Generator[Dict[str, Any], Any, None]:
        """
        Returns the content of the log file for a given sceneid or file path
        """

        query = (f"SELECT * FROM {self.TABLE_ARD_LOG} "
                 f"WHERE sceneid = '{scene_id}' "
                 f"OR path = '{scene_id}' OR name = '{scene_id}'")

        cursor = self.con.execute(query)
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            data = dict(zip(columns, row))
            if 'content' not in data:
                with open(data['path'], 'r') as f:
                    data['content'] = f.read()
            yield data

    @staticmethod
    def loadDB(path, read_only: bool = False, replace: Optional[Dict[str, str]] = None):
        path = Path(path)
        if path.is_dir():
            monitor = FORCEMonitor()
            con = monitor.con
            con.execute(f"IMPORT DATABASE '{path}';")
            print(con.execute("SHOW TABLES;").fetchall())
            monitor.load_config_from_db()
        else:
            con = duckdb.connect(path, read_only=True)
            monitor = FORCEMonitor(connection=con, replace=replace)
        return monitor

    def saveDB(self, path):
        path = Path(path)
        if path.is_dir():
            self.con.execute(f"EXPORT DATABASE '{path}';")
        else:
            query = f"""
            ATTACH '{path}' AS file_db;
            COPY FROM DATABASE memory TO file_db;
            DETACH file_db;
            """
            self.con.execute(query)

    def closeDB(self):
        self.con.close()
