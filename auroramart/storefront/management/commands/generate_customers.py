from django.core.management.base import BaseCommand
from storefront.models import User, Customer
import random
from decimal import Decimal


class Command(BaseCommand):
    help = "Generate sample customer data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=20, help="Number of customers to generate"
        )

    def handle(self, *args, **options):
        count = options["count"]

        first_names = [
            "James",
            "Mary",
            "John",
            "Patricia",
            "Robert",
            "Jennifer",
            "Michael",
            "Linda",
            "William",
            "Barbara",
            "David",
            "Elizabeth",
            "Richard",
            "Susan",
            "Joseph",
            "Jessica",
            "Thomas",
            "Sarah",
            "Charles",
            "Karen",
            "Christopher",
            "Nancy",
            "Daniel",
            "Lisa",
            "Matthew",
            "Betty",
            "Anthony",
            "Margaret",
            "Mark",
            "Sandra",
            "Donald",
            "Ashley",
            "Steven",
            "Kimberly",
            "Paul",
            "Emily",
            "Andrew",
            "Donna",
            "Joshua",
            "Michelle",
        ]

        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
            "Rodriguez",
            "Martinez",
            "Hernandez",
            "Lopez",
            "Gonzalez",
            "Wilson",
            "Anderson",
            "Thomas",
            "Taylor",
            "Moore",
            "Jackson",
            "Martin",
            "Lee",
            "Perez",
            "Thompson",
            "White",
            "Harris",
            "Sanchez",
            "Clark",
            "Ramirez",
            "Lewis",
            "Robinson",
        ]

        cities = [
            "New York",
            "Los Angeles",
            "Chicago",
            "Houston",
            "Phoenix",
            "Philadelphia",
            "San Antonio",
            "San Diego",
            "Dallas",
            "San Jose",
            "Austin",
            "Jacksonville",
            "Fort Worth",
            "Columbus",
            "Charlotte",
            "Indianapolis",
            "Seattle",
            "Denver",
            "Boston",
            "Detroit",
        ]

        streets = [
            "Main St",
            "Oak Ave",
            "Maple Dr",
            "Park Blvd",
            "Cedar Ln",
            "Pine St",
            "Elm Ave",
            "Washington St",
            "Lake View Dr",
            "Hill St",
        ]

        genders = ["Male", "Female"]
        household_sizes = [1, 2, 3, 4, 5]
        employment_statuses = [
            "Full-time",
            "Part-time",
            "Student",
            "Self-employed",
            "Retired",
        ]
        occupations = [
            "Sales",
            "Service",
            "Admin",
            "Tech",
            "Education",
            "Skilled Trades",
        ]
        education_levels = ["Diploma", "Bachelor", "Secondary", "Master", "Doctorate"]

        created_count = 0
        for i in range(count):
            # Generate unique username and email
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"{first_name.lower()}.{last_name.lower()}{i + 100}"
            email = f"{username}@example.com"

            # Check if user already exists
            if User.objects.filter(username=username).exists():
                continue

            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password="password123",
                role="customer",
                is_active=random.choice([True, True, True, True, False]),  # 80% active
            )

            # Generate customer data
            age = random.randint(18, 70)
            household_size = random.choice(household_sizes)
            has_children = random.choice([True, False]) if household_size > 1 else False

            # Generate address
            street_number = random.randint(100, 9999)
            street = random.choice(streets)
            city = random.choice(cities)
            postal_code = f"{random.randint(10000, 99999)}"

            # Create customer
            Customer.objects.create(
                user=user,
                phone=f"+1{random.randint(2000000000, 9999999999)}",
                age=age,
                household_size=household_size,
                has_children=has_children,
                can_appeal=True,
                monthly_income=Decimal(random.randint(2000, 15000)),
                gender=random.choice(genders),
                employment_status=random.choice(employment_statuses),
                occupation=random.choice(occupations),
                education=random.choice(education_levels),
                address=f"{street_number} {street}",
                postal_code=postal_code,
                city_state=city,
            )

            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {created_count} customers")
        )
