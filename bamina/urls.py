
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
urlpatterns = [
    path("admin/", admin.site.urls),
    path('auth/', include('user.urls')), 
    path('manage/', include('manager.urls')),
    path('api/', include('api.urls')) # User authentication URLs
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
