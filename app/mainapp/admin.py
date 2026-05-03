from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(Client)
admin.site.register(ServiceRequest)
admin.site.register(RequestHistory)
admin.site.register(Task)
admin.site.register(Document)
admin.site.register(Invoice)