from db.connection import connect
from pipeline.edits import get_edits_for_item, record_edit


def test_record_edit_writes_row():
    conn = connect(":memory:")
    conn.execute(
        "INSERT INTO items (item_id, status, created_at, updated_at) VALUES (?, 'queued', '2026-01-01', '2026-01-01')",
        ("item-1",),
    )
    conn.commit()

    edit_id = record_edit(conn, "item-1", "brand", "Levi's", "Levis", "manual")

    row = conn.execute("SELECT * FROM edits WHERE edit_id = ?", (edit_id,)).fetchone()
    assert row["item_id"] == "item-1"
    assert row["field_name"] == "brand"
    assert row["model_value"] == "Levi's"
    assert row["edited_value"] == "Levis"
    assert row["origin"] == "manual"
    assert row["edited_at"] is not None


def test_record_edit_allows_null_model_value():
    conn = connect(":memory:")
    conn.execute(
        "INSERT INTO items (item_id, status, created_at, updated_at) VALUES (?, 'queued', '2026-01-01', '2026-01-01')",
        ("item-1",),
    )
    conn.commit()

    edit_id = record_edit(conn, "item-1", "size", None, "M", "manual")
    row = conn.execute("SELECT * FROM edits WHERE edit_id = ?", (edit_id,)).fetchone()
    assert row["model_value"] is None
    assert row["edited_value"] == "M"


def test_get_edits_for_item_returns_only_that_items_edits_in_order():
    conn = connect(":memory:")
    for item_id in ("item-1", "item-2"):
        conn.execute(
            "INSERT INTO items (item_id, status, created_at, updated_at) VALUES (?, 'queued', '2026-01-01', '2026-01-01')",
            (item_id,),
        )
    conn.commit()

    record_edit(conn, "item-1", "brand", "Levi's", "Levis", "manual")
    record_edit(conn, "item-2", "size", "M", "L", "manual")
    record_edit(conn, "item-1", "color", "Blue", "Navy", "manual")

    edits = get_edits_for_item(conn, "item-1")
    assert [e["field_name"] for e in edits] == ["brand", "color"]


def test_get_edits_for_item_empty_when_none():
    conn = connect(":memory:")
    assert get_edits_for_item(conn, "no-such-item") == []
