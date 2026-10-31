from django.urls import path

from .views import CatalogProductListView, ProductVariantViewSet, ProductViewSet

product_list = ProductViewSet.as_view({'get': 'list', 'post': 'create'})
product_detail = ProductViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}
)
product_archive = ProductViewSet.as_view({'post': 'archive'})
product_unarchive = ProductViewSet.as_view({'post': 'unarchive'})

variant_list = ProductVariantViewSet.as_view({'get': 'list', 'post': 'create'})
variant_detail = ProductVariantViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}
)

urlpatterns = [
    path('catalog/products/', CatalogProductListView.as_view(), name='catalog-products'),
    path('products/', product_list, name='product-list'),
    path('products/<int:pk>/', product_detail, name='product-detail'),
    path('products/<int:pk>/archive/', product_archive, name='product-archive'),
    path('products/<int:pk>/unarchive/', product_unarchive, name='product-unarchive'),
    path('products/<int:product_pk>/variants/', variant_list, name='product-variant-list'),
    path('products/<int:product_pk>/variants/<int:pk>/', variant_detail, name='product-variant-detail'),
]
