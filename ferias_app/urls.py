from django.urls import path
from . import views

urlpatterns = [
    path('aviso-ferias/', views.aviso_ferias_endpoint, name='aviso_ferias_endpoint'),
]
