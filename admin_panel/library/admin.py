from django.contrib import admin

from .models import Category, Book


class BookInline(admin.TabularInline):
    model = Book
    extra = 1
    fields = ("caption", "file_id")
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
    list_display = ("short_caption", "category", "created_date")
    list_filter = ("category__parent", "category")
    search_fields = ("caption",)
    readonly_fields = ("created_date", "updated_date")
    autocomplete_fields = ("category",)

    def short_caption(self, obj):
        return obj.caption[:50] + ("…" if len(obj.caption) > 50 else "")

    short_caption.short_description = "Caption"
