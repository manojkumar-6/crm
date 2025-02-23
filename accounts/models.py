from django.db import models
from django.contrib.auth.models import User
class TenantModel(models.Model):
    id = models.AutoField(primary_key=True)  # Optional: Explicitly set id as primary key
    name = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    email_template= models.CharField(max_length=5000)

    def __str__(self):
        return self.name.username
class TemplateModel(models.Model):
     id = models.AutoField(primary_key=True)  # Optional: Explicitly set id as primary key
     name = models.ForeignKey(User, on_delete=models.CASCADE)
     templateName=models.CharField(max_length=50)
     templateDescription=models.CharField(max_length=2000)
     def __str__(self):
          return self.templateName
class UserModels(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, null=True)
    phone = models.CharField(max_length=200, null=True)
    email = models.EmailField(null=True)
    tenant_to=models.ForeignKey(TenantModel, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    address=models.CharField(max_length=2000)
    archived = models.BooleanField(default=False)
    def __str__(self):
	    return self.name
class DashboardAccessProvidedByClientModel(models.Model):
     user=models.ForeignKey(User,on_delete=models.CASCADE)
     access_provided_by=models.ForeignKey(TenantModel,on_delete=models.CASCADE)
     def __str__(self):
          return self.access_provided_by.name.username
class AssigneModel(models.Model):
     name=models.CharField(max_length=100)
     email=models.CharField(max_length=10)
     client=models.ForeignKey(TenantModel,on_delete=models.CASCADE)
     def __str__(self):
          return self.name
class TicketsModel(models.Model):
    user = models.ForeignKey(UserModels, on_delete=models.CASCADE)  # Use Django's User model or your custom User model
    ticket_number = models.CharField(max_length=45, unique=True)  # Optional: Ensure ticket numbers are unique
    Description=models.CharField(max_length=10000)
    def __str__(self):
          return self.ticket_number
class IssueModel(models.Model):
    id = models.AutoField(primary_key=True)
    issue_name = models.CharField(max_length=100)

    def __str__(self):
        return self.issue_name

class TicketsStatusModel(models.Model):
    class TicketStatusChoices(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        INPROGRESS = "INPROGRESS", "INPROGRESS"
        COMPLETED = "COMPLETED", "COMPLETED"

    user = models.ForeignKey(UserModels, on_delete=models.CASCADE)
    tenant_to = models.ForeignKey(TenantModel, on_delete=models.CASCADE)
    assigne=models.ForeignKey(AssigneModel,on_delete=models.CASCADE, null=True, blank=True)
    ticket_number = models.ForeignKey(TicketsModel, on_delete=models.CASCADE)
    issue=models.CharField(max_length=24)
    image_path=models.ImageField(upload_to='uploads', blank=True, null=True)

    ticket_status = models.CharField(
        max_length=20,
        choices=TicketStatusChoices.choices,
        default=TicketStatusChoices.PENDING
    )
    date_reported = models.DateField(auto_now_add=True)
    comments = models.CharField(max_length=800)
    commentHistory=models.CharField(max_length=15000)
    description=models.CharField(max_length=10000)

    def __str__(self):
        return self.ticket_status

class FacebookCredentials(models.Model):
	user=models.ForeignKey(TenantModel, on_delete=models.CASCADE)
	appId=models.CharField(max_length=50)
	version=models.CharField(max_length=10)
	phoneNumberId=models.CharField(max_length=20,unique=True)
	accessToken=models.CharField(max_length=243)
	def __str__(self):
            return self.phoneNumberId
class ChatOptionsToTenant(models.Model):
    user=models.ForeignKey(User, on_delete=models.CASCADE)
    options=models.CharField(max_length=24)
    def __str__(self):
         return self.options
class MessageModel(models.Model):
	customer = models.ForeignKey(UserModels, on_delete= models.SET_NULL, null=True)
	ai_model_hit=models.IntegerField(default=0)
	total_messages_sent=models.IntegerField(default=0)
	def __str__(self):
		return str(self.customer)
class ConversationModel(models.Model):
    user = models.ForeignKey('UserModels', on_delete=models.CASCADE)
    date_queried = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    ai_model_reply = models.CharField(max_length=7000)
    user_query = models.CharField(max_length=5000)
    is_seen = models.BooleanField(default=False)  # New field to mark if the message has been seen

    def __str__(self):
        return self.user.name
class IssueReported(models.Model):
    class IssueChoices(models.TextChoices):
        WATERISSUE = "water", "Water"
    issue = models.CharField(max_length=50, choices=IssueChoices.choices)
    user = models.ForeignKey(UserModels, on_delete=models.CASCADE)
    reported_count = models.IntegerField(default=0)
    escalated_count = models.IntegerField(default=0)
    def __str__(self):
        return self.user.name












