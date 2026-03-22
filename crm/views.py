from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    return render(request, "crm/home.html")


@login_required
def customers(request):
    return render(request, "crm/customers.html")
