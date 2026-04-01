from django.shortcuts import render

# Create your views here.
def accunts(request):
    return render(request, "accounts/accounts.html")