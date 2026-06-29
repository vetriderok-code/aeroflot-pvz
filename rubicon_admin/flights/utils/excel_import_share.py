"""Поиск Excel-файла вылетов на файловой шаре."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_IMPORT_FILENAME = 'ТАБ_ПИСЬМЕННОГО_ДОКЛАДА_ПИЛОТОВ_НОВАЯ2.xlsm'


def default_import_dir() -> Path:
    raw = getattr(settings, 'FLIGHTS_EXCEL_IMPORT_DIR', '') or '/data/Gerasimenko/ГБУ'
    return Path(raw)


def default_import_filename() -> str:
    return (
        getattr(settings, 'FLIGHTS_EXCEL_IMPORT_FILENAME', '')
        or DEFAULT_IMPORT_FILENAME
    )


def _is_ignored_name(name: str) -> bool:
    return name.startswith('~$') or name.startswith('._')


INFO_SHEET_NAME = 'Информация'
INFO_COL_CALLNAME = 12  # L — позывной
INFO_COL_CALC_NUMBER = 13  # M — № расчёта

# Только точное имя листа вылетов (не «сводная_old», «СВОДНАЯ_архив» и т.п.)
SVODNAYA_SHEET_NAMES = frozenset({'svodnaya', 'сводная'})


def find_svodnaya_sheet_name(wb) -> str | None:
    """Лист вылетов: строго «СВОДНАЯ» или «SVODNAYA» (без суффиксов _old и пр.)."""
    for name in wb.sheetnames:
        if name.strip().casefold() in SVODNAYA_SHEET_NAMES:
            return name
    return None


def load_calculation_pilot_mapping(wb) -> dict[int, str]:
    """Сопоставление № расчёта (колонка Q на СВОДНАЯ) → позывной с листа «Информация»."""
    sheet = None
    for name in wb.sheetnames:
        if name.strip().casefold() == INFO_SHEET_NAME.casefold():
            sheet = wb[name]
            break
    if sheet is None:
        logger.warning('Лист «%s» не найден — fallback по № расчёта недоступен', INFO_SHEET_NAME)
        return {}

    mapping: dict[int, str] = {}
    for row_idx in range(1, sheet.max_row + 1):
        callname = sheet.cell(row_idx, INFO_COL_CALLNAME).value
        number = sheet.cell(row_idx, INFO_COL_CALC_NUMBER).value
        if not callname or number is None:
            continue
        callname_str = str(callname).strip()
        if not callname_str:
            continue
        try:
            num = int(float(number))
        except (TypeError, ValueError):
            continue
        mapping[num] = callname_str
    logger.info('Загружено %s позывных по № расчёта с листа «%s»', len(mapping), INFO_SHEET_NAME)
    return mapping


def sheet_last_data_row(ws, *, start_row: int = 5, max_column: int = 22) -> int:
    """Последняя строка листа с данными (не ws.max_row — он часто завышен)."""
    last = start_row - 1
    for row_idx in range(start_row, ws.max_row + 1):
        for col_idx in range(1, max_column + 1):
            value = ws.cell(row_idx, col_idx).value
            if value is not None and str(value).strip():
                last = row_idx
                break
    return last


def resolve_import_file(
    root_dir: Path | str | None = None,
    *,
    filename: str | None = None,
) -> Path:
    """Вернуть путь к файлу импорта на шаре (прямой путь или первый найденный в подкаталогах)."""
    root = Path(root_dir) if root_dir else default_import_dir()
    target_name = (filename or default_import_filename()).strip()
    if not target_name:
        raise ValueError('Имя файла импорта не задано')

    direct = root / target_name
    if direct.is_file():
        logger.info('Файл импорта: %s', direct)
        return direct.resolve()

    if not root.is_dir():
        raise FileNotFoundError(f'Каталог импорта не найден: {root}')

    matches: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for entry in filenames:
            if _is_ignored_name(entry):
                continue
            if entry == target_name:
                matches.append(Path(dirpath) / entry)

    if not matches:
        raise FileNotFoundError(
            f'Файл «{target_name}» не найден в {root}'
        )

    best = max(matches, key=lambda p: p.stat().st_mtime)
    logger.info('Файл импорта (в подкаталоге): %s', best)
    return best.resolve()
