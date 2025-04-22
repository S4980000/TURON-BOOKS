from django.db import models

nb = dict(null=True, blank=True)

class Category(models.Model):
    name = models.CharField(max_length=256)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='children', **nb)

    def __str__(self):
        return self.name

class Book(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='books')
    file_id = models.CharField(max_length=512)
    caption = models.TextField()

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.pk} {self.caption[:25]}'