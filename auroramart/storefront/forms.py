from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import Customer

User = get_user_model()

class UserSignupForm(UserCreationForm):
    # AbstractUser already has an email field; we expose it and enforce uniqueness
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already used by an account.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # ensure role is set for signups
        user.role = "customer"
        user.email = self.cleaned_data.get("email", "").strip().lower()
        if commit:
            user.save()
        return user
    
class ProfileForm(forms.Form):
    # --- User fields (from signup, minus password) ---
    username = forms.CharField(max_length=150)
    email = forms.EmailField()

    # --- Customer fields (same as your signup page) ---
    name = forms.CharField(label="Full Name", max_length=120, required=False)
    phone = forms.CharField(required=False)
    age = forms.IntegerField(min_value=0, required=False)
    household_size = forms.IntegerField(min_value=1, required=False)
    has_children = forms.BooleanField(required=False)
    monthly_income = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)

    # If your model defines choices, we'll use them; else these render as text.
    gender = forms.ChoiceField(required=False, choices=())
    employment_status = forms.ChoiceField(required=False, choices=())
    occupation = forms.ChoiceField(required=False, choices=())
    education = forms.ChoiceField(required=False, choices=())

    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    city_state = forms.CharField(required=False, max_length=50)
    postal_code = forms.CharField(required=False, max_length=10)

    def __init__(self, user, *args, **kwargs):
        """
        Pass the logged-in user as the first arg:
            form = ProfileForm(request.user, request.POST or None)
        """
        super().__init__(*args, **kwargs)
        self.user = user
        self.customer = getattr(user, "customer", None)

        # Fill initial from instances
        if not self.is_bound:
            self.initial.update({
                "username": user.username,
                "email": user.email or "",
            })
            if self.customer:
                self.initial.update({
                    "name": self.customer.name or "",
                    "phone": self.customer.phone or "",
                    "age": self.customer.age,
                    "household_size": self.customer.household_size,
                    "has_children": self.customer.has_children,
                    "monthly_income": self.customer.monthly_income,
                    "gender": getattr(self.customer, "gender", "") or "",
                    "employment_status": getattr(self.customer, "employment_status", "") or "",
                    "occupation": getattr(self.customer, "occupation", "") or "",
                    "education": getattr(self.customer, "education", "") or "",
                    "address": self.customer.address or "",
                    "city_state": self.customer.city_state or "",
                    "postal_code": self.customer.postal_code or "",
                })

        # Wire up choices from your model if present
        def get_choices(name):
            try:
                return Customer._meta.get_field(name).choices or []
            except Exception:
                # fallback to class-level constants like Customer.GENDER_CHOICES
                return getattr(Customer, f"{name.upper()}_CHOICES", []) or []

        self.fields["gender"].choices = [("", "---------")] + list(get_choices("gender"))
        self.fields["employment_status"].choices = [("", "---------")] + list(get_choices("employment_status"))
        self.fields["occupation"].choices = [("", "---------")] + list(get_choices("occupation"))
        self.fields["education"].choices = [("", "---------")] + list(get_choices("education"))

    # --- Validation (simple & safe) ---
    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        qs = User.objects.filter(username__iexact=username).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already used by an account.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone:
            digits = [c for c in phone if c.isdigit()]
            if len(digits) < 8:
                raise forms.ValidationError("Enter a valid phone number.")
        return phone

    # --- Save both models in one go ---
    def save(self):
        u = self.user
        c = self.customer

        u.username = self.cleaned_data["username"]
        u.email = self.cleaned_data["email"]
        u.save(update_fields=["username", "email"])

        if c is None:
            # Should not happen if you created Customer at signup, but just in case:
            c = Customer.objects.create(user=u)

        for f in [
            "name","phone","age","household_size","has_children","monthly_income",
            "gender","employment_status","occupation","education",
            "address","city_state","postal_code",
        ]:
            setattr(c, f, self.cleaned_data.get(f))
        c.save()
        return u, c
    
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        exclude = ("user",)  
        widgets = {
            "name":             forms.TextInput(attrs={"placeholder": "Full name"}),
            "email":            forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone":            forms.TextInput(attrs={"placeholder": "e.g. +65 9123 4567"}),
            "age":              forms.NumberInput(attrs={"min": 18, "max": 120}),
            "household_size":   forms.Select(),
            "has_children":     forms.CheckboxInput(),
            "monthly_income":   forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "gender":           forms.Select(),
            "employment_status":forms.Select(),
            "occupation":       forms.Select(),
            "education":        forms.Select(),
            "address":          forms.Textarea(attrs={"rows": 3, "placeholder": "Address line"}),
            "postal_code":      forms.TextInput(attrs={"maxlength": 10}),
            "city_state":       forms.TextInput(attrs={"maxlength": 50, "placeholder": "City / State"}),
        }
        labels = {
            "has_children": "Has children",
            "city_state": "City / State",
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        # keep Customer.email unique (model enforces) AND avoid clashing with auth user
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already used by an account.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = [c for c in phone if c.isdigit()]
        if len(digits) < 8:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

    def save(self, user=None, commit=True):
        obj = super().save(commit=False)
        if user is not None:
            obj.user = user
        if commit:
            obj.save()
        return obj

class EmailLoginForm(forms.Form):
    email = forms.EmailField(label="Email",
                             widget=forms.EmailInput(attrs={"placeholder": "Enter your email"}))
    
    password = forms.CharField(label="Password",
                               widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}))
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email", "").strip().lower()
        password = cleaned_data.get("password", "")
        
        if email and password:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise forms.ValidationError("No account found with that email.")
            
            user = authenticate(username=user.username, password=password)
            if user is None:
                raise forms.ValidationError("Invalid email or password.")
            
            cleaned_data["user"] = user
        return cleaned_data
    
class AddressForm(forms.Form):
    address = forms.CharField(label="Address Line", max_length=255,
                                   widget=forms.TextInput(attrs={"placeholder": "123 Main St"}))
    city_state = forms.CharField(label="City/State", max_length=50, required=False)
    postal_code = forms.CharField(label="Postal Code", max_length=10)
    save_to_profile = forms.BooleanField(label="Save this address to my profile", required=False)

class PaymentForm(forms.Form):
    PAYMENT_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('paynow', 'PayNow'),
        ('cod', 'Cash on Delivery'),
    ]
    payment_method = forms.ChoiceField(choices=PAYMENT_CHOICES, widget=forms.RadioSelect)
