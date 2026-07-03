from io import BytesIO

from src.services.document_store import DocumentStore


def test_document_store_saves_original_pdf_and_preserves_existing_file(tmp_path):
    store = DocumentStore(upload_dir=tmp_path / "uploads", derived_dir=tmp_path / "derived")
    content = b"%PDF-1.4\n%test\n"

    saved = store.save_upload(BytesIO(content), "report.pdf")
    saved_again = store.save_upload(BytesIO(content), "report.pdf")

    assert saved.file_hash == saved_again.file_hash
    assert saved.stored_path != saved_again.stored_path
    assert saved.path.read_bytes() == content
    assert saved.path.exists()