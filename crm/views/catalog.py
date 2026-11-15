from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q, Value
from django.db.models.functions import Coalesce, Lower
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from crm.forms import ProductCategoryForm, ProductForm, ServiceForm
from crm.models import Product, ProductCategory, Service

from .common import has_permission, list_page, return_to_list
from django.utils import timezone
from django.views.decorators.http import require_POST


@login_required
def product_categories(request):
    if not has_permission(request.user, "crm.view_productcategory"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    search_query = request.GET.get("q", "").strip()
    existing_categories = ProductCategory.objects.annotate(
        product_count=Count("products")
    )

    if search_query:
        existing_categories = existing_categories.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    existing_categories = existing_categories.order_by(Lower("name"), "id")
    return render(
        request,
        "crm/product_categories.html",
        {
            **list_page(request, existing_categories, "existing_categories"),
            "search_query": search_query,
        },
    )


@login_required
def create_product_category(request):
    if not has_permission(request.user, "crm.add_productcategory"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    if request.method == "POST":
        form = ProductCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Category '{category}' was created.")
            return return_to_list(request, "product_categories")
    else:
        form = ProductCategoryForm()

    return render(
        request,
        "crm/catalog_form.html",
        {
            "form": form,
            "page_title": "Create Product Category",
            "submit_label": "Create category",
            "form_description": "Add a category to group related products together.",
            "back_url": "product_categories",
            "back_label": "Back to categories",
        },
    )


@login_required
def edit_product_category(request, category_id):
    if not has_permission(request.user, "crm.change_productcategory"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    category = get_object_or_404(ProductCategory, pk=category_id)

    if request.method == "POST":
        form = ProductCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category}' was updated.")
            return return_to_list(request, "product_categories")
    else:
        form = ProductCategoryForm(instance=category)

    return render(
        request,
        "crm/catalog_form.html",
        {
            "form": form,
            "page_title": f"Edit Product Category: {category}",
            "submit_label": "Save changes",
            "form_description": "Update the category details below.",
            "back_url": "product_categories",
            "back_label": "Back to categories",
        },
    )


@login_required
def delete_product_category(request, category_id):
    if not has_permission(request.user, "crm.delete_productcategory"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    if request.method != "POST":
        return HttpResponseForbidden(
            "Categories can only be deleted with a POST request."
        )

    category = get_object_or_404(ProductCategory, pk=category_id)
    category_name = str(category)
    category.delete()
    messages.success(request, f"Category '{category_name}' was deleted.")
    return return_to_list(request, "product_categories")


@login_required
def products(request):
    if not has_permission(request.user, "crm.view_product"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    search_query = request.GET.get("q", "").strip()
    existing_products = (
        Product.objects.select_related("category")
        .prefetch_related(
            Prefetch("services", queryset=Service.objects.order_by("name", "id"))
        )
        .all()
    )

    catalog_status = request.GET.get("status", "active")
    if catalog_status not in ("active", "archived", "all"):
        catalog_status = "active"
    if catalog_status != "all":
        existing_products = existing_products.filter(
            is_archived=catalog_status == "archived"
        )

    if search_query:
        existing_products = existing_products.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(services__name__icontains=search_query)
        ).distinct()

    existing_products = existing_products.order_by(Lower("name"), "id")
    return render(
        request,
        "crm/products.html",
        {
            **list_page(request, existing_products, "existing_products"),
            "catalog_status": catalog_status,
            "search_query": search_query,
        },
    )


@login_required
def create_product(request):
    if not has_permission(request.user, "crm.add_product"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Product '{product}' was created.")
            return return_to_list(request, "products")
    else:
        form = ProductForm()

    return render(
        request,
        "crm/catalog_form.html",
        {
            "form": form,
            "page_title": "Create Product",
            "submit_label": "Create product",
            "form_description": "Add a product and optionally attach it to a category.",
            "back_url": "products",
            "back_label": "Back to products",
        },
    )


@login_required
def edit_product(request, product_id):
    if not has_permission(request.user, "crm.change_product"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product}' was updated.")
            return return_to_list(request, "products")
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "crm/catalog_form.html",
        {
            "form": form,
            "page_title": f"Edit Product: {product}",
            "submit_label": "Save changes",
            "form_description": "Update the product details below.",
            "back_url": "products",
            "back_label": "Back to products",
        },
    )


@login_required
def delete_product(request, product_id):
    if not has_permission(request.user, "crm.delete_product"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    if request.method != "POST":
        return HttpResponseForbidden(
            "Products can only be deleted with a POST request."
        )

    product = get_object_or_404(Product, pk=product_id)
    product_name = str(product)
    try:
        product.delete()
    except ProtectedError:
        messages.error(
            request, "This product is used on a service order and cannot be deleted."
        )
        return return_to_list(request, "products")
    messages.success(request, f"Product '{product_name}' was deleted.")
    return return_to_list(request, "products")


@login_required
def services(request):
    if not has_permission(request.user, "crm.view_service"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    search_query = request.GET.get("q", "").strip()
    existing_services = Service.objects.prefetch_related(
        Prefetch(
            "products",
            queryset=Product.objects.select_related("category").order_by(
                Lower(Coalesce("category__name", Value("~no-category~"))),
                Lower("name"),
                "id",
            ),
        )
    ).all()

    catalog_status = request.GET.get("status", "active")
    if catalog_status not in ("active", "archived", "all"):
        catalog_status = "active"
    if catalog_status != "all":
        existing_services = existing_services.filter(
            is_archived=catalog_status == "archived"
        )

    if search_query:
        existing_services = existing_services.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(products__name__icontains=search_query)
        ).distinct()

    existing_services = existing_services.order_by(Lower("name"), "id")
    return render(
        request,
        "crm/services.html",
        {
            **list_page(request, existing_services, "existing_services"),
            "catalog_status": catalog_status,
            "search_query": search_query,
        },
    )


@login_required
def create_service(request):
    if not has_permission(request.user, "crm.add_service"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save()
            messages.success(request, f"Service '{service}' was created.")
            return return_to_list(request, "services")
    else:
        form = ServiceForm()

    return render(
        request,
        "crm/catalog_form.html",
        {
            "form": form,
            "page_title": "Create Service",
            "submit_label": "Create service",
            "form_description": "Add a service with pricing and optionally link it to products.",
            "back_url": "services",
            "back_label": "Back to services",
        },
    )


@login_required
def edit_service(request, service_id):
    if not has_permission(request.user, "crm.change_service"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    service = get_object_or_404(Service, pk=service_id)

    if request.method == "POST":
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f"Service '{service}' was updated.")
            return return_to_list(request, "services")
    else:
        form = ServiceForm(instance=service)

    return render(
        request,
        "crm/catalog_form.html",
        {
            "form": form,
            "page_title": f"Edit Service: {service}",
            "submit_label": "Save changes",
            "form_description": "Update the service details and linked products below.",
            "back_url": "services",
            "back_label": "Back to services",
        },
    )


@login_required
def delete_service(request, service_id):
    if not has_permission(request.user, "crm.delete_service"):
        return HttpResponseForbidden("Only admin users can manage configuration.")

    if request.method != "POST":
        return HttpResponseForbidden(
            "Services can only be deleted with a POST request."
        )

    service = get_object_or_404(Service, pk=service_id)
    service_name = str(service)
    try:
        service.delete()
    except ProtectedError:
        messages.error(
            request, "This service is used on a service order and cannot be deleted."
        )
        return return_to_list(request, "services")
    messages.success(request, f"Service '{service_name}' was deleted.")
    return return_to_list(request, "services")


@login_required
@require_POST
def set_catalog_archive(request, kind, object_id, archived):
    model = {"product": Product, "service": Service}[kind]
    if not has_permission(request.user, f"crm.change_{kind}"):
        return HttpResponseForbidden("You cannot change this catalogue record.")
    record = get_object_or_404(model, pk=object_id)
    model.objects.filter(pk=record.pk).update(
        is_archived=archived, updated_at=timezone.now()
    )
    messages.success(
        request,
        f"{kind.title()} '{record}' was {'archived' if archived else 'restored'}.",
    )
    return return_to_list(request, kind + "s")
