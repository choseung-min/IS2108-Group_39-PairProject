import csv
from django.utils.text import slugify
from storefront.models import Category, Product


def unique_slug(model, base_slug, instance_id=None):
    """Generate a unique slug by appending numbers if needed."""
    slug = base_slug or "item"
    slug = slug.strip("-")
    candidate = slug
    i = 2

    while True:
        # Check if slug exists, excluding current instance if updating
        qs = model.objects.filter(slug=candidate)
        if instance_id:
            qs = qs.exclude(id=instance_id)
        if not qs.exists():
            return candidate
        candidate = f"{slug}-{i}"
        i += 1


with open("b2c_products_500.csv", newline="", encoding="latin1") as f:
    reader = csv.DictReader(f)
    count = 0

    for row in reader:
        # Create or get main category
        cat_name = row["Product Category"]
        cat_slug = slugify(cat_name)

        main_cat, created = Category.objects.get_or_create(
            name=cat_name,
            defaults={"slug": unique_slug(Category, cat_slug), "parent": None},
        )

        # Create or get subcategory if exists
        sub_cat = None
        if row["Product Subcategory"]:
            sub_name = row["Product Subcategory"]
            sub_slug = slugify(sub_name)

            sub_cat, created = Category.objects.get_or_create(
                name=sub_name,
                parent=main_cat,
                defaults={"slug": unique_slug(Category, sub_slug)},
            )

        # Create or update product
        product_name = row["Product name"]
        sku = row["SKU code"]
        base_slug = slugify(product_name)

        # Check if product exists
        try:
            product = Product.objects.get(sku=sku)
            # Update existing product
            product.name = product_name
            product.description = row["Product description"]
            product.stock = int(row.get("Quantity on hand", 0))
            product.reorder_threshold = int(row.get("Reorder Quantity", 10))
            product.price = float(row.get("Unit price", 0))
            product.rating = float(row.get("Product rating", 0) or 0)
            product.category = sub_cat or main_cat
            product.is_active = True
            product.save()
        except Product.DoesNotExist:
            # Create new product
            Product.objects.create(
                sku=sku,
                name=product_name,
                slug=unique_slug(Product, base_slug),
                description=row["Product description"],
                stock=int(row.get("Quantity on hand", 0)),
                reorder_threshold=int(row.get("Reorder Quantity", 10)),
                price=float(row.get("Unit price", 0)),
                rating=float(row.get("Product rating", 0) or 0),
                category=sub_cat or main_cat,
                is_active=True,
            )

        count += 1

print(f"✅ Imported {count} products successfully.")
