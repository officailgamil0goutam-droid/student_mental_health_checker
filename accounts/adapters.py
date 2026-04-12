from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        return '/mood/'


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_connect_redirect_url(self, request, socialaccount):
        return '/mood/'

    def get_login_redirect_url(self, request):
        user = request.user
        try:
            profile = user.profile
            if not profile.university:
                provider = ''
                social = user.socialaccount_set.first()
                if social:
                    provider = social.provider.capitalize()
                return f'/accounts/register/?social=true&provider={provider}'
        except Exception:
            pass
        return '/mood/'