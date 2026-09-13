
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health(request):
    return JsonResponse({"status": "ok"})
urlpatterns = [
    path("admin/", admin.site.urls),
    path('auth/', include('user.urls')),
    path('manage/', include('manager.urls')),
    path('api/', include('api.urls')),
    path('telegram/', include('telegram_bot.urls')),
    path('health/', health, name='health'),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
