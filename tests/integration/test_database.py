from tms.accounts.models import Account


def test_schema_account_and_wal(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+84123456", str(tmp_path / "a.session"))
    )
    assert account_id > 0
    assert store.accounts.list_all()[0].phone == "+84123456"
    with store.db.reader() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(migration_items)")
        }
        assert "target_state" in columns
