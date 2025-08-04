from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
import datetime

class HasConversionAllowance(permissions.BasePermission):
    """
    Custom permission to check if the user has conversion allowance.
    Authenticated users have unlimited conversions.
    Unauthenticated users have a limited number of conversions per day.
    """
    message = 'Conversion limit exceeded. Please create an account to process more files.'
    code = 'conversion_limit_exceeded'

    def has_permission(self, request, view):
        # Authenticated users have unlimited conversions
        if request.user and request.user.is_authenticated:
            return True

        # Unauthenticated users have a limit based on their session
        session = request.session
        today_str = datetime.date.today().isoformat()
        
        # Initialize or retrieve conversion count for today
        conversion_counts = session.get('conversion_counts', {})
        current_day_count = conversion_counts.get(today_str, 0)

        # Define the limit for unauthenticated users
        UNAUTH_CONVERSION_LIMIT = 2 # Example: 2 conversions per day for unauthenticated users

        if request.method == 'POST':
            if current_day_count >= UNAUTH_CONVERSION_LIMIT:
                # If limit exceeded for POST request, raise PermissionDenied with custom code
                raise PermissionDenied(detail={'detail': self.message, 'code': self.code})
            else:
                # Increment count for successful POST
                conversion_counts[today_str] = current_day_count + 1
                session['conversion_counts'] = conversion_counts
                session.modified = True # Ensure session is saved
                return True
        
        # For GET requests (e.g., status/download), allow if the job exists/is being checked
        # and doesn't explicitly involve creating a new conversion.
        # This permission only restricts the *creation* of new conversion jobs.
        return True # Allow GET, HEAD, OPTIONS requests