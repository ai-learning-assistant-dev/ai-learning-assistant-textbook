"""
    OneNote 解析实现

    只读保证：本包内只有 parser._write_outputs / page2md.save_document_markdown
    会写磁盘，Note2Anki 的适配层（onenote_api.py）不调用它们，
    因此 OneNote 源文件不会被修改。
"""

from .config import ConfigError, ParserConfig, discover_one_files
from .extractor import ExtractError, extract_file
from .page2md import document_to_markdown, page_to_markdown
from .parser import is_one_file

__all__ = [
    "ConfigError",
    "ExtractError",
    "ParserConfig",
    "discover_one_files",
    "document_to_markdown",
    "extract_file",
    "is_one_file",
    "page_to_markdown",
]
