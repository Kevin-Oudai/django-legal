import difflib
import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone


class LegalDocument(models.Model):
    human_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    is_required = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.human_name

    def get_ordered_sections(self):
        return self.sections.all().order_by("order", "id")

    def build_current_snapshot(self) -> str:
        lines: list[str] = []
        for section in self.get_ordered_sections():
            heading = (section.heading or "").strip()
            body = (section.body or "").strip()
            if heading:
                lines.append(heading)
            if body:
                lines.append(body)
            lines.append("")
        return "\n".join(lines).strip()

    def _compute_diff_percent(self, old_snapshot: str, new_snapshot: str) -> float:
        if not old_snapshot and not new_snapshot:
            return 0.0
        if not old_snapshot or not new_snapshot:
            return 100.0
        matcher = difflib.SequenceMatcher(None, old_snapshot, new_snapshot)
        similarity = matcher.ratio()
        return (1.0 - similarity) * 100.0

    def _next_version_label(self, last_version, diff_percent: float) -> str:
        if last_version is None or not last_version.version_label:
            return "1.0.0"

        try:
            major_str, minor_str, patch_str = last_version.version_label.split(".")
            major, minor, patch = int(major_str), int(minor_str), int(patch_str)
        except (ValueError, TypeError):
            major, minor, patch = 1, 0, 0

        if diff_percent <= 5.0:
            patch += 1
        elif diff_percent <= 15.0:
            minor += 1
            patch = 0
        else:
            major += 1
            minor = 0
            patch = 0

        return f"{major}.{minor}.{patch}"

    def publish_new_version(self):
        snapshot = self.build_current_snapshot()
        last_version = self.versions.order_by("-created_at").first()

        if last_version is not None:
            diff_percent = self._compute_diff_percent(
                last_version.content_snapshot,
                snapshot,
            )
        else:
            diff_percent = 100.0

        version_label = self._next_version_label(last_version, diff_percent)
        timestamp = timezone.now()

        hash_input = (
            f"{self.pk}:{self.slug}:{version_label}:{snapshot}:{timestamp.isoformat()}"
        ).encode("utf-8")
        version_hash = hashlib.sha256(hash_input).hexdigest()

        version = LegalDocumentVersion.objects.create(
            document=self,
            version_label=version_label,
            content_snapshot=snapshot,
            created_at=timestamp,
            published_at=timestamp,
            version_hash=version_hash,
        )
        return version


class LegalDocumentSection(models.Model):
    document = models.ForeignKey(
        LegalDocument,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    heading = models.CharField(max_length=255)
    body = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return f"{self.document.slug} - {self.heading}"


class LegalDocumentVersion(models.Model):
    document = models.ForeignKey(
        LegalDocument,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_label = models.CharField(max_length=50)
    content_snapshot = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    version_hash = models.CharField(max_length=128)

    def __str__(self) -> str:
        return f"{self.document.slug} v{self.version_label}"


class LegalDocumentAcceptanceManager(models.Manager):
    def record_acceptance(
        self,
        user,
        version: "LegalDocumentVersion",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> "LegalDocumentAcceptance":
        acceptance, created = self.get_or_create(
            user=user,
            version=version,
            defaults={
                "version_hash_snapshot": version.version_hash,
                "accepted_at": timezone.now(),
                "ip_address": ip_address or "",
                "user_agent": user_agent or "",
            },
        )
        return acceptance


class LegalDocumentAcceptance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_document_acceptances",
    )
    version = models.ForeignKey(
        LegalDocumentVersion,
        on_delete=models.CASCADE,
        related_name="acceptances",
    )
    version_hash_snapshot = models.CharField(max_length=128)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.TextField(blank=True)

    objects = LegalDocumentAcceptanceManager()

    def __str__(self) -> str:
        return f"{self.user} accepted {self.version} at {self.accepted_at}"


def check_user_legal_compliance(user):
    required_documents = LegalDocument.objects.filter(is_required=True)
    missing_versions: list[LegalDocumentVersion] = []

    for document in required_documents:
        current_version = document.versions.order_by("-created_at").first()
        if current_version is None:
            continue

        has_accepted = LegalDocumentAcceptance.objects.filter(
            user=user,
            version=current_version,
        ).exists()

        if not has_accepted:
            missing_versions.append(current_version)

    is_compliant = len(missing_versions) == 0
    return is_compliant, missing_versions
