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


@admin.register(LegalDocumentVersion)
class LegalDocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("document", "version_label", "created_at", "published_at")
    search_fields = ("document__human_name", "document__slug", "version_label")
    list_filter = ("document", "created_at", "published_at")


@admin.register(LegalDocumentAcceptance)
class LegalDocumentAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "accepted_at", "ip_address")
    search_fields = ("user__username", "ip_address", "user_agent")
    list_filter = ("accepted_at",)
