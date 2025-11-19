from django.contrib import admin

from .models import LegalDocument, LegalDocumentAcceptance, LegalDocumentSection, LegalDocumentVersion


class LegalDocumentSectionInline(admin.TabularInline):
    model = LegalDocumentSection
    extra = 1
    fields = ("order", "heading", "body")
    ordering = ("order",)


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ("human_name", "slug", "is_required")
    search_fields = ("human_name", "slug")
    list_filter = ("is_required",)
    inlines = (LegalDocumentSectionInline,)
    actions = ("publish_new_version",)

    def publish_new_version(self, request, queryset):
        for document in queryset:
            document.publish_new_version()
        self.message_user(request, f"Published new version for {queryset.count()} document(s).")

    publish_new_version.short_description = "Publish new legal version from current sections"

    def save_related(self, request, form, formsets, change):
        """
        After saving a document and its sections, ensure there is an
        up-to-date LegalDocumentVersion snapshot.

        - If the document has sections but no versions yet, create the
          initial version (1.0.0).
        - If a latest version exists and the current snapshot differs
          from its content, publish a new version using the diff rules.
        """
        super().save_related(request, form, formsets, change)
        document = form.instance

        if not document.sections.exists():
            return

        last_version = document.versions.order_by("-created_at").first()

        # Always build the current snapshot from the latest saved sections
        # so we compare against the most recent state.
        current_snapshot = document.build_current_snapshot()

        if last_version is None:
            # No versions yet: publish the initial 1.0.0 snapshot.
            document.publish_new_version()
        elif current_snapshot != last_version.content_snapshot:
            # Sections have changed since the last version; publish a new one.
            document.publish_new_version()


@admin.register(LegalDocumentVersion)
class LegalDocumentVersionAdmin(admin.ModelAdmin):
    """
    Read-only view of published legal document versions.

    Versions are immutable snapshots; they are created via the publish
    helper/action on LegalDocument, not edited directly in the admin.
    """

    list_display = ("document", "version_label", "created_at", "published_at")
    search_fields = ("document__human_name", "document__slug", "version_label")
    list_filter = ("document", "created_at", "published_at")
    readonly_fields = (
        "document",
        "version_label",
        "content_snapshot",
        "version_hash",
        "created_at",
        "published_at",
    )

    def has_add_permission(self, request):
        # New versions are created via LegalDocument.publish_new_version,
        # not by adding LegalDocumentVersion records manually.
        return False


@admin.register(LegalDocumentAcceptance)
class LegalDocumentAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "accepted_at", "ip_address")
    search_fields = ("user__username", "ip_address", "user_agent")
    list_filter = ("accepted_at",)
