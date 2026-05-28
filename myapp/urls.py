from django.urls import path
from . import views

urlpatterns = [
    path('', views.index,name='index'),
    path('upload/', views.upload_pdf,name='upload'),
    path('chat/<int:pdf_id>/',views.chat_view,name='chat'),
    path('delete/<int:pdf_id>/',views.delete_view,name='delete'),
]