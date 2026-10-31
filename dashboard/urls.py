from django.urls import path

from .views import AdminDashboardView, CustomerDashboardView, ReportsView, SearchView, StaffDashboardView

urlpatterns = [
    path('dashboard/admin/', AdminDashboardView.as_view(), name='dashboard-admin'),
    path('dashboard/staff/', StaffDashboardView.as_view(), name='dashboard-staff'),
    path('dashboard/customer/', CustomerDashboardView.as_view(), name='dashboard-customer'),
    path('dashboard/reports/', ReportsView.as_view(), name='dashboard-reports'),
    path('search/', SearchView.as_view(), name='search'),
]
