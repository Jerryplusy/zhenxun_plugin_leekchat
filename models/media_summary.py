from tortoise import fields

from zhenxun.services.db_context import Model


class MediaSummary(Model):
    id = fields.BigIntField(pk=True, auto_increment=True)
    key = fields.CharField(max_length=128, unique=True)
    kind = fields.CharField(max_length=16)
    source = fields.TextField()
    summary = fields.TextField()
    created_at = fields.BigIntField()

    class Meta:
        table = "leekchat_media_summaries"
        table_description = "leekchat 媒体摘要缓存"
        indexes = [("key",), ("kind",)]


class MediaSummarySource(Model):
    source_key = fields.CharField(pk=True, max_length=128)
    summary = fields.ForeignKeyField(
        "leekchat.MediaSummary",
        related_name="sources",
        on_delete=fields.CASCADE,
    )
    created_at = fields.BigIntField()

    class Meta:
        table = "leekchat_media_summary_sources"
        table_description = "leekchat 媒体摘要来源映射"
        indexes = [("summary",)]