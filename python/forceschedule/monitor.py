import argparse
import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import chain
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import duckdb
import pandas as pd
from _duckdb import DuckDBPyConnection
from osgeo import gdal
from tqdm import tqdm

from forceschedule.utils import (
    DATE,
    DATETIME,
    FORCEConfig,
    find_tile_folders,
    rx_level2_product,
    to_date,
    to_datetime,
    to_tile_ids,
)

__version__ = "0.1"

DATETIME_RANGE = Tuple[Optional[DATETIME], Optional[DATETIME]]
DATE_RANGE = Tuple[Optional[DATE], Optional[DATE]]


class FORCEMonitor(object):
    TABLE_CONFIG = "config"

    TABLE_ARD_LOG = "ard_log"  # collects ARD log files
    TABLE_ARD_TILES = "ard_tiles"

    C_DIR_ARD_LOG = "DIR_ARD_LOG"
    C_DIR_ARD_CUBE = "DIR_ARD_CUBE"

    def __init__(
        self,
        replace: Optional[Dict[str, str]] = None,
        database: Union[Path, str] = ":memory:",
    ):
        if replace is None:
            replace = dict()

        self.replace = replace

        self.con = duckdb.connect(database=database)

        if database == ":memory:":
            self.initDB()

        # if database != ":memory:":
        #     path = Path(database)
        #     if path.is_dir():
        #         self.con.execute(f"IMPORT DATABASE '{database}';")
        #     elif path.is_file():
        #         query = f"""
        #         ATTACH '{database}' AS file_db;
        #         COPY FROM DATABASE file_db TO memory;
        #         DETACH file_db;
        #                 """
        #         self.con.execute(query)
        #     else:
        #         raise NotImplementedError()
        # else:
        #     self.initDB()

    def update_config(self, path):

        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            data = [line.strip() for line in f.read().split("\n")]
            data = [line.strip().split("=") for line in data if len(line) > 0]
            data = {kv[0].strip(): kv[1].strip() for kv in data}

        c: DuckDBPyConnection = self.con

        payload = []
        for k, v in data.items():
            payload.append({"key": k, "value": v})

        df_staging = pd.DataFrame(payload)
        self.con.register("df_config", df_staging)
        # 3. Bulk insert using ON CONFLICT in a single query
        self.con.execute(
            f"""
             MERGE INTO {self.TABLE_CONFIG}
             USING df_config
             ON ({self.TABLE_CONFIG}.key = df_config.key)  
             WHEN MATCHED THEN UPDATE SET value = df_config.value 
             WHEN NOT MATCHED THEN INSERT (key, value) VALUES (df_config.key, df_config.value);
            """
        )
        self.con.unregister("df_config")

    def initDB(self):
        """
        Create a DuckDB database to contain the datacube metadata
        """
        c = self.con
        c.execute("INSTALL spatial;")
        c.execute("LOAD spatial;")

        # table for datacube configuration
        c.execute(
            f"CREATE TABLE {self.TABLE_CONFIG} ("
            f"key VARCHAR PRIMARY KEY,"
            f"value VARCHAR,"
            f");"
        )

        # table for ARD log file information
        c.execute(
            f"CREATE TABLE {self.TABLE_ARD_LOG} ("
            # "name VARCHAR PRIMARY KEY,"
            "sceneid VARCHAR PRIMARY KEY,"
            "failed BOOLEAN,"
            "m_time TIMESTAMP,"
            "path VARCHAR UNIQUE,"
            ");"
        )

        # table for ARD tile file information. Potentially very large
        c.execute(
            f"CREATE TABLE {self.TABLE_ARD_TILES} ("
            "tile VARCHAR,"
            "date DATE,"
            "sensor VARCHAR,"
            "product VARCHAR,"
            "name VARCHAR,"
            "size BIGINT,"
            "c_time TIMESTAMP,"
            "m_time TIMESTAMP,"
            "force VARCHAR, "
            "path VARCHAR UNIQUE,"
            "PRIMARY KEY (tile, date, sensor, product),"
            ");"
        )

    def configValue(self, key: str, replace_prefix: bool = True) -> str:
        """
        Returns the config value for a key.
        Prefix replacements are applied
        """
        c = self.con.cursor()

        result = c.execute(
            f"SELECT value FROM {self.TABLE_CONFIG} WHERE key = ?", (key,)
        ).fetchone()

        value = None
        if result:
            value = str(result[0])
            if replace_prefix:
                for k, v in self.replace.items():
                    if value.startswith(k):
                        value = value.replace(k, v)
                        break
        if value is None:
            value = ""
        return value

    def load_config_from_db(self):

        config = FORCEConfig()

        for k, v in self.con.execute(f"SELECT * FROM {self.TABLE_CONFIG};").fetchall():
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

        query = "SELECT COUNT(*) FROM ard_log WHERE failed = TRUE"
        n_failed = self.con.execute(query).fetchone()[0]
        query = "SELECT COUNT(*) FROM ard_log WHERE failed = FALSE"
        n_success = self.con.execute(query).fetchone()[0]

        query = "SELECT MIN(m_time), MAX(m_time) FROM ard_log"
        min_date, max_date = self.con.execute(query).fetchone()

        info = [
            f"ARD log status: {self.configValue(self.C_DIR_ARD_LOG)}",
            f"Total:   {n_success + n_failed}",
            f"Success: {n_success}",
            f"Failed:  {n_failed}",
            f"Files created between: {min_date} and {max_date}",
        ]

        n_tile_ids = f"SELECT COUNT(tile) FROM {self.TABLE_ARD_TILES};"
        dates_per_sensor = ""

        query = f"""
                SELECT 
                  COUNT(DISTINCT "tile") as tiles,
                  COUNT(*) as count,
                  MIN("date") as obs_min, MAX("date") as obs_max,
                  "sensor",
                  "product",
                  SUM("size") / 1024^3 as size_gb,
                  MIN(DATE("c_time")) as c_min ,MAX(DATE("c_time")) as c_max
                  FROM {self.TABLE_ARD_TILES}
                  WHERE "product" = 'BOA' 
                  GROUP BY "product", "sensor"
                """
        info += [f"\nARD Cube: {self.configValue(self.C_DIR_ARD_CUBE)}"]
        results: pd.DataFrame = self.con.execute(query).df()
        n = len(results)
        if n == 0:
            info += [f"No entries in {self.TABLE_ARD_TILES}"]

        else:
            with pd.option_context(
                "display.max_rows",
                None,
                "display.max_columns",
                None,
                "display.width",
                None,
            ):
                info += ["\n" + str(results)]
        return "\n".join(info)

    @staticmethod
    def _scan_ard_tile(
        tiles: List[Path],
        obs_date: DATE_RANGE = (None, None),
        mod_time: DATETIME_RANGE = (None, None),
    ) -> pd.DataFrame:
        """
        Scan a single ARD tile folder and return the metadata of its files.

        This performs only filesystem I/O and no database access, so it is
        safe to run in a worker thread.
        """

        obs_date_min, obs_date_max = to_date(obs_date[0]), to_date(obs_date[1])
        mod_date_min, mod_date_max = to_datetime(mod_time[0]), to_datetime(mod_time[1])

        payload = []

        for tile in tiles:
            tile_id = tile.name
            for f in [e for e in os.scandir(tile) if e.is_file()]:
                if match := rx_level2_product.match(f.name):
                    obs_date_ = datetime.datetime.fromisoformat(match.group("date"))

                    if obs_date_min and obs_date_min > obs_date_:
                        continue
                    if obs_date_max and obs_date_max < obs_date_:
                        continue

                    sensor = match.group("sensor")
                    product = match.group("product")
                    extension = match.group("ext")

                    ds = gdal.Open(f.path)
                    MD = ds.GetMetadata_Dict("FORCE")
                    force_version = MD["FORCE_version"]
                    del ds
                    # p = Path(f)
                    stat = f.stat()
                    c_time = datetime.datetime.fromtimestamp(stat.st_ctime)
                    m_time = datetime.datetime.fromtimestamp(stat.st_mtime)

                    if mod_date_min and m_time < mod_date_min:
                        continue
                    if mod_date_max and m_time > mod_date_max:
                        continue

                    info = {
                        "tile": tile_id,
                        "date": obs_date_,
                        "sensor": sensor,
                        "product": product,
                        "name": f.name,
                        "size": stat.st_size,
                        "c_time": c_time,
                        "m_time": m_time,
                        "force": force_version,
                        "path": str(f.path),
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

        # tiles_batches = [
        #     tiles[i : i + batch_size] for i in range(0, len(tiles), batch_size)
        # ]

        tiles_batches = [
            [
                t,
            ]
            for t in tiles
        ]

        def insert_payload(df_staging: pd.DataFrame):
            if len(df_staging) == 0:
                return

            df_name = "df_tiles_staging"
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
                f"DELETE FROM {self.TABLE_ARD_TILES} "
                "WHERE (tile, date, sensor, product) IN "
                f"(SELECT tile, date, sensor, product FROM {df_name});"
                " "
                f"INSERT INTO {self.TABLE_ARD_TILES} ("
                "tile, date, sensor, product, name,"
                "size, c_time, m_time, force, path"
                f") FROM {df_name}"
            )
            self.con.unregister(df_name)

        with ThreadPoolExecutor(max_workers=max(1, n_workers)) as executor:
            futures = {
                executor.submit(self._scan_ard_tile, batch, obs_date, mod_date): batch
                for batch in tiles_batches
            }
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Updating ARD tiles",
            ):
                insert_payload(future.result())

    def _update_ard_log(
        self,
        mod_time: DATETIME_RANGE = (None, None),
    ):

        patterns = ["*.log", "*.fail"]

        dir_logfile = str(self.configValue(self.C_DIR_ARD_LOG))

        files = list(self.get_log_files(dir_logfile, patterns=patterns))

        m_time_min, m_time_max = to_datetime(mod_time[0]), to_datetime(mod_time[1])

        REPLACE = {v: k for k, v in self.replace.items()}

        payload = []

        for f in tqdm(files, desc=f'Updating ARD log ("{patterns}")'):
            f: Path
            stat = f.stat()
            m_time = datetime.datetime.fromtimestamp(stat.st_mtime)

            if m_time_min and m_time_min > m_time:
                continue
            if m_time_max and m_time_max < m_time:
                continue

            p = str(f)
            for k, v in REPLACE.items():
                if p.startswith(k):
                    p = p.replace(k, v)
                    break

            payload.append(
                {
                    # "name": f.name,
                    "sceneid": f.name.split(".")[0],
                    "failed": f.name.endswith(".fail"),
                    "m_time": m_time,
                    "path": p,
                }
            )
        if len(payload) == 0:
            print(
                f"No log files found for pattern '{patterns}' "
                f"created between {m_time_min} and {m_time_max}"
            )
            return

        df_staging = pd.DataFrame(payload)
        self.con.register("df_param", df_staging)
        # 3. Bulk insert using ON CONFLICT in a single query
        self.con.execute(
            f"""
              INSERT INTO {self.TABLE_ARD_LOG}
              (sceneid, failed, m_time, path)
              SELECT sceneid, failed, m_time, path
              FROM df_param
              ON CONFLICT (path)
              DO UPDATE SET (sceneid, failed, m_time, path) = (EXCLUDED.sceneid, EXCLUDED.failed, EXCLUDED.m_time, EXCLUDED.path)
            """
        )
        self.con.unregister("df_param")

    def update_db(
        self,
        mod_time: DATETIME_RANGE = (None, None),
        update_ard_log: bool = True,
        update_ard_tiles: bool = False,
        n_workers: int = 10,
        tile_ids=None,
    ):
        """
        Updates the database with log files
        """
        query = f"SELECT MIN(m_time), MAX(m_time) FROM {self.TABLE_ARD_LOG}"

        min_time, max_time = mod_time

        m_time_min, m_time_max = self.con.execute(query).fetchone()

        # by default, update only files created after the last update
        if min_time is None:
            min_time = m_time_min

        # write *.log and *.fail files into the same table ard_log
        if update_ard_log:
            self._update_ard_log(mod_time=mod_time)

        # update the ARD tile table
        if update_ard_tiles:
            self._update_ard_tiles(
                mod_time=mod_time, n_workers=n_workers, tile_ids=tile_ids
            )

    def logfile_content(self, scene_id: str) -> Generator[Dict[str, Any], Any, None]:
        """
        Returns the content of the log file for a given sceneid or file path
        """

        query = (
            f"SELECT * FROM {self.TABLE_ARD_LOG} "
            f"WHERE sceneid = '{scene_id}' "
            f"OR path = '{scene_id}' OR name = '{scene_id}'"
        )

        cursor = self.con.execute(query)
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            data = dict(zip(columns, row))
            if "content" not in data:
                with open(data["path"], "r") as f:
                    data["content"] = f.read()
            yield data

    @staticmethod
    def loadDB(
        uri: str,
        replace: Optional[Dict[str, str]] = None,
    ):

        monitor = FORCEMonitor(replace=replace, database=uri)
        # path = Path(uri)
        # if path.is_dir():
        #     monitor = FORCEMonitor(replace=replace, da)
        #     con = monitor.con
        #     con.execute(f"IMPORT DATABASE '{path}';")
        #     print(con.execute("SHOW TABLES;").fetchall())
        #     monitor.load_config_from_db()
        # else:
        #     con = duckdb.connect(path, read_only=read_only)
        #     monitor = FORCEMonitor(connection=con, replace=replace)
        #     monitor.load_config_from_db()
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


