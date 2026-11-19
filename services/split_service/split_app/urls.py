from django.urls import path

from . import views

app_name = "split_app"

urlpatterns = [
    path("bills/<str:bill_id>/", views.bill_entry, name="bill-entry"),
    path("bills/<str:bill_id>/participants/", views.join_session, name="join-session"),
]
