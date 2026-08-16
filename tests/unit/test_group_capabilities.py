from types import SimpleNamespace

from tms.telegram.telethon_gateway import TelethonGateway


class Channel:
    def __init__(self, *, left=False, username="public", broadcast=False, banned_invite=False):
        self.id = 1
        self.access_hash = 2
        self.title = "group"
        self.username = username
        self.left = left
        self.creator = False
        self.admin_rights = None
        self.broadcast = broadcast
        self.default_banned_rights = SimpleNamespace(invite_users=banned_invite)


def test_public_group_can_be_read_by_link_without_forcing_membership():
    group = TelethonGateway._group_context(Channel(left=True))
    assert group.is_member is False
    assert group.can_read is True
    assert group.can_invite is False


def test_joined_megagroup_member_invite_capability_respects_default_rights():
    allowed = TelethonGateway._group_context(Channel(left=False, banned_invite=False))
    blocked = TelethonGateway._group_context(Channel(left=False, banned_invite=True))
    assert allowed.can_invite is True
    assert blocked.can_invite is False


def test_remove_capability_requires_creator_or_ban_users_admin_right():
    member = Channel(left=False)
    assert TelethonGateway._group_context(member).can_remove is False

    admin = Channel(left=False)
    admin.admin_rights = SimpleNamespace(invite_users=True, ban_users=True)
    assert TelethonGateway._group_context(admin).can_remove is True
