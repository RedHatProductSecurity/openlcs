import ldap

from django.contrib import auth
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import middleware
from django.core.exceptions import ImproperlyConfigured

User = get_user_model()


class RemoteUserMiddleware(middleware.RemoteUserMiddleware):

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the RemoteUserMiddleware class.")
        try:
            username = dict(request.META)["HTTP_" + self.header]
        except KeyError:
            return

        # If the user not exist in the system, will create this user first.
        user_qs = User.objects.filter(username=username)
        if not user_qs.exists():
            self.sync_ldap_user(username)

        # We are seeing this user for the first time in this session, attempt
        # to authenticate the user.
        user = auth.authenticate(remote_user=username)
        if user:
            # User is valid.  Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            auth.login(request, user)

    def sync_ldap_user(self, username):
        conn = ldap.initialize(settings.LDAP_URI)
        ldap_user = conn.search_s(
            settings.LDAP_USERS_DN,
            ldap.SCOPE_SUBTREE,
            filterstr='(uid=' + username + ')',
            attrlist=['uid', 'cn', 'manager', 'mail']
        )[0]
        if 'uid' not in ldap_user[1]:
            print(f"Not find this user: {username}")
            return
        uid = str(ldap_user[1]['uid'][0], encoding='utf-8')
        try:
            user, _ = User.objects.get_or_create(username=uid)
        except Exception as e:
            print(f"Cannot get or create user: {uid}, error: f{e}")
            return

        # Email setting
        mail = ldap_user[1]['mail'][0] if 'mail' in ldap_user[1] else ''
        mail = str(mail, encoding='utf-8') if mail else ''
        if user.email != mail:
            user.email = mail

        # Permission setting
        if uid in settings.OPENLCS_ADMIN_LIST:
            user.is_staff = True
            user.is_superuser = True
        user.save()

        # Manager setting
        if 'manager' in ldap_user[1]:
            l_manager = str(ldap_user[1]['manager'][0], encoding='utf-8')
            muid = l_manager.split(',')[0].split('=')[1]
            try:
                manager, _ = User.objects.get_or_create(
                    username=muid, email=muid + "@redhat.com")
            except Exception as e:
                print(f"Cannot get or create manager: {uid}, error: f{e}")
                return
        else:
            manager = None

        common_name = ldap_user[1]['cn'][0] if 'cn' in ldap_user[1] else None
        common_name = str(common_name,
                          encoding='utf-8') if common_name else None
        profile = user.profile
        if profile.realname != common_name or profile.manager != manager:
            profile.realname = common_name
            profile.manager = manager
            profile.save()
        conn.unbind()
