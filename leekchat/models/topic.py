from tortoise import fields

from zhenxun.services.db_context import Model
from zhenxun.services.log import logger


class TopicRecord(Model):
    id = fields.BigIntField(pk=True, auto_increment=True)
    session_id = fields.CharField(max_length=128)
    title = fields.CharField(max_length=255)
    keywords = fields.TextField(default="[]")
    summary = fields.TextField()
    message_count = fields.BigIntField(default=0)
    window_start_at = fields.BigIntField(null=True)
    window_end_at = fields.BigIntField(null=True)
    created_at = fields.BigIntField()
    updated_at = fields.BigIntField()

    class Meta:
        table = "leekchat_topics"
        table_description = "leekchat 话题记录 (TODO: 未实现)"
        indexes = [
            ("session_id", "updated_at"),
            ("session_id", "window_end_at"),
        ]

    async def save(self, *args, **kwargs):
        logger.warning("TODO: TopicRecord.save 未实现")
        raise NotImplementedError("Topic persistence is TODO in leekchat")