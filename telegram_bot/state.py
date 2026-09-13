from .models import ConversationState


class StateStore:
    @staticmethod
    def get(account):
        state, _ = ConversationState.objects.get_or_create(account=account)
        return state

    @staticmethod
    def set(account, name, **data):
        state = StateStore.get(account)
        state.state = name
        state.data = data
        state.save(update_fields=['state', 'data', 'updated_at'])
        return state

    @staticmethod
    def clear(account):
        state = StateStore.get(account)
        state.clear()