def update_db(
    config: Union[Path, FORCEConfig],
    replace: Optional[dict] = None,
    tile_ids: Optional[List[str]] = None,
    n_workers: int = 10,
):
    monitor = FORCEMonitor(
        config=config,
        replace=replace,
    )
    print(monitor.status())
    path_db = config.DB_MONITOR
    monitor.update_db(update_ard_tiles=True, tile_ids=tile_ids, n_workers=n_workers)

    print(f"Write database to {path_db}")
    monitor.saveDB(path_db)
    print(f"Update done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create or update a DuckDB database to monitor a FORCE datacube"
    )
    parser.add_argument(
        "config",
        type=str,
        help="Path to FORCE schedule config file",
    )

    parser.add_argument("--db", type=str, help="DB location (path / uri)")

    parser.add_argument("--tile_ids", type=str, help="tile ids to focus on.")
    parser.add_argument(
        "-n",
        "--n_workers",
        type=int,
        default=10,
        help="Number of workers to parallel file reading.",
    )
    parser.add_argument(
        "--replace",
        type=str,
        help="A JSON dictionary with replacement string for file path prefixes in the config.txt"
        ', e.g \'{"old/prefix":"new/prefix"}\'',
    )

    args = parser.parse_args()

    if args.tile_ids:
        tile_ids = to_tile_ids(args.tile_ids)
    else:
        tile_ids = None

    if isinstance(args.replace, str):
        replace = json.loads(args.replace)
        if not isinstance(replace, dict):
            raise ValueError(f"Unable to retrieve dictionary from {args.replace}")
    else:
        replace = None

    config = FORCEConfig(args.config, replace=replace)

    if args.db:
        config.DB_MONITOR = args.db

    s = ""

    update_db(config, replace=replace, tile_ids=tile_ids)
