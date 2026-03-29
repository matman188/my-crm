from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q, Value
from django.db.models.functions import Coalesce, Lower
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from crm.forms import (
    CustomerForm,
    ProductCategoryForm,
    ProductForm,
    ProfileUpdateForm,
    ServiceForm,
    SystemUserCreationForm,
    SystemUserPasswordChangeForm,
    SystemUserUpdateForm,
)
from crm.models import Customer, Product, ProductCategory, Service


@login_required
def home(request):
    return render(request, "crm/home.html")


@login_required
def customers(request):
    search_query = request.GET.get("q", "").strip()
    existing_customers = Customer.objects.select_related("owner").all()

    if search_query:
        existing_customers = existing_customers.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(company__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(primary_phone__icontains=search_query)
            | Q(secondary_phone__icontains=search_query)
        )

    existing_customers = existing_customers.order_by(
        Lower("first_name"),
        Lower("last_name"),
        "id",
    )
    return render(
        request,
        "crm/customers.html",
        {
            "existing_customers": existing_customers,
            "search_query": search_query,
        },
    )


@login_required
def create_customer(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.owner = request.user
            customer.save()
            messages.success(request, f"Customer '{customer}' was created.")
            return redirect("customers")
    else:
        form = CustomerForm()

    return render(
        request,
        "crm/customer_form.html",
        {
            "form": form,
            "page_title": "Create Customer",
            "submit_label": "Create customer",
            "form_description": "Add a new customer record to the CRM.",
        },
    )


@login_required
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Customer '{customer}' was updated.")
            return redirect("customers")
    else:
        form = CustomerForm(instance=customer)

    return render(
        request,
        "crm/customer_form.html",
        {
            "form": form,
            "page_title": f"Edit Customer: {customer}",
            "submit_label": "Save changes",
            "form_description": "Update the customer details below.",
        },
    )


@login_required
def delete_customer(request, customer_id):
    if request.method != "POST":
        return HttpResponseForbidden("Customers can only be deleted with a POST request.")

    customer = get_object_or_404(Customer, pk=customer_id)
    customer_name = str(customer)
    customer.delete()
    messages.success(request, f"Customer '{customer_name}' was deleted.")
    return redirect("customers")


@login_required
def product_categories(request):
    search_query = request.GET.get("q", "").strip()
    existing_categories = ProductCategory.objects.annotate(product_count=Count("products"))

    if search_query:
        existing_categories = existing_categories.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    existing_categories = existing_categories.order_by(Lower("name"), "id")
    return render(
        request,
        "crm/product_categories.html",
        {
            "existing_categories": existing_categories,
            "search_query": search_query,
        },
    )


@login_required
def create_product_category(request):
    if request.method == "POST":
        form = ProductCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Category '{category}' was created.")
            return redirect("product_categories")
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
    category = get_object_or_404(ProductCategory, pk=category_id)

    if request.method == "POST":
        form = ProductCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category}' was updated.")
            return redirect("product_categories")
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
    if request.method != "POST":
        return HttpResponseForbidden("Categories can only be deleted with a POST request.")

    category = get_object_or_404(ProductCategory, pk=category_id)
    category_name = str(category)
    category.delete()
    messages.success(request, f"Category '{category_name}' was deleted.")
    return redirect("product_categories")


@login_required
def products(request):
    search_query = request.GET.get("q", "").strip()
    existing_products = Product.objects.select_related("category").prefetch_related(
        Prefetch("services", queryset=Service.objects.order_by("name", "id"))
    ).all()

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
            "existing_products": existing_products,
            "search_query": search_query,
        },
    )


@login_required
def create_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Product '{product}' was created.")
            return redirect("products")
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
    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product}' was updated.")
            return redirect("products")
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
    if request.method != "POST":
        return HttpResponseForbidden("Products can only be deleted with a POST request.")

    product = get_object_or_404(Product, pk=product_id)
    product_name = str(product)
    product.delete()
    messages.success(request, f"Product '{product_name}' was deleted.")
    return redirect("products")


@login_required
def services(request):
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
            "existing_services": existing_services,
            "search_query": search_query,
        },
    )


@login_required
def create_service(request):
    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save()
            messages.success(request, f"Service '{service}' was created.")
            return redirect("services")
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
    service = get_object_or_404(Service, pk=service_id)

    if request.method == "POST":
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f"Service '{service}' was updated.")
            return redirect("services")
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
    if request.method != "POST":
        return HttpResponseForbidden("Services can only be deleted with a POST request.")

    service = get_object_or_404(Service, pk=service_id)
    service_name = str(service)
    service.delete()
    messages.success(request, f"Service '{service_name}' was deleted.")
    return redirect("services")


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("home")
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": "Edit Profile",
            "submit_label": "Save profile",
            "form_description": "Update your own account details.",
        },
    )


@login_required
def users(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can create system users.")

    search_query = request.GET.get("q", "").strip()
    existing_users = get_user_model().objects.all()

    if search_query:
        existing_users = existing_users.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    existing_users = existing_users.order_by(Lower("username"), "id")
    return render(
        request,
        "crm/users.html",
        {
            "existing_users": existing_users,
            "search_query": search_query,
        },
    )


@login_required
def create_user(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can create system users.")

    if request.method == "POST":
        form = SystemUserCreationForm(request.POST)
        if form.is_valid():
            created_user = form.save()
            messages.success(request, f"User '{created_user.username}' was created.")
            return redirect("users")
    else:
        form = SystemUserCreationForm()

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": "Create User",
            "submit_label": "Create user",
        },
    )


@login_required
def edit_user(request, user_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can manage system users.")

    user_to_edit = get_object_or_404(get_user_model(), pk=user_id)

    if request.method == "POST":
        form = SystemUserUpdateForm(request.POST, instance=user_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f"User '{user_to_edit.username}' was updated.")
            return redirect("users")
    else:
        form = SystemUserUpdateForm(instance=user_to_edit)

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": f"Edit User: {user_to_edit.username}",
            "submit_label": "Save changes",
            "form_description": "Update the user's profile details below.",
        },
    )


@login_required
def change_user_password(request, user_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can manage system users.")

    user_to_update = get_object_or_404(get_user_model(), pk=user_id)

    if request.method == "POST":
        form = SystemUserPasswordChangeForm(user_to_update, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Password updated for '{user_to_update.username}'.")
            return redirect("users")
    else:
        form = SystemUserPasswordChangeForm(user_to_update)

    return render(
        request,
        "crm/user_form.html",
        {
            "form": form,
            "page_title": f"Change Password: {user_to_update.username}",
            "submit_label": "Update password",
            "form_description": "Set a new password for this user.",
        },
    )


@login_required
def delete_user(request, user_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only superusers can manage system users.")

    if request.method != "POST":
        return HttpResponseForbidden("Users can only be deleted with a POST request.")

    user_to_delete = get_object_or_404(get_user_model(), pk=user_id)
    username = user_to_delete.username

    if user_to_delete.is_superuser:
        messages.error(request, "Superusers cannot be deleted from this screen.")
        return redirect("users")

    user_to_delete.delete()
    messages.success(request, f"User '{username}' was deleted.")
    return redirect("users")
