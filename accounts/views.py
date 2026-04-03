from django.shortcuts import render

# Create your views here.
def accounts(request):
    return render(request, "accounts/accounts.html")

# Create your views here.
def login(request):
    return render(request, "accounts/login.html")

def register(request):
    return render(request, "accounts/register.html")

def forget_password(request):
    return render(request, "accounts/forget_password.html")