from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Category, Book

admin.site.unregister(User)


class BookInline(admin.TabularInline):
    model = Book
    extra = 1
    fields = ("file_name", "caption", "file_id")
    readonly_fields = ("created_date", "updated_date")
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "book_count")
    list_filter = ("parent",)
    search_fields = ("name",)
    inlines = [BookInline]

    def book_count(self, obj):
        return obj.books.count()

    book_count.short_description = "Books in this category"


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("file_name", "short_caption", "category", "created_date")
    list_filter = ("category__parent", "category")
    search_fields = ("caption", "file_name")
    readonly_fields = ("created_date", "updated_date")
    autocomplete_fields = ("category",)

    def short_caption(self, obj):
        return obj.caption[:50] + ("…" if len(obj.caption) > 50 else "")

    short_caption.short_description = "Caption"


class MyUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    # "groups",
                    # "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

admin.site.register(User, MyUserAdmin)
