from rest_framework.views import exception_handler


def custom_exception_handler(exc,context):
    response = exception_handler(exc,context)
    if response is not None:
        message="Error"
        if response.status_code==400:
            message="Validation Error"
        elif response.status_code==401:
            message="Authentication Failed"
        elif response.status_code==403:
            message="Permission Denied"
        elif response.status_code==404:
            message="Not Found"
        elif response.status_code==429:
            message="Too Many Requests"
        response.data = {
            "success":False,
            "status":response.status_code,
            "message":message,
            "errors":response.data,
        }
    return response