from django.forms import ModelForm
from .models import *
from django import forms
class MessageModelForm(ModelForm):
	class Meta:
		model = MessageModel
		fields = '__all__'

class UserModelForm(ModelForm):
	class Meta:
		model= UserModels
		exclude = ['tenant_to']
from django import forms
from .models import TenantModel

class TenantForm(forms.ModelForm):
    class Meta:
        model = TenantModel
        fields = ['name', 'email']

class UploadCSVForm(forms.Form):
    file = forms.FileField(
        label='Upload your CSV file',
        help_text='Please upload a valid CSV file. Max size: 5MB.',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control custom-file-input',  # Add Bootstrap and custom class
            'accept': '.csv',  # Restrict to CSV files
            'id': 'customFile'  # Custom ID for label styling
        })
    )
class Credentials(ModelForm):
	class Meta:
		model=FacebookCredentials
		exclude =['user']
from django import forms
from .models import TicketsStatusModel
from django import forms
from .models import TicketsModel

class TicketsForm(forms.ModelForm):
    class Meta:
        model = TicketsModel
        fields = ['user', 'ticket_number']

class TicketsStatusForm(forms.ModelForm):
    class Meta:
        model = TicketsStatusModel
        fields = ['user', 'tenant_to', 'ticket_number', 'issue', 'ticket_status', 'comments']
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password

class UserProfileForm(forms.ModelForm):
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email']  # Exclude password fields

    def clean(self):
        cleaned_data = super().clean()

        current_password = cleaned_data.get('current_password')
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        username = cleaned_data.get('username')
        email = cleaned_data.get("email")

        # Password validation logic
        user = self.instance  # Get the instance of the user being updated

        if new_password and not current_password:
            raise forms.ValidationError("Current password is required to change the password.")

        if current_password and not check_password(current_password, user.password):
            raise forms.ValidationError("Current password is incorrect.")

        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("New password and confirm password must match.")

        return cleaned_data
