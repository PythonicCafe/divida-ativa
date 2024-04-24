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
            progress_bar.prefix = progress_bar.description = (
                f"Importing {self.name} (ZIP {counter}/{len(files_to_extract)})"
            )
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
    filename_patterns = ("Dados_abertos_FGTS.zip",)
    inner_filename_pattern = "*.csv"
    has_header = True
    name = "divida_ativa_fgts_orig"
    schema_filename = "divida_ativa_fgts.csv"


class DividaAtivaPrevidenciario(TableConfig):
    filename_patterns = ("Dados_abertos_Previdenciario.zip",)
    inner_filename_pattern = "*.csv"
    has_header = True
    name = "divida_ativa_previdenciario_orig"
    schema_filename = "divida_ativa_previdenciario.csv"


class DividaAtivaNaoPrevidenciario(TableConfig):
    filename_patterns = ("Dados_abertos_Nao_Previdenciario.zip",)
    inner_filename_pattern = "*.csv"
    has_header = True
    name = "divida_ativa_nao_previdenciario_orig"
    schema_filename = "divida_ativa_nao_previdenciario.csv"


def link_list(url):
    response = requests.get(url)
    tree = document_fromstring(response.text)
    for link in tree.xpath("//li/a"):
        link_url = urljoin(url, link.xpath("./@href")[0])
        link_title = link.xpath(".//text()")[0].strip()
        if link_title == "Parent Directory":
            continue
        yield (link_title, link_url)


if __name__ == "__main__":
    import argparse
    import os
    import re
    import sys

    REGEXP_TRIMESTRE = re.compile("^20[0-9]{2}-[1-4]$")
    default_download_path = Path(__file__).parent / "data" / "download"
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    parser_download = subparsers.add_parser("download")
    parser_download.add_argument(
        "--trimestre",
        help=(
            "Baixa um trimestre específico (em vez do último), formato: `YYYY-T`, onde `YYYY` é o nome com 4 dígitos "
            "e `T` é o número do trimestre (1, 2, 3 ou 4)"
        ),
    )
    parser_download.add_argument(
        "--base-download-path",
        type=Path,
        default=default_download_path,
        help=(
            "Pasta onde os arquivos serão baixados (uma pasta chamada `YYYY-T` será criada dentro dessa para "
            "armazenar os arquivos desse trimestre)"
        ),
    )

    parser_import = subparsers.add_parser("import")
    parser_import.add_argument(
        "--trimestre",
        help=(
            "Importa um trimestre específico (em vez do último), formato: `YYYY-T`, onde `YYYY` é o nome com 4 "
            "dígitos e `T` é o número do trimestre (1, 2, 3 ou 4)"
        ),
    )
    parser_import.add_argument(
        "--base-download-path",
        type=Path,
        default=default_download_path,
        help=(
            "Pasta onde os arquivos foram baixados (uma pasta chamada `YYYY-T` precisa existir dentro dessa, contendo "
            "os arquivos desse trimestre)"
        ),
    )
    parser_import.add_argument(
        "--database-url", default=os.environ.get("DATABASE_URL"), help="URL de conexão para o banco postgres"
    )
    parser_import.add_argument("--unlogged", action="store_true", help="Cria a tabela no postgres como 'unlogged'")
    parser_import.add_argument("--access-method", default="heap", help="Método de armazenamento da tabela no postgres:")
    parser_import.add_argument("--no-drop", action="store_true", help="Não deleta a tabela antes de inserir os dados")
    args = parser.parse_args()
    command = args.command

    if command == "download":
        trimestre, base_download_path = args.trimestre, args.base_download_path
        if trimestre and not REGEXP_TRIMESTRE.match(trimestre):
            print(f"ERRO - Formato inválido para trimestre: {repr(trimestre)}", file=sys.stderr)
            sys.exit(1)

        url = "http://dadosabertos.pgfn.gov.br/"
        trimestres = {
            item[0].replace("_trimestre_0", "-").replace("/", ""): item[1]
            for item in link_list(url)
            if "trimestre" in item[0]
        }
        if trimestre:
            if trimestre not in trimestres:
                print(
                    f"ERRO - Trimestre não encontrado: {repr(trimestre)} (opções: {', '.join(trimestres.keys())})",
                    file=sys.stderr,
                )
                sys.exit(2)
        else:
            trimestre = sorted(trimestres.keys())[-1]
        download_path = base_download_path / trimestre
        download_path.mkdir(parents=True, exist_ok=True)

        print(f"Baixando dados para o trimestre {trimestre} em {download_path}")
        downloader = Downloader.subclasses()["aria2c"](path=download_path)
        for link_title, link_url in link_list(trimestres[trimestre]):
            filename = Path(urlparse(link_url).path).name
            downloader.add(Download(url=link_url, filename=filename))
        downloader.run()

    elif command == "import":
        trimestre, base_download_path = args.trimestre, args.base_download_path
        if not trimestre:
            trimestres = sorted(
                [
                    item.name
                    for item in base_download_path.glob("*")
                    if REGEXP_TRIMESTRE.match(item.name)
                ]
            )
            if not trimestres:
                print(f"ERRO - Nenhum arquivo baixado foi detectado em {base_download_path}", file=sys.stderr)
                sys.exit(3)
            trimestre = trimestres[-1]
        elif not REGEXP_TRIMESTRE.match(trimestre):
            print(f"ERRO - Formato inválido para trimestre: {repr(trimestre)}", file=sys.stderr)
            sys.exit(1)
        download_path = base_download_path / trimestre
        if not download_path.exists():
            print(f"ERRO - Diretório onde os arquivos deveriam ter sido baixados não existe: {download_path}", file=sys.stderr)
            sys.exit(4)

        for Table in (DividaAtivaFGTS, DividaAtivaPrevidenciario, DividaAtivaNaoPrevidenciario):
            print(f"Importando dados do trimestre {trimestre} na tabela {Table.name}")
            table = Table()
            table.load(
                download_path,
                args.database_url,
                unlogged=args.unlogged,
                access_method=args.access_method,
                drop=not args.no_drop,
            )
