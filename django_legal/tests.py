from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings

from django_legal.decorators import legal_required
from django_legal.models import (
    LegalDocument,
    LegalDocumentAcceptance,
    LegalDocumentSection,
    check_user_legal_compliance,
)


def _make_required_document(
    *,
    human_name="Terms of Use",
    slug="terms-of-use",
    body="Initial content",
):
    document = LegalDocument.objects.create(
        human_name=human_name,
        slug=slug,
        is_required=True,
    )
    LegalDocumentSection.objects.create(
        document=document,
        heading="Intro",
        body=body,
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

    def test_version_update_diff_marks_added_and_removed_lines(self):
        initial, _created = self.document.publish_new_version()
        section = self.document.sections.first()
        section.body = "Initial content\nAdded detail"
        section.save()
        updated, _created = self.document.publish_new_version()

        diff = updated.get_update_diff()

        self.assertEqual(initial, diff["previous_version"])
        self.assertTrue(diff["has_previous"])
        self.assertTrue(diff["has_changes"])
        self.assertIn(
            {"kind": "added", "label": "Added", "lines": ["Added detail"], "is_changed": True},
            diff["blocks"],
        )

    def test_initial_version_diff_marks_document_as_added(self):
        version, _created = self.document.publish_new_version()

        diff = version.get_update_diff()

        self.assertIsNone(diff["previous_version"])
        self.assertFalse(diff["has_previous"])
        self.assertTrue(diff["has_changes"])
        self.assertEqual("added", diff["blocks"][0]["kind"])


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

    def test_gate_shows_missing_versions_without_bulk_acceptance(self):
        response = self.client.get("/legal/accept/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Terms of Use")
        self.assertContains(response, "Review and decide")
        self.assertNotContains(response, "accept all")

    def test_gate_post_redirects_to_first_missing_document(self):
        response = self.client.post("/legal/accept/")

        self.assertEqual(302, response.status_code)
        self.assertEqual("/legal/terms-of-use/current/", response["Location"])
        self.assertFalse(
            LegalDocumentAcceptance.objects.filter(
                user=self.user, version=self.version
            ).exists()
        )

    def test_current_document_acceptance_moves_to_next_document_then_home(self):
        privacy = _make_required_document(
            human_name="Privacy Policy",
            slug="privacy-policy",
            body="Privacy content",
        )
        privacy_version, _ = privacy.publish_new_version()

        response = self.client.get("/legal/terms-of-use/current/")
        self.assertEqual(200, response.status_code)
        self.assertIn("version_update_diff", response.context)
        self.assertContains(response, "I accept these changes")
        self.assertContains(response, "Decline")

        response = self.client.post(
            "/legal/terms-of-use/current/",
            {"legal_action": "accept", "version_id": str(self.version.pk), "version_hash": self.version.version_hash},
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/legal/privacy-policy/current/", response["Location"])
        self.assertTrue(
            LegalDocumentAcceptance.objects.filter(
                user=self.user, version=self.version
            ).exists()
        )

        response = self.client.post(
            "/legal/privacy-policy/current/",
            {"legal_action": "accept", "version_id": str(privacy_version.pk), "version_hash": privacy_version.version_hash},
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/", response["Location"])
        self.assertTrue(
            LegalDocumentAcceptance.objects.filter(
                user=self.user, version=privacy_version
            ).exists()
        )
        is_compliant, missing_versions = check_user_legal_compliance(self.user)
        self.assertTrue(is_compliant)
        self.assertEqual([], missing_versions)

    def test_current_document_decline_returns_home_without_acceptance(self):
        response = self.client.post(
            "/legal/terms-of-use/current/",
            {"legal_action": "decline"},
        )

        self.assertEqual(302, response.status_code)
        self.assertEqual("/", response["Location"])
        self.assertFalse(
            LegalDocumentAcceptance.objects.filter(
                user=self.user, version=self.version
            ).exists()
        )

    def test_document_specific_template_can_replace_default_template(self):
        custom_document = _make_required_document(
            human_name="Custom Document",
            slug="custom-document",
            body="Custom content",
        )
        custom_document.publish_new_version()

        response = self.client.get("/legal/custom-document/current/")

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Custom template for Custom Document")


class AcceptanceSafetyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="safe", password="test-password")
        self.doc = _make_required_document()
        self.version, _ = self.doc.publish_new_version()
        self.client.force_login(self.user)
        self.url = "/legal/terms-of-use/current/"

    def test_missing_or_unknown_action_never_accepts(self):
        for data in ({}, {"legal_action": "other"}):
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.assertFalse(LegalDocumentAcceptance.objects.exists())

    def test_unseen_new_version_is_not_accepted(self):
        LegalDocumentSection.objects.filter(document=self.doc).update(body="New terms")
        self.doc.publish_new_version()
        response = self.client.post(self.url, {"legal_action": "accept", "version_id": str(self.version.pk), "version_hash": self.version.version_hash})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(LegalDocumentAcceptance.objects.exists())

    def test_metadata_private_by_default_and_records_immutable(self):
        from django.core.exceptions import ValidationError
        from django.db.models.deletion import ProtectedError
        record = LegalDocumentAcceptance.objects.record_acceptance(self.user, self.version, ip_address="203.0.113.1", user_agent="Private browser")
        self.assertEqual((record.ip_address, record.user_agent), ("", ""))
        for obj in (record, self.version):
            with self.assertRaises(ValidationError): obj.save()
            with self.assertRaises(ValidationError): obj.delete()
            with self.assertRaises(ValidationError): type(obj).objects.filter(pk=obj.pk).update(pk=obj.pk)
            with self.assertRaises(ValidationError): type(obj).objects.filter(pk=obj.pk).delete()
        with self.assertRaises(ProtectedError): self.doc.delete()

    def test_safe_next_preserved_and_external_redirect_rejected(self):
        data={"legal_action":"accept", "version_id":str(self.version.pk), "version_hash":self.version.version_hash}
        self.assertEqual(self.client.post(self.url+"?next=/tools/merge-pdf/", data)["Location"], "/tools/merge-pdf/")
        self.assertEqual(self.client.post(self.url+"?next=https://evil.test", data)["Location"], "/")

    def test_save_sections_keeps_published_snapshot_until_explicit_publish(self):
        from django_legal.admin import LegalDocumentAdmin
        from django.contrib.admin import site
        admin = LegalDocumentAdmin(type(self.doc), site)
        with patch("django.contrib.admin.ModelAdmin.save_related"):
            form=type("Form", (), {"instance":self.doc})()
            LegalDocumentSection.objects.filter(document=self.doc).update(body="A draft")
            admin.save_related(None, form, [], True)
        self.assertEqual(self.doc.versions.count(), 1)
        self.assertEqual(self.doc.versions.first().content_snapshot, self.version.content_snapshot)
        _,created=self.doc.publish_new_version()
        self.assertTrue(created)
