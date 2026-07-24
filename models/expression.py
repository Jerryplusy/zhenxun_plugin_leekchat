from tortoise import fields

from zhenxun.services.db_context import Model
from zhenxun.services.log import logger


class ExpressionRecord(Model):
    id = fields.BigIntField(pk=True, auto_increment=True)
    session_id = fields.CharField(max_length=128)
    user_id = fields.BigIntField()
    user_name = fields.CharField(max_length=128)
    situation = fields.TextField()
    style = fields.TextField()
    example = fields.TextField()
    created_at = fields.BigIntField()

    class Meta:
        table = "leekchat_expressions"
        table_description = "leekchat 表达习惯记录 (TODO: 未实现)"
        indexes = [
            ("session_id", "created_at"),
            ("user_id", "created_at"),
        ]

    async def save(self, *args, **kwargs):
        logger.warning("TODO: ExpressionRecord.save 未实现")
        raise NotImplementedError("Expression persistence is TODO in leekchat")