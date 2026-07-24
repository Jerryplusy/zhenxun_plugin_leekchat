from tortoise import fields

from zhenxun.services.db_context import Model


class ChatSession(Model):
    id = fields.CharField(pk=True, max_length=128)
    type = fields.CharField(max_length=16)
    target_id = fields.BigIntField()
    created_at = fields.BigIntField()
    updated_at = fields.BigIntField()
    compressed_context = fields.TextField(null=True)

    class Meta:
        table = "leekchat_sessions"
        table_description = "leekchat 会话元数据"
        indexes = [("updated_at",)]