from django.urls import path
from .views import UploadReportView, CategorizeAccountsView, GenerateDisputeView, DownloadPDFView

urlpatterns = [
    path("upload-report/", UploadReportView.as_view(), name="upload_report"),
    path("categorize-accounts/", CategorizeAccountsView.as_view(), name="categorize_accounts"),
    path("generate-dispute/", GenerateDisputeView.as_view(), name="generate_dispute"),
    path("download-pdf/", DownloadPDFView.as_view(), name="download_pdf"),
]