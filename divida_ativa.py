import fnmatch
import warnings
import zipfile
from functools import cached_property
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from lxml.html import document_fromstring
from rows.plugins.postgresql import PostgresCopy, pg_execute_psql
from rows.utils import NotNullWrapper, ProgressBar, load_schema, subclasses
from rows.utils.download import Download, Downloader

SCHEMA_PATH = Path(__file__).parent / "schema"


# Taken from `import_rfb.py` @ github.com/turicas/socios-brasil
class TableConfig:
    """Base class to handle table configurations during import"""

    filename_patterns: str  # Glob pattern for ZIP filename
    schema_filename: str  # Schema filename to use when importing
    has_header: bool  # Does the CSV file's first line is the header?
    name: str  # Table name to be imported
    inner_filename_pattern: str = None  # Glob pattern for filename inside ZIP
    # archive (if not specified, all files in archive are used)
    encoding: str = "iso-8859-15"  # Encoding for CSV
    dialect: str = "excel-semicolon"  # Dialect for CSV

    @classmethod
    def subclasses(cls):
        return {class_.name: class_ for class_ in subclasses(cls)}

    @cached_property
    def schema(self):
        return load_schema(str(SCHEMA_PATH / self.schema_filename))

    def filenames(self, zip_path):
        """List of zip files which matches this table's ZIP archive pattern"""
        zip_path = Path(zip_path)
        all_filenames = []
        for filename_pattern in self.filename_patterns:
            all_filenames.extend(zip_path.glob(filename_pattern))
        return sorted(set(all_filenames))

    def load(self, zip_path, database_url, unlogged=False, access_method=None, drop=False):
        """Load data into PostgreSQL database"""

        desc_import = f"Importing {self.name} (calculating size)"
        desc_drop = f"Dropping {self.name}"

        progress_bar = ProgressBar(pre_prefix=desc_drop if drop else desc_import, prefix="", unit="bytes")

        if drop:
            pg_execute_psql(database_url, f'DROP TABLE IF EXISTS "{self.name}"')
            progress_bar.prefix = progress_bar.description = desc_import

        # First, select all zip files and inner files to load
        filenames = self.filenames(zip_path)
        uncompressed_size, files_to_extract = 0, []
        for zip_filename in filenames:
            zf = zipfile.ZipFile(zip_filename)
            files_infos = [file_info for file_info in zf.filelist]
            if self.inner_filename_pattern:
                files_infos = [
                    file_info
                    for file_info in files_infos
                    if fnmatch.fnmatch(file_info.filename, self.inner_filename_pattern)
                ]
            if not files_infos:
                warnings.warn(f"Cannot match inner files in {zip_filename}", RuntimeWarning)
            files_to_extract.append((zf, files_infos))
            uncompressed_size += sum(file_info.file_size for file_info in files_infos)

        pgcopy = PostgresCopy(database_url)
        progress_bar.prefix = progress_bar.description = f"Importing {self.name} (ZIP 0/{len(files_to_extract)})"
        progress_bar.total = uncompressed_size
        rows_imported = 0
        for counter, (zf, files_infos) in enumerate(files_to_extract, start=1):
            progress_bar.prefix = progress_bar.description = f"Importing {self.name} (ZIP {counter}/{len(files_to_extract)})"
            for file_info in files_infos:
                # TODO: check if table already exists/has rows before importing?
                fobj = zf.open(file_info.filename)
                result = pgcopy.import_from_fobj(
                    fobj=NotNullWrapper(fobj),
                    table_name=self.name,
                    encoding=self.encoding,
                    dialect=self.dialect,
                    schema=self.schema,
                    has_header=self.has_header,
                    unlogged=unlogged,
                    access_method=access_method,
                    callback=progress_bar.update,
                )
                rows_imported += result["rows_imported"]
        progress_bar.description = f"[{self.name}] {rows_imported} rows imported"
        progress_bar.close()


class DividaAtivaFGTS(TableConfig):
    filename_patterns = ("Dados_abertos_FGTS.zip", )
    inner_filename_pattern = "*.csv"
    has_header = True
    name = "divida_ativa_fgts_orig"
    schema_filename = "divida_ativa_fgts.csv"


class DividaAtivaPrevidenciario(TableConfig):
    filename_patterns = ("Dados_abertos_Previdenciario.zip", )
    inner_filename_pattern = "*.csv"
    has_header = True
    name = "divida_ativa_previdenciario_orig"
    schema_filename = "divida_ativa_previdenciario.csv"


class DividaAtivaNaoPrevidenciario(TableConfig):
    filename_patterns = ("Dados_abertos_Nao_Previdenciario.zip", )
    inner_filename_pattern = "*.csv"
    has_header = True
    name = "divida_ativa_nao_previdenciario_orig"
    schema_filename = "divida_ativa_nao_previdenciario.csv"


def link_list(url):
    response = requests.get(url)
    tree = document_fromstring(response.text)
    trimestres = []
    for link in tree.xpath("//li/a"):
        link_url = urljoin(url, link.xpath("./@href")[0])
        link_title = link.xpath(".//text()")[0].strip()
        if link_title == "Parent Directory":
            continue
        yield (link_title, link_url)

if __name__ == "__main__":
    import argparse
    import os
    import sys


    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["download", "import"])
    args = parser.parse_args()
    command = args.command

    download_path = Path(__file__).parent / "data" / "download"
    if command == "download":
        url = "http://dadosabertos.pgfn.gov.br/"
        # TODO: adicionar opção para baixar de outros trimestres
        trimestres = sorted(link_list(url))
        ultimo_tri = trimestres[-1]
        print(f"Baixando dados de: {ultimo_tri[0]}")
        if not download_path.exists():
            download_path.mkdir(parents=True)
        downloader = Downloader.subclasses()["aria2c"](path=download_path)
        for link_title, link_url in link_list(ultimo_tri[1]):
            filename = Path(urlparse(link_url).path).name
            downloader.add(Download(url=link_url, filename=filename))
        downloader.run()

    elif command == "import":
        database_url = os.environ["DATABASE_URL"]
        unlogged = False
        drop_if_exists = True
        access_method = "heap"
        for Table in (DividaAtivaFGTS, DividaAtivaPrevidenciario, DividaAtivaNaoPrevidenciario):
            table = Table()
            table.load(
                download_path,
                database_url,
                unlogged=unlogged,
                access_method=access_method,
                drop=drop_if_exists,
            )
