from django.urls import path
from .views import CatalogueListView, CatalogueDetailView

urlpatterns = [
    path("wl/",           CatalogueListView.as_view(),   name="catalogue-wl-list"),
    path("wl/<uuid:id>/", CatalogueDetailView.as_view(), name="catalogue-wl-detail"),
]