from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("requests/", views.request_list, name="request-list"),
    path("requests/new/", views.request_create, name="request-create"),
    path("requests/<int:pk>/", views.request_detail, name="request-detail"),
    path("requests/<int:pk>/print/", views.request_print, name="request-print"),
    path("requests/<int:pk>/edit/", views.request_edit, name="request-edit"),
    path("requests/<int:pk>/submit/", views.request_submit, name="request-submit"),
    path("requests/<int:pk>/decide/", views.request_decide, name="request-decide"),
    path("requests/<int:pk>/supplier/", views.supplier_select, name="supplier-select"),
    path("requests/<int:pk>/supplier/evaluate/", views.supplier_evaluate, name="supplier-evaluate"),
    path("requests/<int:pk>/po/create/", views.po_create, name="po-create"),
    path("po/<int:pk>/", views.po_detail, name="po-detail"),
    path("po/<int:pk>/print/", views.po_print, name="po-print"),
    path("po/<int:pk>/receive/", views.po_receive, name="po-receive"),
    path("po/<int:pk>/milestone/<int:milestone_pk>/complete/", views.milestone_complete, name="milestone-complete"),
    path("po/<int:pk>/discrepancy/new/", views.discrepancy_create, name="discrepancy-create"),
    path("po/<int:pk>/discrepancy/<int:discrepancy_pk>/resolve/", views.discrepancy_resolve, name="discrepancy-resolve"),
    path("requests/<int:pk>/cancel/", views.cancellation_create, name="cancellation-create"),
    path("cancellations/<int:pk>/decide/", views.cancellation_decide, name="cancellation-decide"),
]
