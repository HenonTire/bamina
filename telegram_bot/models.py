from django.conf import settings
from django.db import models


class ConversationState(models.Model):
    account = models.OneToOneField(
        'user.TelegramAccount',
        on_delete=models.CASCADE,
        related_name='conversation_state',
    )
    state = models.CharField(max_length=80, blank=True, default='')
    data = models.JSONField(default=dict, blank=True)
    last_update_id = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clear(self):
        self.state = ''
        self.data = {}
        self.save(update_fields=['state', 'data', 'updated_at'])
