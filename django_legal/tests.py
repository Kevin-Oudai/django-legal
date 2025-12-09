from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings

from django_legal.decorators import legal_required
from django_legal.models import (
    LegalDocument,
    LegalDocumentAcceptance,
    LegalDocumentSection,
)


def _make_required_document():
    document = LegalDocument.objects.create(
        human_name="Terms of Use",
        slug="terms-of-use",
        is_required=True,
    )
    LegalDocumentSection.objects.create(
        document=document,
        heading="Intro",
        body="Initial content",
        order=1,
    )
    return document


class LegalDocumentPublishTests(TestCase):
    def setUp(self):
        self.document = _make_required_document()

    def test_publish_is_idempotent_when_snapshot_unchanged(self):
        first, created = self.document.publish_new_version()
        self.assertTrue(created)
        first_hash = first.version_hash

        repeat, created_again = self.document.publish_new_version()

        self.assertFalse(created_again)
        self.assertEqual(first.id, repeat.id)
        self.assertEqual(first_hash, repeat.version_hash)
        self.assertEqual(1, self.document.versions.count())

    @patch("django_legal.models.LegalDocument._compute_diff_percent", return_value=10.0)
    def test_publish_advances_version_label_when_content_changes(self, _mock_diff):
        initial, created = self.document.publish_new_version()
        self.assertTrue(created)

        # Update content to trigger a new snapshot.
        section = self.document.sections.first()
        section.body = "Updated content"
        section.save()

        updated, created_again = self.document.publish_new_version()

        self.assertTrue(created_again)
        self.assertNotEqual(initial.id, updated.id)
        self.assertEqual("1.1.0", updated.version_label)
        self.assertNotEqual(initial.version_hash, updated.version_hash)


class LegalRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.document = _make_required_document()
        self.document.publish_new_version()
        self.user = get_user_model().objects.create_user(
            username="alice",
            password="password123",
        )

    @override_settings(LEGAL_ACCEPTANCE_URL="/legal/accept/")
    def test_redirects_to_acceptance_when_missing_required_versions(self):
        @legal_required
        def view(request):
            return HttpResponse("ok")

        request = self.factory.get("/dashboard/")
        request.user = self.user

        response = view(request)

        self.assertEqual(302, response.status_code)
        self.assertTrue(response["Location"].startswith("/legal/accept/"))
        self.assertIn("next=%2Fdashboard%2F", response["Location"])


@override_settings(ROOT_URLCONF="test_project.urls")
class AcceptanceGateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.document = _make_required_document()
        self.version, _ = self.document.publish_new_version()
        self.user = get_user_model().objects.create_user(
            username="bob",
            password="password123",
        )
        self.client.login(username="bob", password="password123")

    def test_gate_shows_missing_versions_and_records_acceptance(self):
        response = self.client.get("/legal/accept/")
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Terms of Use")

        response = self.client.post("/legal/accept/", {"next": "/after/"})

        self.assertEqual(302, response.status_code)
        self.assertEqual("/after/", response["Location"])
        self.assertTrue(
            LegalDocumentAcceptance.objects.filter(
                user=self.user, version=self.version
            ).exists()
        )
