from django.urls import path

from .views import ManualReviewClaimView, ManualReviewDecisionView, ManualReviewQueueListView

urlpatterns = [
    path("manual-review-queue", ManualReviewQueueListView.as_view(), name="manual-review-queue-list"),
    path(
        "manual-review-queue/<uuid:item_id>/claim",
        ManualReviewClaimView.as_view(),
        name="manual-review-item-claim",
    ),
    path(
        "manual-review-queue/<uuid:item_id>/decision",
        ManualReviewDecisionView.as_view(),
        name="manual-review-item-decision",
    ),
]
