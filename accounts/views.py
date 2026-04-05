from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import RegisterForm

# Create your views here.
def accounts(request):
    return render(request, "accounts/accounts.html")

# Create your views here.
def login(request):
    return render(request, "accounts/login.html")


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # 👈 auto login
            return redirect('home')  # 👈 redirect here
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})
# def register(request):
#     return render(request, "accounts/register.html")

def forget_password(request):
    return render(request, "accounts/forget_password.html")