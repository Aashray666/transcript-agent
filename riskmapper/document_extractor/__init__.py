"""Document Risk Extractor — extracts risks from any document type.

Supports: audit reports, con-call transcripts, annual reports,
board presentations, management letters, regulatory filings.

Usage:
    from riskmapper.document_extractor import extract_risks_from_document

    result = extract_risks_from_document(
        file_path="path/to/audit_report.pdf",
        document_type="audit_report",
        sector="Automotive",
        llm=LLMWrapper(),
    )
"""

from riskmapper.document_extractor.extractor import extract_risks_from_document

__all__ = ["extract_risks_from_document"]
