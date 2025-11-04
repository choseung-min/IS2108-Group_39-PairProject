import csv
from adminpanel.models import Category, Product

with open("b2c_products_500.csv", newline="", encoding="latin1") as f:
    reader = csv.DictReader(f)
    for row in reader:
        main_cat, _ = Category.objects.get_or_create(
            name=row["Product Category"], parent=None
        )
        sub_cat = None
        if row["Product Subcategory"]:
            sub_cat, _ = Category.objects.get_or_create(
                name=row["Product Subcategory"], parent=main_cat
            )

        Product.objects.update_or_create(
            sku=row["SKU code"],
            defaults={
                "name": row["Product name"],
                "description": row["Product description"],
                "stock": int(row.get("Quantity on hand", 0)),
                "reorder_threshold": int(row.get("Reorder Quantity", 10)),
                "price": float(row.get("Unit price", 0)),
                "rating": float(row.get("Product rating", 0) or 0),
                "category": sub_cat or main_cat,
                "is_active": True,
            },
        )

print("✅ Imported all products successfully.")
