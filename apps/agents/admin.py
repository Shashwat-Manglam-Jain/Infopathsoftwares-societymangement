from django.contrib import admin

from .models import Agent, AgentCollection, AgentCommission, PigmmyAccount, PigmmyTransaction

admin.site.register(Agent)
admin.site.register(PigmmyAccount)
admin.site.register(PigmmyTransaction)
admin.site.register(AgentCollection)
admin.site.register(AgentCommission)
