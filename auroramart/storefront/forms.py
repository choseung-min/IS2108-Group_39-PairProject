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