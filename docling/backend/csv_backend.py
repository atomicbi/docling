import csv
import logging
from io import BytesIO, StringIO
from pathlib import Path
from typing import Set, Union

from docling_core.types.doc import DoclingDocument, DocumentOrigin, TableCell, TableData

from docling.backend.abstract_backend import DeclarativeDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import InputDocument

_log = logging.getLogger(__name__)


class CsvDocumentBackend(DeclarativeDocumentBackend):
    def __init__(self, in_doc: "InputDocument", path_or_stream: Union[BytesIO, Path]):
        super().__init__(in_doc, path_or_stream)

        # Load content
        try:
            if isinstance(self.path_or_stream, BytesIO):
                self.content = self.path_or_stream.getvalue().decode("utf-8")
            elif isinstance(self.path_or_stream, Path):
                with open(self.path_or_stream, "r", newline="") as f:
                    self.content = f.read()
            self.valid = True
        except Exception as e:
            raise RuntimeError(
                f"CsvDocumentBackend could not load document with hash {self.document_hash}"
            ) from e
        return

    def is_valid(self) -> bool:
        return self.valid

    @classmethod
    def supports_pagination(cls) -> bool:
        return False

    def unload(self):
        if isinstance(self.path_or_stream, BytesIO):
            self.path_or_stream.close()
        self.path_or_stream = None

    @classmethod
    def supported_formats(cls) -> Set[InputFormat]:
        return {InputFormat.CSV}

    def convert(self) -> DoclingDocument:
        """
        Parses the CSV data into a structured document model.
        """

        # Detect CSV dialect
        dialect = csv.Sniffer().sniff(self.content)
        _log.info(f'Parsing CSV with delimiter: "{dialect.delimiter}"')
        if not dialect.delimiter in {",", ";", "\t", "|"}:
            raise RuntimeError(
                f"Cannot convert csv with unknown delimiter {dialect.delimiter}."
            )

        # Parce CSV
        result = csv.reader(StringIO(self.content), dialect=dialect)
        self.csv_data = list(result)
        _log.info(f"Detected {len(self.csv_data)} lines")

        # Parse the CSV into a structured document model
        origin = DocumentOrigin(
            filename=self.file.name or "file.csv",
            mimetype="text/csv",
            binary_hash=self.document_hash,
        )

        doc = DoclingDocument(name=self.file.stem or "file.csv", origin=origin)

        if self.is_valid():
            # Convert CSV data to table
            if self.csv_data:
                num_rows = len(self.csv_data)
                num_cols = max(len(row) for row in self.csv_data)

                table_data = TableData(
                    num_rows=num_rows,
                    num_cols=num_cols,
                    table_cells=[],
                )

                # Convert each cell to TableCell
                for row_idx, row in enumerate(self.csv_data):
                    for col_idx, cell_value in enumerate(row):
                        cell = TableCell(
                            text=str(cell_value),
                            row_span=1,  # CSV doesn't support merged cells
                            col_span=1,
                            start_row_offset_idx=row_idx,
                            end_row_offset_idx=row_idx + 1,
                            start_col_offset_idx=col_idx,
                            end_col_offset_idx=col_idx + 1,
                            col_header=row_idx == 0,  # First row as header
                            row_header=False,
                        )
                        table_data.table_cells.append(cell)

                doc.add_table(data=table_data)
        else:
            raise RuntimeError(
                f"Cannot convert doc with {self.document_hash} because the backend failed to init."
            )

        return doc
