from django.urls import path
from .views import (
    EnquiryCreateView,
    EnquiryListView,
    EnquiryDetailView,
    EnquiryUnreadCountView,
)

urlpatterns = [
    # Public
    path('enquiries/',                         EnquiryCreateView.as_view(),      name='enquiry-create'),

    # Admin / Staff
    path('enquiries/admin/',                   EnquiryListView.as_view(),         name='enquiry-admin-list'),
    path('enquiries/admin/unread-count/',      EnquiryUnreadCountView.as_view(),  name='enquiry-unread-count'),
    path('enquiries/admin/<uuid:id>/',         EnquiryDetailView.as_view(),       name='enquiry-admin-detail'),
]