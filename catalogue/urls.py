from django.urls import path
from .views import (
    CatalogueListView, CatalogueDetailView,
    FabricsListView, FabricsDetailView,
)

urlpatterns = [
    # WL Prototypes
    path("wl/",           CatalogueListView.as_view(),  name="catalogue-wl-list"),
    path("wl/<uuid:id>/", CatalogueDetailView.as_view(), name="catalogue-wl-detail"),

    # Fabrics
    path("fabrics/",           FabricsListView.as_view(),  name="fabrics-list"),
    path("fabrics/<uuid:id>/", FabricsDetailView.as_view(), name="fabrics-detail"),
]