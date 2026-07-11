import ast
from pathlib import Path


def test_alembic_revision_ids_fit_version_table_column():
    for migration in Path("alembic/versions").glob("*.py"):
        tree = ast.parse(migration.read_text(encoding="utf-8"))
        revision = None
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "revision":
                revision = ast.literal_eval(node.value)
                break
            if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "revision" for target in node.targets):
                revision = ast.literal_eval(node.value)
                break
        assert revision is not None, migration
        assert len(revision) <= 32, f"{migration.name}: {revision}"
