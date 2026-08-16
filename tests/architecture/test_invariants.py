from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "src" / "tms"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_ui_has_no_telegram_rpc_or_sqlite_write_primitives():
    for path in (ROOT / "ui").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "Telethon" not in text
        assert "TelegramClient" not in text
        assert ".gateway." not in text
        assert "INSERT INTO" not in text
        assert "UPDATE " not in text
        assert "DELETE FROM" not in text


def test_migration_hot_path_has_no_file_or_resolve_calls():
    text = _text("migration/executor.py")
    forbidden = ["openpyxl", ".xlsx", ".csv", "resolve_group", "get_entity", "get_input_entity"]
    for token in forbidden:
        assert token not in text


def test_invite_hot_path_uses_cached_input_entities_only():
    text = _text("telegram/telethon_gateway.py")
    start = text.index("    async def invite_user")
    end = text.index("    async def remove_user", start)
    invite_method = text[start:end]
    assert "InputUser" in invite_method
    assert "InputChannel" not in invite_method or "_input_channel" in invite_method
    assert ".get_entity(" not in invite_method
    assert ".get_input_entity(" not in invite_method
    assert "InviteToChannelRequest(target_input, [input_user])" in invite_method


def test_database_connections_are_owned_by_database_and_dbwriter_only():
    offenders = []
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "database.connect()" in text and path.name != "db_writer.py":
            offenders.append(str(path.relative_to(ROOT)))
        if ".db.connect()" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_remove_hot_path_uses_cached_input_entities_only():
    text = _text("telegram/telethon_gateway.py")
    start = text.index("    async def remove_user")
    end = text.index("    async def join_group", start)
    remove_method = text[start:end]
    assert "InputUser" in remove_method
    assert ".get_entity(" not in remove_method
    assert ".get_input_entity(" not in remove_method
    assert "kick_participant(target_input, input_user)" in remove_method
    assert "DeleteChatUserRequest" in remove_method
