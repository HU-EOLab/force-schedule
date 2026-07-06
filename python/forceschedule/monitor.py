import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import chain
from pathlib import Path
from typing import Union, Optional, Dict, Any, Generator, List, Tuple

import duckdb
import pandas as pd
from tqdm import tqdm

from forceschedule.utils import FORCEConfig, find_tile_folders, rx_level2_product, to_date, to_datetime, DATETIME, DATE

DATETIME_RANGE = Tuple[Optional[DATETIME], Optional[DATETIME]]
DATE_RANGE = Tuple[Optional[DATE], Optional[DATE]]


class FORCEMonitor(object):
    TABLE_ARD_LOG = 'ard_log'  # collects ARD log files
    TABLE_CONFIG = 'config'
    TABLE_ARD_TILE = 'ard_tiles'

    C_DIR_ARD_LOG = 'DIR_ARD_LOG'
    C_DIR_ARD_CUBE = 'DIR_ARD_CUBE'

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

        # table for ARD tile file information. Potentially very large
        c.execute(
            f"CREATE TABLE IF NOT EXISTS {self.TABLE_ARD_TILE} ("
            "tile VARCHAR,"
            "date DATE,"
            "sensor VARCHAR,"
            "product VARCHAR,"
            "name VARCHAR,"
            "size BIGINT,"
            "c_time TIMESTAMP,"
            "m_time TIMESTAMP,"
            "path VARCHAR UNIQUE,"
            "PRIMARY KEY (tile, date, sensor, product),"
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

        n_tile_ids = f"SELECT COUNT(tile) FROM {self.TABLE_ARD_TILE};"
        dates_per_sensor = ''

        query = f"""
                SELECT 
                  COUNT(DISTINCT "tile") as tiles,
                  COUNT(*) as count,
                  MIN("date") as obs_min, MAX("date") as obs_max,
                  "sensor",
                  "product",
                  SUM("size") / 1024^3 as size_gb,
                  MIN(DATE("c_time")) as c_min ,MAX(DATE("c_time")) as c_max
                  FROM {self.TABLE_ARD_TILE}
                  WHERE "product" = 'BOA' 
                  GROUP BY "product", "sensor"
                """
        info += [f'ARD Cube: {self._config_value(self.C_DIR_ARD_CUBE)}']
        results: pd.DataFrame = self.con.execute(query).df()
        s = ""
        with pd.option_context(
            'display.max_rows', None,
            'display.max_columns', None,
            'display.width', None
        ):
            info += ['\n' + str(results)]
        return '\n'.join(info)

    @staticmethod
    def _scan_ard_tile(
        tiles: List[Path],
        obs_date: DATE_RANGE = (None, None),
        mod_date: DATE_RANGE = (None, None),
    ) -> pd.DataFrame:
        """
        Scan a single ARD tile folder and return the metadata of its files.

        This performs only filesystem I/O and no database access, so it is
        safe to run in a worker thread.
        """

        obs_date_min, obs_date_max = to_date(obs_date[0]), to_date(obs_date[1])
        mod_date_min, mod_date_max = to_datetime(mod_date[0]), to_datetime(mod_date[1])

        payload = []

        for tile in tiles:
            tile_id = tile.name
            for f in [e for e in os.scandir(tile) if e.is_file()]:
                if match := rx_level2_product.match(f.name):
                    obs_date_ = datetime.datetime.fromisoformat(match.group('date'))

                    if obs_date_min and obs_date_min > obs_date_:
                        continue
                    if obs_date_max and obs_date_max < obs_date_:
                        continue

                    sensor = match.group('sensor')
                    product = match.group('product')
                    extension = match.group('ext')
                    # p = Path(f)
                    stat = f.stat()
                    c_time = datetime.datetime.fromtimestamp(stat.st_ctime)
                    m_time = datetime.datetime.fromtimestamp(stat.st_mtime)

                    if mod_date_min and m_time < mod_date_min:
                        continue
                    if mod_date_max and m_time > mod_date_max:
                        continue

                    info = {
                        'tile': tile_id
                        , 'date': obs_date_
                        , 'sensor': sensor
                        , 'product': product
                        , 'name': f.name
                        , 'size': stat.st_size
                        , 'c_time': c_time
                        , 'm_time': m_time
                        , 'path': str(f.path)
                    }
                    payload.append(info)
        if len(payload) == 0:
            return pd.DataFrame()
        else:
            return pd.DataFrame(payload)

    def _update_ard_tiles(
        self,
        n_workers: int = 8,
        obs_date: DATE_RANGE = (None, None),
        mod_date: DATE_RANGE = (None, None),
        tile_ids: Optional[List[str]] = None,
        batch_size: int = 10,
    ):
        """
        Loads the metadata of ARD files.

        The tile folders are scanned in parallel using ``n_workers`` threads,
        while the resulting rows are inserted into the database on the calling
        thread (the DuckDB connection is not shared between threads).
        """
        tiles = list(find_tile_folders(self.config.DIR_ARD_CUBE))

        if tile_ids:
            tiles = [t for t in tiles if t.name in tile_ids]

        tiles_batches = [tiles[i: i + batch_size] for i in range(0, len(tiles), batch_size)]

        def insert_payload(df_staging: pd.DataFrame):
            if len(df_staging) == 0:
                return

            df_name = 'df_tiles_staging'
            self.con.register(df_name, df_staging)
            # Bulk upsert: the table has two unique constraints
            # (PRIMARY KEY (tile, date, sensor, product) and UNIQUE path),
            # so ON CONFLICT / INSERT OR REPLACE cannot infer a single target.
            # Delete any rows colliding on either constraint, then insert.
            self.con.execute(
                # f"DELETE FROM {self.TABLE_ARD_TILE} t USING {df_name} s "
                # "WHERE (t.tile = s.tile AND t.date = s.date "
                # "       AND t.sensor = s.sensor AND t.product = s.product) "
                # "   OR t.path = s.path"
                f"DELETE FROM {self.TABLE_ARD_TILE} "
                "WHERE (tile, date, sensor, product) IN "
                f"(SELECT tile, date, sensor, product FROM {df_name});"
                " "
                f"INSERT INTO {self.TABLE_ARD_TILE} ("
                "tile, date, sensor, product, name,"
                "size, c_time, m_time, path"
                f") FROM {df_name}")
            self.con.unregister(df_name)

        with ThreadPoolExecutor(max_workers=max(1, n_workers)) as executor:
            futures = {
                executor.submit(
                    self._scan_ard_tile, batch, obs_date, mod_date
                ): batch
                for batch in tiles_batches
            }
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc='Updating ARD tiles',
            ):
                insert_payload(future.result())

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
    def loadDB(
        path: Union[Path, str],
        read_only: bool = False,
        replace: Optional[Dict[str, str]] = None,
    ):
        path = Path(path)
        if path.is_dir():
            monitor = FORCEMonitor()
            con = monitor.con
            con.execute(f"IMPORT DATABASE '{path}';")
            print(con.execute("SHOW TABLES;").fetchall())
            monitor.load_config_from_db()
        else:
            con = duckdb.connect(path, read_only=read_only)
            monitor = FORCEMonitor(connection=con, replace=replace)
            monitor.load_config_from_db()
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

    def clone(self) -> "FORCEMonitor":
        """
        Create a clone of this monitor backed by a new, independent in-memory
        DuckDB that contains a copy of all tables and data from this monitor's
        connection.
        """
        clone = FORCEMonitor()
        clone.replace = dict(self.replace)

        dst = clone.con
        dst.execute("INSTALL spatial;")
        dst.execute("LOAD spatial;")

        # recreate every table (schema + constraints) and copy its data
        tables = self.con.execute(
            "SELECT table_name, sql FROM duckdb_tables() ORDER BY table_name"
        ).fetchall()

        table_names = set()
        for table_name, create_sql in tables:
            table_names.add(table_name)
            # recreate the table with its original schema and constraints
            dst.execute(create_sql)
            # copy the data via a staging DataFrame
            df = self.con.execute(f'SELECT * FROM "{table_name}"').fetch_df()
            dst.register("df_clone", df)
            dst.execute(f'INSERT INTO "{table_name}" SELECT * FROM df_clone')
            dst.unregister("df_clone")

        # load the config from the cloned data, if available
        if self.TABLE_CONFIG in table_names:
            clone.load_config_from_db()
        else:
            clone.config = self.config

        return clone

    def closeDB(self):
        self.con.close()
