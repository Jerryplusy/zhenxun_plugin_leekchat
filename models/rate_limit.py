from tortoise import fields

from zhenxun.services.db_context import Model


class GroupRateLimit(Model):
    group_id = fields.BigIntField(pk=True)
    requests = fields.JSONField()
    updated_at = fields.BigIntField()

    class Meta:
        table = "leekchat_group_rate_limits"
        table_description = "leekchat 群请求限速（可选持久化）"