from django.conf import settings
from django.contrib.auth import logout
from django.utils import timezone
import datetime


class RoleBasedSessionTimeoutMiddleware:
    """
    Middleware to set different session timeout durations based on user role.
    - Admin users: 2 hours timeout
    - Customer users: 1 week timeout
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Determine session timeout based on user role
            if (
                request.user.is_staff
                or request.user.is_superuser
                or request.user.role == "admin"
            ):
                # Admin user - 2 hours timeout
                session_timeout = settings.ADMIN_SESSION_TIMEOUT
            else:
                # Regular customer - 1 week timeout
                session_timeout = settings.CUSTOMER_SESSION_TIMEOUT

            # Get the last activity time from session
            last_activity = request.session.get("last_activity")

            if last_activity:
                # Convert last_activity string to datetime if needed
                if isinstance(last_activity, str):
                    last_activity = datetime.datetime.fromisoformat(last_activity)

                # Calculate time since last activity
                now = timezone.now()
                time_since_activity = (now - last_activity).total_seconds()

                # Check if session has expired
                if time_since_activity > session_timeout:
                    # Session expired - logout user
                    logout(request)
                    request.session.flush()
                else:
                    # Update last activity time
                    request.session["last_activity"] = now.isoformat()
            else:
                # First time - set last activity
                request.session["last_activity"] = timezone.now().isoformat()

            # Set the session age for this request
            request.session.set_expiry(session_timeout)

        response = self.get_response(request)
        return response
