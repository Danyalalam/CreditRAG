from django.urls import path
from .views import ProcessView

urlpatterns = [
    path("process/", ProcessView.as_view(), name="process"),
]

##