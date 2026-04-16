"""Risk registry loader — reads an XLSX workbook and stores entries in ChromaDB.

Reads the specified sector sheet, embeds each risk entry as
"{Primary Impact} - {Risk Name}", and stores them in the "risk_registry"
ChromaDB collection with metadata.
"""

from __future__ import annotations

import logging
import os

import openpyxl

logger = logging.getLogger(__name__)


def load_registry(
    xlsx_path: str,
    sector: str,
    chroma_client,
    embedding_fn=None,
) -> int:
    """Load risk entries from the sector sheet into ChromaDB.

    Args:
        xlsx_path: Path to the risk registry XLSX workbook.
        sector: Sheet name matching the client sector.
        chroma_client: A chromadb.ClientAPI instance.
        embedding_fn: Optional ChromaDB embedding function. If None,
            ChromaDB's default (Sentence Transformers) is used.

    Returns:
        Number of entries loaded.

    Raises:
        FileNotFoundError: If xlsx_path does not exist.
        ValueError: If the sector sheet is not found or is empty.
    """
    if not os.path.isfile(xlsx_path):
        raise FileNotFoundError(
            f"Risk registry file not found: {xlsx_path}"
        )

    wb = openpyxl.load_workbook(xlsx_path, read_only=True)

    if sector not in wb.sheetnames:
        wb.close()
        raise ValueError(
            f"Sector sheet '{sector}' not found in {xlsx_path}. "
            f"Available sheets: {wb.sheetnames}"
        )

    ws = wb[sector]
    rows = list(ws.iter_rows(min_row=2, values_only=True))  # skip header
    wb.close()

    # Filter out completely empty rows
    rows = [r for r in rows if r and r[0] is not None]

    if len(rows) == 0:
        raise ValueError(
            f"Sector sheet '{sector}' in {xlsx_path} contains zero risk entries."
        )

    # Build sector prefix for IDs (first 3 chars uppercase)
    sector_prefix = sector[:3].upper()

    # Idempotency: delete collection if it exists, then recreate
    try:
        chroma_client.delete_collection("risk_registry")
    except Exception:
        pass  # Collection doesn't exist yet — that's fine

    collection_kwargs = {"name": "risk_registry"}
    if embedding_fn is not None:
        collection_kwargs["embedding_function"] = embedding_fn
    collection = chroma_client.create_collection(**collection_kwargs)

    ids = []
    documents = []
    metadatas = []

    for idx, row in enumerate(rows, start=1):
        risk_name = str(row[0]).strip()
        primary_impact = str(row[1]).strip() if row[1] else ""
        registry_risk_id = f"REG_{sector_prefix}_{idx:03d}"

        doc_text = f"{primary_impact} - {risk_name}"

        ids.append(registry_risk_id)
        documents.append(doc_text)
        metadatas.append({
            "registry_risk_id": registry_risk_id,
            "risk_name": risk_name,
            "primary_impact": primary_impact,
        })

    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    logger.info(
        "Registry loaded | sector=%s | entries=%d | collection=risk_registry",
        sector, len(ids),
    )

    return len(ids)
