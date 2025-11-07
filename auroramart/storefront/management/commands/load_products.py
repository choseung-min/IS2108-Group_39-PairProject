import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from storefront.models import (
    Category,
    Product,
)  # adjust import if your app label differs


def unique_slug(model, base_slug, slug_field="slug"):
    """
    Generate a unique slug for `model` based on base_slug by appending -2, -3, ...
    """
    slug = base_slug or "item"
    slug = slug.strip("-")
    candidate = slug
    i = 2
    qs = model.objects
    while qs.filter(**{slug_field: candidate}).exists():
        candidate = f"{slug}-{i}"
        i += 1
    return candidate


def get_or_create_category(row):
    """
    Create (or get) a Category and optional Subcategory (as child).
    Returns the most specific Category instance to be assigned to Product.category.
    CSV columns used: Product Category, Product Subcategory
    """
    cat_name = (row.get("Product Category") or "").strip()
    sub_name = (row.get("Product Subcategory") or "").strip()

    if not cat_name:
        raise CommandError("Missing 'Product Category' in row.")

    # Top-level category
    cat_slug_base = slugify(cat_name)
    try:
        category = Category.objects.get(name=cat_name, parent=None)
    except Category.DoesNotExist:
        cat_slug = unique_slug(Category, cat_slug_base)
        category = Category.objects.create(name=cat_name, slug=cat_slug, parent=None)

    # Optional subcategory
    if sub_name:
        sub_slug_base = slugify(sub_name)
        try:
            subcategory = Category.objects.get(name=sub_name, parent=category)
        except Category.DoesNotExist:
            sub_slug = unique_slug(Category, sub_slug_base)
            subcategory = Category.objects.create(
                name=sub_name, slug=sub_slug, parent=category
            )
        return subcategory

    return category


def parse_int(value, default=0):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def parse_decimal(value, default=Decimal("0.00")):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def clamp_rating(r):
    try:
        x = float(r)
    except (ValueError, TypeError):
        return 0.0
    return max(0.0, min(5.0, x))


class Command(BaseCommand):
    help = "Import products from a CSV file into Category/Product tables."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to the CSV file")
        parser.add_argument(
            "--update",
            action="store_true",
            help="If a product with the same SKU exists, update it instead of skipping.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate rows, but do not write to the database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        dry_run = options["dry_run"]
        do_update = options["update"]

        encodings_to_try = ["utf-8-sig", "cp1252", "latin-1"]
        last_err = None

        try:
            for ENC in encodings_to_try:
                try:
                    with open(csv_path, newline="", encoding=ENC) as f:
                        reader = csv.DictReader(f)

                        required_cols = {
                            "SKU code",
                            "Product name",
                            "Product description",
                            "Product Category",
                            "Product Subcategory",
                            "Quantity on hand",
                            "Reorder Quantity",
                            "Unit price",
                            "Product rating",
                        }
                        missing = required_cols - set(reader.fieldnames or [])
                        if missing:
                            raise CommandError(
                                f"CSV is missing columns: {', '.join(sorted(missing))}"
                            )

                        created_count = 0
                        updated_count = 0
                        skipped_count = 0

                        for idx, row in enumerate(reader, start=2):  # header is row 1
                            sku = (row.get("SKU code") or "").strip()
                            name = (row.get("Product name") or "").strip()
                            description = row.get("Product description") or ""

                            if not sku or not name:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"Row {idx}: Missing SKU or Product name. Skipping."
                                    )
                                )
                                skipped_count += 1
                                continue

                            try:
                                category = get_or_create_category(row)
                            except CommandError as e:
                                self.stdout.write(
                                    self.style.WARNING(f"Row {idx}: {e}. Skipping.")
                                )
                                skipped_count += 1
                                continue

                            stock = parse_int(row.get("Quantity on hand"), 0)
                            reorder_threshold = parse_int(
                                row.get("Reorder Quantity"), 10
                            )
                            price = parse_decimal(
                                row.get("Unit price"), Decimal("0.00")
                            )
                            rating = clamp_rating(row.get("Product rating"))

                            base_slug = slugify(name)
                            slug = (
                                base_slug
                                if not Product.objects.filter(slug=base_slug).exists()
                                else unique_slug(Product, base_slug)
                            )

                            # Create or update by SKU
                            try:
                                product = Product.objects.get(sku=sku)
                                if do_update:
                                    product.name = name
                                    product.description = description
                                    product.category = category
                                    product.stock = stock
                                    product.reorder_threshold = reorder_threshold
                                    product.price = price
                                    product.rating = rating
                                    if not product.slug:
                                        product.slug = slug
                                    if not dry_run:
                                        product.save()
                                    updated_count += 1
                                else:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f"Row {idx}: SKU {sku} exists and --update not set. Skipping."
                                        )
                                    )
                                    skipped_count += 1
                            except Product.DoesNotExist:
                                product = Product(
                                    sku=sku,
                                    name=name,
                                    description=description,
                                    category=category,
                                    stock=stock,
                                    reorder_threshold=reorder_threshold,
                                    price=price,
                                    rating=rating,
                                    slug=slug,
                                    is_active=True,
                                )
                                if not dry_run:
                                    product.save()
                                created_count += 1

                        if dry_run:
                            transaction.set_rollback(True)

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Done. Created: {created_count}, Updated: {updated_count}, "
                                f"Skipped: {skipped_count} (decoded with {ENC}) "
                                f"{'(dry run — no changes saved)' if dry_run else ''}"
                            )
                        )
                        return  # success; stop trying encodings

                except UnicodeDecodeError as e:
                    last_err = e
                    continue

            # If we got here, decoding failed for all encodings
            raise CommandError(
                f"Could not decode file with any of {encodings_to_try}: {last_err}"
            )

        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")
