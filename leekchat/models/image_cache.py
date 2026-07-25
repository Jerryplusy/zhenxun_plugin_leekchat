from tortoise import fields

from zhenxun.services.db_context import Model


class ImageCache(Model):
    id = fields.BigIntField(pk=True, auto_increment=True)
    hash = fields.CharField(max_length=64, unique=True)
    url = fields.TextField()
    type = fields.CharField(max_length=16, default="image")
    description = fields.TextField()
    emotion = fields.CharField(max_length=32, null=True)
    character = fields.CharField(max_length=64, null=True)
    file_path = fields.TextField(null=True)
    created_at = fields.BigIntField()

    class Meta:
        table = "leekchat_image_cache"
        table_description = "leekchat 图片缓存（含多模态描述）"
        indexes = [("hash",), ("type",)]