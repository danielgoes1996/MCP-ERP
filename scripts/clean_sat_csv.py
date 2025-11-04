#!/usr/bin/env python3
"""Clean the SAT catalog CSV so it only keeps the official three columns."""

from __future__ import annotations

import csv
from pathlib import Path


OUTPUT_HEADERS = ["Nivel", "Código Agrupador", "Nombre de la cuenta y/o subcuenta"]


def main() -> None:
    src = Path("data/sat_catalog/codigo_agrupadorVF.csv")
    dst = Path("data/sat_catalog/codigo_agrupadorVF_clean.csv")

    if not src.exists():
        raise SystemExit(f"Archivo fuente no encontrado: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    with src.open("r", encoding="utf-8") as infile, dst.open("w", encoding="utf-8", newline="") as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        buffer = []
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            buffer.append(row[:3])

        if not buffer:
            raise SystemExit("El archivo no contiene filas válidas.")

        writer.writerow(OUTPUT_HEADERS)
        writer.writerows(buffer)

    print(f"✅ CSV limpio guardado en: {dst}")
    print("Primeras filas:")
    for preview_row in buffer[:5]:
        print(preview_row)


if __name__ == "__main__":
    main()
