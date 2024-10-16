from django.contrib import admin

from django.contrib.auth.models import User

from . models import *

admin.site.register(UserModels)
admin.site.register(MessageModel)
admin.site.register(TicketsModel)
admin.site.register(TenantModel)
admin.site.register(ConversationModel)
admin.site.register(IssueReported)
admin.site.register(IssueModel)
admin.site.register(TicketsStatusModel)
admin.site.register(FacebookCredentials)
admin.site.register(TemplateModel)


