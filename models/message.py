from tortoise import fields

from zhenxun.services.db_context import Model


class ChatMessage(Model):
    id = fields.BigIntField(pk=True, auto_increment=True)
    session = fields.ForeignKeyField(
        "models.ChatSession",
        related_name="messages",
        on_delete=fields.CASCADE,
    )
    role = fields.CharField(max_length=16)
    content = fields.TextField()
    user_id = fields.BigIntField(null=True)
    user_name = fields.CharField(max_length=128, null=True)
    user_role = fields.CharField(max_length=16, null=True)
    user_title = fields.CharField(max_length=128, null=True)
    group_id = fields.BigIntField(null=True)
    group_name = fields.CharField(max_length=128, null=True)
    timestamp = fields.BigIntField()
    message_id = fields.BigIntField(null=True)

    class Meta:
        table = "leekchat_messages"
        table_description = "leekchat 消息记录"
        indexes = [
            ("session", "timestamp"),
            ("user_id", "timestamp"),
            ("session", "content"),
        ]