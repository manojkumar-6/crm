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

