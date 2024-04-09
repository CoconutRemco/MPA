from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('Mpapp.urls')),  # Add this line
    path('accounts/', include('django.contrib.auth.urls')),  # Add this line
]
