from django.contrib import admin
from .models import Event, TicketTier, SavedEvent

admin.site.register(Event)
admin.site.register(TicketTier)
admin.site.register(SavedEvent)