from django import forms

from storefront.models import Category, Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "description",
            "category",
            "stock",
            "reorder_threshold",
            "price",
            "image",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "is_active": forms.CheckboxInput(),
        }
        labels = {
            "sku": "SKU Code",
            "name": "Product Name",
            "stock": "Stock Quantity",
            "reorder_threshold": "Reorder Threshold",
            "price": "Price",
            "image": "Product Image",
            "is_active": "Active?",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_categories = Category.objects.filter(
            parent__isnull=True
        ).prefetch_related("category_set")
        self.fields["category"].queryset = Category.objects.all()
