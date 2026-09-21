from django.conf import settings


class SecurityHeadersMiddleware:
    """Adds Content-Security-Policy (report-only unless CSP_ENFORCE) and Permissions-Policy."""

    def __init__(self, get_response):
        self.get_response = get_response
        policy = "; ".join(f"{k} {' '.join(v)}" for k, v in settings.CSP_POLICY.items())
        self.header = (
            "Content-Security-Policy"
            if settings.CSP_ENFORCE
            else "Content-Security-Policy-Report-Only"
        )
        self.policy = policy

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/admin/"):
            response.headers.setdefault(self.header, self.policy)
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
        )
        return response
