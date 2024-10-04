from PIL import Image
from transformers import pipeline
import nltk
import requests
from nltk.corpus import wordnet
import tempfile
from django.shortcuts import render,redirect
from .models import *
from django.db.models import Count, Case, When, IntegerField
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from collections import defaultdict
from datetime import datetime
from django.shortcuts import render, get_object_or_404
from .filters import *
from django.shortcuts import render
from .forms import *
from django.http import HttpResponseRedirect
from django.urls import reverse
from functools import wraps
from django.shortcuts import render
from django.db.models import Count
import csv
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.core.mail import send_mail
from django.conf import settings
import json
from django.contrib.auth.models import User
import csv
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import HttpResponse
import pandas as pd

issue_dict={}


def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            print("user not authenticated")
            return HttpResponseRedirect(reverse('login'))  # Redirect to your login URL
    return _wrapped_view

def delete_conversation(request, message_id):
    if request.method == 'POST':
        conversation = get_object_or_404(ConversationModel, id=message_id)
        conversation.delete()
        return redirect('dashboard')  # Adjust as needed
    return HttpResponse(status=405)  # Method not allowed

@login_required(login_url='/')
def upload_csv(request):
    print("getting loaded")
    if request.method == 'POST':
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            print("valid")
            csv_file = request.FILES['file']
            try:
                # Assuming the file is being processed correctly
                df = pd.read_csv(csv_file)
                table_html = df.to_html(classes="table table-striped")  # Generate HTML for the table

                # Return JSON response with HTML table
                return JsonResponse({'message': 'Upload successful'})

            except Exception as e:
                # Return an error response with a descriptive error message
                return JsonResponse({'error': f'There was an error processing the file: {e}'}, status=400)

    # If the request method is not POST or form is invalid, show an error message
    return JsonResponse({'error': 'The form was not submitted successfully. Please try again.'}, status=400)


@login_required(login_url='/')
def verify(request):
    # Parse params from the webhook verification request
    print(request,request.method)

    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge")

    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == "12345":
            # Respond with 200 OK and challenge token from the request

            return HttpResponse(challenge, status=200)
        else:
            # Responds with '403 Forbidden' if verify tokens do not match

            return HttpResponse(str({"status": "error", "message": "Verification failed"}), status=403)
    else:
        # Responds with '400 Bad Request' if verify tokens do not match

        return HttpResponse(str({"status": "error", "message": "Missing parameters"}), status=400)


def group_messages(messages):
    """
    Groups messages by user and hour.
    """
    grouped = defaultdict(lambda: {"id": None, "messages": [], "user": None, "date_queried": None})

    for message in messages:
        # Create a unique key based on user and hour
        date_key = message.date_queried.strftime('%Y-%m-%d %H')
        group_key = f"{message.user.id}_{date_key}"

        # Fill in the grouped dictionary
        if not grouped[group_key]["id"]:
            grouped[group_key]["id"] = message.id
        grouped[group_key]["messages"].append(message)
        grouped[group_key]["user"] = message.user
        grouped[group_key]["date_queried"] = message.date_queried

    return grouped.values()
@login_required(login_url='/')
def issue_detail_view(request, issue_id):
    # Get filters from the GET parameters
    status_filter = request.GET.get('status', '')
    username_search = request.GET.get('username', '')  # Could be user_name or email, depending on your User model
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    sort_by = request.GET.get('sort_by', '')  # Default sorting by date

    # Fetch all tickets for the given issue
    tenant = TenantModel.objects.filter(name=request.user).first()  # Get the tenant object
    tickets = TicketsStatusModel.objects.filter(issue=issue_id, tenant_to=tenant)

    # Apply status filter
    if status_filter:
        tickets = tickets.filter(ticket_status=status_filter)

    # Apply username search
    if username_search:
        tickets = tickets.filter(user__user_name__icontains=username_search)  # Adjust to your actual field name

    # Apply date range filter
    if start_date and end_date:
        tickets = tickets.filter(date_reported__range=[start_date, end_date])

    # Apply sorting
    if sort_by:
        tickets = tickets.order_by(sort_by)

    # Pagination
    paginator = Paginator(tickets, 10)  # Show 10 tickets per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Count ticket statuses for the pie chart
    pending_count = tickets.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.PENDING).count()
    in_progress_count = tickets.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.INPROGRESS).count()
    completed_count = tickets.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.COMPLETED).count()

    context = {
        'page_obj': tickets,
        'status_filter': status_filter,
        'username_search': username_search,
        'start_date': start_date,
        'end_date': end_date,
        'sort_by': sort_by,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
    }

    return render(request, 'accounts/issue_view.html', context)

@csrf_exempt  # Temporarily exempt CSRF for testing; not recommended for production
# views.py
# Adjust import based on your actual model
@login_required(login_url='/')
def get_detailed_export_issue_csv(request):
    # Retrieve data from your model
    tenant=TenantModel.objects.filter(name=request.user)
    print(tenant)
    tickets = TicketsStatusModel.objects.filter(tenant_to=tenant[0])  # Adjust this query to fit your data retrieval needs

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tickets.csv"'

    writer = csv.writer(response)
    # Write CSV header row
    writer.writerow(['Reported User', 'Ticket Number', 'Ticket Status', 'Reported Date', 'Comment'])

    # Write data rows
    for ticket in tickets:
        writer.writerow([
            ticket.user,
            ticket.ticket_number,
            ticket.ticket_status,
            ticket.date_reported,
            ticket.comments
        ])

    return response
@login_required(login_url='/')
def export_issue_csv(request):
    # Retrieve data from your model
    tenant=TenantModel.objects.filter(name=request.user)
    print(tenant)
    tickets = TicketsStatusModel.objects.filter(tenant_to=tenant[0])  # Adjust this query to fit your data retrieval needs

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tickets.csv"'

    writer = csv.writer(response)
    # Write CSV header row
    writer.writerow(['Reported User', 'Ticket Number', 'Ticket Status', 'Reported Date', 'Comment'])

    # Write data rows
    for ticket in tickets:
        writer.writerow([
            ticket.user,
            ticket.ticket_number,
            ticket.ticket_status,
            ticket.date_reported,
            ticket.comments
        ])

    return response
@login_required(login_url='/')
def dashBoard(request):
    # Fetch all orders and customers (if needed for other parts of your dashboard)
    orders = MessageModel.objects.all()
    customers = UserModels.objects.all()
     # Get filters from the GET parameters
    status_filter = request.GET.get('status', '')
    username_search = request.GET.get('username', '')  # Could be user_name or email, depending on your User model
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    sort_by = request.GET.get('sort_by', '')  # Default sorting by date

    # Fetch all tickets for the given issue
    tenant = TenantModel.objects.filter(name=request.user).first()
    tickets_ = TicketsStatusModel.objects.filter(tenant_to=tenant)

    # Apply status filter
    if status_filter:
        tickets_ = tickets_.filter(ticket_status=status_filter)

    # Apply username search
    if username_search:
        tickets_ = tickets_.filter(user__user_name__icontains=username_search)  # Adjust to your actual field name

    # Apply date range filter
    if start_date and end_date:
        tickets_ = tickets_.filter(date_reported__range=[start_date, end_date])

    # Apply sorting
    if sort_by:
        tickets_ = tickets_.order_by(sort_by)

    # Pagination
    paginator = Paginator(tickets_, 10)  # Show 10 tickets per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Count ticket statuses for the pie chart
    pending_count = tickets_.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.PENDING).count()
    in_progress_count = tickets_.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.INPROGRESS).count()
    completed_count = tickets_.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.COMPLETED).count()
    print(pending_count)
    issues_count = TicketsStatusModel.objects.values('issue').annotate(
        total=Count('id'),  # Total number of tickets for each issue
        pending_count=Count(Case(  # Count only pending tickets
            When(ticket_status=TicketsStatusModel.TicketStatusChoices.PENDING, then=1),
            output_field=IntegerField()
        )),
        inprogress_count=Count(Case(  # Count only pending tickets
            When(ticket_status=TicketsStatusModel.TicketStatusChoices.INPROGRESS, then=1),
            output_field=IntegerField()
        )),
        completed_count=Count(Case(  # Count only pending tickets
            When(ticket_status=TicketsStatusModel.TicketStatusChoices.COMPLETED, then=1),
            output_field=IntegerField()
        )),
        users_count=Count('user', distinct=True)  # Count distinct users who reported the issue
    )
    print(issues_count)
    user_conversated = ConversationModel.objects.all()
    print("user",request.user.username)
    username=User.objects.filter(username=request.user.username).first()
    tenant=TenantModel.objects.filter(name=username).first()

    total_users=0
    if tenant :
        total_users =(UserModels.objects.filter(tenant_to=tenant).count())
    # Count interactions per user and order by interaction count
    total_hits = ConversationModel.objects.exclude(ai_model_reply__icontains='welcome message')
    i_count=0
    a_count=0
    for data in total_hits:
        if data.user.tenant_to.email==request.user.email:
            a_count+=1
    for data in ConversationModel.objects.all():
        if data.user.tenant_to.email==request.user.email:
            i_count+=1
    a_count = i_count//2
    today = timezone.now().date()
    if tenant:
        tickets = TicketsStatusModel.objects.filter(tenant_to=tenant)
        ticket_list_ = []
        for ticket in tickets:
            days_reported = (today - ticket.date_reported).days  # Calculate days reported
            ticket_list_.append({
                'ticket': ticket,
                'days_reported': days_reported,
            })
    else:
        ticket_list_=[]
    context = {
        'tickets': tickets_,
        'ticket_list': ticket_list_,
        'today': today,
        "total_users":total_users,
        'total_users_interacted': i_count,
        "i_count":i_count,
        "a_count":a_count,
        "issues_count":issues_count,
        'page_obj': tickets_,
        'status_filter': status_filter,
        'username_search': username_search,
        'start_date': start_date,
        'end_date': end_date,
        'sort_by': sort_by,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
    }


    return render(request, 'accounts/dashboard.html', context)


@csrf_exempt  # You can use CSRF exemption for API-like views if needed
def send_email_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email_description = data.get('emailDescription')
            userData=UserModels.objects.filter(email=request.email).first()
            name=User.objects.filter(username=userData.tenant_to).first()
            tenant_id = data.get('tenant_id')
            tenant=TenantModel.objects.filter(name=name).first()

            facebookData=FacebookCredentials.objects.filter(user=tenant).first()
            print(facebookData)
            for user in UserModels.objects.filter(tenant_to=tenant):
                message = get_text_message_input(user.phone[2:], data)
                conv=ConversationModel(user=user,ai_model_reply="welcome message",user_query=data)
                conv.save()
                send_message(message,facebookData)

            return JsonResponse({'message': 'messages successfully!'}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@method_decorator(csrf_exempt, name='dispatch')
class AutoSaveView(View):
    def post(self, request):
        data = json.loads(request.body)
        email_description = data.get('emailDescription')
        print("email",email_description)
        tenant=User.objects.filter(email=request.user.email).first()
        print(tenant)
        desc=TenantModel.objects.get(name=tenant)
        print(desc)
        desc.email_template=email_description
        desc.save()
        print("saved")
        return JsonResponse({'status': 'success', 'message': 'Auto-saved successfully.'})

def customer(request, pk):
	customer = UserModels.objects.get(id=pk)
	messages = MessageModel.objects.filter(customer=customer)
	conversation_made=ConversationModel.objects.filter(user=UserModels.objects.get(id=pk))
	messages = ConversationModel.objects.filter(user=customer).order_by('date_queried')
	total_messages_sent = messages.count()
	grouped_messages = group_messages(messages)
	context = {'customer':customer, 'messages':conversation_made, 'total_messages':total_messages_sent,'grouped_messages': grouped_messages,'filter': filter
	}
	return render(request, 'accounts/customer.html', context)
def conversation_list(request):
    filter = ConversationFilter(request.GET, queryset=ConversationFilter.objects.all())
    return render(request, 'accounts/customer.html', {'filter': filter})
def user_ai_model_coversation(request,userpk,date):
	customer = UserModels.objects.get(id=userpk)
	messages = ConversationModel.objects.all()
	context = {'customer':customer, 'messages':messages,"date":date
	}
	return render(request, 'accounts/conversation.html', context)
def loginUser(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        login_user = authenticate(request, username=username, password=password)

        if login_user is not None:
            login(request, login_user)
            print(login(request,login_user))
            if request.user.is_superuser:
                return redirect("/adashboard")
            return redirect("/dashboard")
        else:
            error_message = "Invalid username or password."
            return render(request, "accounts/login.html", {'error_message': error_message})

    return render(request, "accounts/login.html")

def update_customer(request, customer_id):
    customer = get_object_or_404(UserModels, id=customer_id)
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        customer.name = name
        customer.email = email
        customer.phone = phone
        customer.save()

        messages.success(request, 'Customer updated successfully!')
        return redirect('/customer_detail/' + str(customer.id))

    return render(request, 'customer_update_form.html', {'customer': customer})
def delete_customer(request, customer_id):
    customer = get_object_or_404(UserModels, id=customer_id)
    if request.method == 'POST':
        customer.delete()
        messages.success(request, 'Customer deleted successfully!')
        return redirect('/customer_list/')  # Redirect to the customer list or another appropriate page

    return render(request, 'customer_detail.html', {'customer': customer})
def createUser(request):
    action = 'create_user'
    form = UserModelForm()
    tenant=TenantModel.objects.filter(name=request.user.username)
    if request.method == "POST":
        form = UserModelForm(request.POST)
        if form.is_valid():
            print("form submitted")
            user = form.save(commit=False)  # Don't save the form to the database yet
            user.tenant_to = tenant[0]  # Assign the tenant to the logged-in user's tenant
            user.save()  # Save the form with the tenant assigned
            return redirect("/dashboard")

    context = {'action': action, 'form': form}
    return render(request, 'accounts/t.html', context)

def updateCredentials(request):
    action = 'credentials'
    form = Credentials()
    if request.method == "POST":
        form = Credentials(request.POST)

        if form.is_valid():
            credentials = form.save(commit=False
                            )
            user=TenantModel.objects.filter(name=request.user).first()
            print(user)
            credentials.user = user
                # Assign the excluded user field
            credentials.save()                     # Save the form with the user included
            return redirect("/dashboard")

    context = {'action': action, 'form': form}
    return render(request, 'accounts/t.html', context)

def deleteUser(request,pk):
	user=UserModels.objects.get(id=pk)
	user.objects.delete()
	return redirect("/")

import google.generativeai as genai

genai.configure(api_key="AIzaSyDy3FHTLDFr_gUM74_RuVHoOSnF5BEC-No")

model = genai.GenerativeModel('gemini-1.5-flash-latest')

message_dict = {}



# Download necessary datasets for nltk
nltk.download('wordnet')
nltk.download('omw-1.4')

# Initialize sentiment-analysis pipeline
model_name = "distilbert-base-uncased-finetuned-sst-2-english"
sentiment_pipeline = pipeline("sentiment-analysis", model=model_name)

# Constants
SUPPORT_THRESHOLD = 4
ACKNOWLEDGMENT_KEYWORDS = set()

# WhatsApp API constants
# MEDIA_URL = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/media"

# Helper function to get acknowledgment keywords dynamically
def get_acknowledgment_keywords(base_keywords):
    synonyms = set(base_keywords)
    for word in base_keywords:
        for syn in wordnet.synsets(word):
            for lemma in syn.lemmas():
                synonyms.add(lemma.name().lower())
    return synonyms

# Get synonyms for the base acknowledgment words
base_acknowledgment_words = ["thank", "thanks","fine", "cool", "got it", "understand"]
ACKNOWLEDGMENT_KEYWORDS = get_acknowledgment_keywords(base_acknowledgment_words)
ACKNOWLEDGMENT_RESPONSE = "You're welcome! Feel free to reach out if you need more help."

# Track conversation and support status
message_dict = {}
support_count_dict = {}
processed_messages = set()

# Helper function to construct the WhatsApp text message input
def get_text_message_input(recipient, text):
    return json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    })

# Helper function to construct the Whfprint("inputatsApp media message input
def get_media_message_input(recipient, media_id, caption=None):
    return json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "image",
        "image": {
            "id": media_id,
            "caption": caption if caption else ''
        }
    })
import nltk
from nltk.corpus import wordnet

# Download necessary datasets for nltk
nltk.download('wordnet')
nltk.download('omw-1.4')

# Initialize support request keywords
SUPPORT_REQUEST_KEYWORDS = set()

# Helper function to get synonyms of keywords dynamically
def get_support_keywords(base_keywords):
    synonyms = set(base_keywords)
    for word in base_keywords:
        for syn in wordnet.synsets(word):
            for lemma in syn.lemmas():
                synonyms.add(lemma.name().lower())
    return synonyms

# Define base support request keywords
base_support_keywords = ["help", "support", "assist", "team"]
SUPPORT_REQUEST_KEYWORDS = get_support_keywords(base_support_keywords)

# Updated function to check if user is requesting support
def check_support_needed(message):
    """
    Check if the user is explicitly asking for support using keywords.
    """
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in SUPPORT_REQUEST_KEYWORDS)

# Updated get_gemini_response function
def  get_gemini_response(input_message, recipient,caption, media=None):
    if is_acknowledgment(input_message):
        message_dict[recipient] = []
        return ACKNOWLEDGMENT_RESPONSE
    print(input_message)
    if(len(caption)):
        input_message=caption
    if recipient not in message_dict:
        message_dict[recipient] = []
    # if (mes)
    print("input message",input_message)
    message_dict[recipient].append(input_message)

    # Check if the user is explicitly asking for support
    support_needed = check_support_needed(input_message)
    print("support needed",support_needed)
    # Initialize support count if recipient is not already tracked
    if recipient not in support_count_dict:
        support_count_dict[recipient] = 0

    if support_needed:
        support_count_dict[recipient] += 1

    # Check if the user explicitly requested external help
    if support_count_dict[recipient] >= 3:  # Change the threshold to 1
        message_dict[recipient] = []
        support_count_dict[recipient]=0
        return ("It looks like you need additional help. I've raised a support request, "
                "and our team will reach out to you soon.")

    full_input = " ".join(message_dict[recipient])

    if media:
        image = Image.open(media['file_path'])
        # media_response = process_media_with_model(media['file_path'])
        response = model.generate_content([full_input, image])

    else:
        response = model.generate_content(full_input )

    message_dict[recipient].append(response.text[:150])
    response=model.generate_content('''Analyzing Support Need:

Analyze the provided response and determine if it needs the additional phrase: "I can raise a request for support if needed."
If the response already covers support or additional help, return the same text with no changes.
If the response lacks support information, add the phrase to the end of the response text if it is not a grreting or acknowledge message.
If the response cannot be handled, return "Our support team will reach out to you."
User Asking for Support Multiple Times:

If the user asks for support the first or second time, respond with troubleshooting steps (for example, asking for more details about the problem).
If the user asks for support more than 2 times, return "I've raised a request, and our support team will reach out to you soon."
Return the final text, ensuring no other changes are made to the original response unless the phrase or support escalation is added.
the text is
''' + response.text)
    print(message_dict)
    if(response.text =="I've raised a request, and our support team will reach out to you soon."):
        message_dict[recipient]=[]
        print("triggered a email")
    return response.text
def process_media_with_model(file_path):
    print(f"Processing media file at: {file_path}")
    # Implement the actual model's media processing logic here.
    # For example, pass the image to a computer vision model.
    return "Media processed successfully."

# Function to check for acknowledgment in the user's message
def is_acknowledgment(message):
    return any(keyword in message.lower() for keyword in ACKNOWLEDGMENT_KEYWORDS)

# Function to analyze sentiment of a message
def check_support_needed(message):
    result = sentiment_pipeline(message)
    sentiment = result[0]['label']
    return sentiment == 'NEGATIVE'

# Function to handle media retrieval
def process_media(media_id,caption,facebookData):
    url = f"https://graph.facebook.com/{facebookData.version}/{media_id}"
    headers = {
        "Authorization": f"Bearer {facebookData.accessToken}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        media_url = response.json().get('url')
        media_type = response.headers['Content-Type']

        # Download media content
        media_content = download_media(media_url,facebookData)

        # Save media content to a file and return the file path
        if media_content:
            file_path = save_media_file(media_content, media_type)
            return {"url": media_url, "type": media_type, "file_path": file_path,"captions":caption}
        else:
            print("Failed to download media content.")
    else:
        print(f"Failed to retrieve media: {response.status_code}, {response.text}")
    return None

# Function to download media from a URL
def download_media(media_url,facebookData):
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,

    }
    response = requests.get(media_url,headers=headers)
    print("downloading the media",response.text)
    if response.status_code == 200:
        return response.content
    return None

# Function to save media content to a file
import tempfile
import threading
import time
import os

# Helper function to delete the file after a delay
def delayed_file_deletion(file_path, delay):
    time.sleep(delay)  # Wait for the specified delay (in seconds)
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"File {file_path} deleted after {delay} seconds.")

# Updated save_media_file function
def save_media_file(media_content, media_type):
    file_extension = get_file_extension(media_type)

    # Create a temporary file without automatic deletion
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}")
    try:
        # Write media content to the temporary file
        temp_file.write(media_content)
        temp_file_path = temp_file.name
        print(f"Saving the media at {temp_file_path}")
    finally:
        temp_file.close()  # Close the file to ensure data is flushed to disk

    # Start a thread to delete the file after 2 minutes (120 seconds)
    deletion_thread = threading.Thread(target=delayed_file_deletion, args=(temp_file_path, 30))
    deletion_thread.start()
    return temp_file_path


# Function to get file extension based on media type
def get_file_extension(media_type):
    if 'image' in media_type:
        return 'jpg'
    elif 'video' in media_type:
        return 'mp4'
    elif 'application/pdf' in media_type:
        return 'pdf'
    return 'bin'

# Function to process WhatsApp messages
def process_whatsapp_message(body):
    print('body',body)
    message_data = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_id = message_data.get("id")
    receipient_number=message_data.get("from")[2:]
    print(receipient_number)
    userData=UserModels.objects.filter(phone=receipient_number).first()
    print(userData)
    name=User.objects.filter(username=userData.tenant_to).first()
    tenant=TenantModel.objects.filter(name=name).first()
    facebookData=FacebookCredentials.objects.filter(user=tenant).first()
    print(facebookData)
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]

    if message_id in processed_messages:
        print(f"Message {message_id} already processed.")
        return

    processed_messages.add(message_id)

    media = None
    caption=""
    if "image" in message_data:
        media_id = message_data["image"]["id"]
        if message_data["image"]["caption"]:
            caption=message_data["image"]["caption"]
        media = process_media(media_id,caption,facebookData)
    elif "document" in message_data:
        media_id = message_data["document"]["id"]
        media = process_media(media_id,caption,facebookData)
    elif "video" in message_data:
        media_id = message_data["video"]["id"]
        media = process_media(media_id,caption,facebookData)

    message_body = message_data.get("text", {}).get("body", "")
    response = get_gemini_response(message_body, wa_id,caption, media)
    data = get_text_message_input(wa_id, response)
    send_message(data,facebookData)

# Function to send messages via WhatsApp
def send_message(data,facebookData):

    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }
    print("data",data,facebookData)
    response = requests.post(url, headers=headers, data=data)
    try:
            pass
    except ValueError:
        print("Response is not in JSON format")

    return response

# View to handle incoming WhatsApp messages
@csrf_exempt
def handle_message(request):
    body = json.loads(request.body.decode("utf-8"))

    if is_valid_whatsapp_message(body):
        process_whatsapp_message(body)

# Function to check if the incoming message is valid for processing
def is_valid_whatsapp_message(body):
    print("vlaid")
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
    )

# View to send WhatsApp messages manually
from django.http import JsonResponse

@csrf_exempt
def send_whatsapp_message(request):
    if request.method == 'POST':
        print("here")
        handle_message(request)
        return JsonResponse({'status': 'Message sent successfully'}, status=200)
    elif request.method == 'GET':
        verify(request)
        return JsonResponse({'status': 'Verification successful'}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

from django.shortcuts import render, get_object_or_404, redirect

from django.http import JsonResponse
from .models import TenantModel
from django.contrib.auth.models import User
from .forms import TenantForm  # You need to create this form for editing
@superuser_required
# List all tenants and handle CRUD operations
def tenant_list(request):
    tenants = TenantModel.objects.all()  # Fetch all tenants from the database
    return render(request, 'accounts/tenant_list.html', {'tenants': tenants})
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from .models import TenantModel
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.contrib.auth.models import User
@superuser_required
def tenant_page(request):
    tenants = TenantModel.objects.all()
    users = User.objects.all()
    print(users)
    return render(request, 'accounts/tenant.html', {'tenants': tenants, 'users':users})
@superuser_required
@csrf_exempt
def create_tenant(request):
    if request.method == 'POST':

        email = request.POST.get('email')
        user_=User.objects.filter(email=email).first()

        tenant = TenantModel(name=user_, email=email)
        tenant.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

# Update tenant
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from .models import TenantModel  # Adjust the import according to your app structure

@csrf_exempt
@superuser_required
def update_tenant(request):
    if request.method == 'POST':
        tenant_id = request.POST.get('tenant_id')
        name = request.POST.get('name')
        email = request.POST.get('email')
        user=User.objects.filter(email=email).first()
        # Fetch the tenant
        print(user)
        for u in User.objects.all():
            print(u.id)
            print(u.username)
            print(u.email)
        tenant = get_object_or_404(TenantModel, name=user)
        user.username=name
        user.email=email
        user.save()
        tenant.name=user
        tenant.email=email
        tenant.save()

        # tenant = get_object_or_404(TenantModel, id=tenant_id)

        # # Update tenant details
        # tenant.name = name
        # tenant.email = email
        # tenant.save()

        return JsonResponse({'success': True, 'message': 'Tenant updated successfully!'})

    return JsonResponse({'error': 'Invalid request method'}, status=400)


# Delete tenant
@superuser_required
@csrf_exempt
def delete_tenant(request, tenant_id):
    if request.method == 'DELETE':
        tenant = get_object_or_404(TenantModel, id=tenant_id)
        tenant.delete()

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request method'}, status=400)
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import TenantModel, UserModels, TicketsModel, TicketsStatusModel, IssueReported
from django.contrib.auth.models import User

# List all data related to users, tenants, and tickets
@superuser_required
def dashboard_(request):
    context = {
        'users': UserModels.objects.all(),
        'tenants': TenantModel.objects.all(),
        'tickets': TicketsModel.objects.all(),
        'ticket_status': TicketsStatusModel.objects.all(),
        'issues_reported': IssueReported.objects.all(),
    }
    return render(request, 'accounts/d.html', context)

# Create a new user
@superuser_required
@csrf_exempt
def create_user(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        tenant_id = request.POST.get('tenant_to')

        tenant = get_object_or_404(TenantModel, id=tenant_id)
        user = UserModels.objects.create(name=name, phone=phone, email=email, tenant_to=tenant)
        return JsonResponse({'success': True, 'user_id': user.id})

    return JsonResponse({'error': 'Invalid request'}, status=400)

# Update a user
@superuser_required
@csrf_exempt
def update_user(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')

        user = get_object_or_404(UserModels, id=user_id)
        user.name = name
        user.phone = phone
        user.email = email
        user.save()

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request'}, status=400)

# Delete a user
@superuser_required
def delete_user(request, user_id):
    user = get_object_or_404(UserModels, id=user_id)
    user.delete()
    return JsonResponse({'success': True})

# Create a new ticket
@superuser_required
def create_ticket(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        ticket_number = request.POST.get('ticket_number')
        descrition=request.POST.get('ticket_des')
        print("descrioto",descrition)
        user = get_object_or_404(UserModels, id=user_id)
        ticket = TicketsModel.objects.create(user=user, ticket_number=ticket_number,Description=descrition)
        ticket.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request'}, status=400)

@superuser_required
def facebook_credentials_page(request):
    credentials = FacebookCredentials.objects.all()
    tenants = TenantModel.objects.all()
    for c in credentials:
        print(c.accessToken)
        print(c.version)
    print(credentials)
    return render(request, 'accounts/f.html', {'credentials': credentials, 'tenants': tenants})
@superuser_required
@csrf_exempt
def create_facebook_credential(request):
    if request.method == 'POST':
        tenant_id = request.POST.get('tenant_id')
        app_id = request.POST.get('appId')
        phone_number_id = request.POST.get('phoneNumberId')
        version = request.POST.get('version')
        accessToken=request.POST.get('accessToken')
        tenant = get_object_or_404(TenantModel, id=tenant_id)
        credential = FacebookCredentials(user=tenant, appId=app_id, phoneNumberId=phone_number_id, version=version,accessToken=accessToken)
        credential.save()

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request method'}, status=400)
@superuser_required
@csrf_exempt
def update_facebook_credential(request):
    if request.method == 'POST':
        credential_id = request.POST.get('credential_id')
        app_id = request.POST.get('appId')
        phone_number_id = request.POST.get('phoneNumberId')
        version = request.POST.get('version')
        token=request.POST.get('accessToken')
        credential = get_object_or_404(FacebookCredentials, id=credential_id)
        credential.appId = app_id
        credential.phoneNumberId = phone_number_id
        credential.version = version
        credential.accessToken=token
        credential.save()

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request method'}, status=400)
@superuser_required
@csrf_exempt
def delete_facebook_credential(request, credential_id):
    if request.method == 'DELETE':
        credential = get_object_or_404(FacebookCredentials, id=credential_id)
        credential.delete()

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request method'}, status=400)
@superuser_required
def ticket_status_list(request):
    tickets = TicketsStatusModel.objects.all()
    # Assuming you have models for User, Tenant, and Ticket
    users = UserModels.objects.all()
    tenants = TenantModel.objects.all()
    ticket_numbers = TicketsModel.objects.all()
    print(ticket_numbers)
    issues=IssueModel.objects.all()
    print(issues)
    return render(request, 'accounts/m.html', {
        'tickets': tickets,
        'users': users,
        'tenants': tenants,
        'ticket_numbers': ticket_numbers,
        'issues':issues
    })
@superuser_required
@csrf_exempt
def create_ticket_status(request):
    if request.method == 'POST':
        form = TicketsStatusForm(request.POST)

        # Access form data for debugging
        user = request.POST.get('user')
        tenant_to = request.POST.get('tenant_to')
        ticket_number = request.POST.get('ticket_number')
        issue = request.POST.get('issue')
        ticket_status = request.POST.get('ticket_status')
        comments = request.POST.get('comments')

        print(f"User: {user}")
        print(f"Tenant: {tenant_to}")
        print(f"Ticket Number: {ticket_number}")
        print(f"Issue: {issue}")
        print(f"Ticket Status: {ticket_status}")
        print(f"Comments: {comments}")

        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            # Return errors if form is not valid
            print(f"Form Errors: {form.errors}")
            return JsonResponse({'success': False, 'error': form.errors})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

@superuser_required
@csrf_exempt
def update_ticket_status(request):
    print("int his ",request.method)
    if request.method == 'POST':
        print("in post")
        ticket_id = request.POST.get('ticket_id')
        print(ticket_id)
        ticket = get_object_or_404(TicketsStatusModel, id=ticket_id)
        form = TicketsStatusForm(request.POST, instance=ticket)
        print("form",form)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid data'})
@superuser_required
@csrf_exempt
def delete_ticket_status(request, ticket_id):
    if request.method == 'DELETE':
        ticket = get_object_or_404(TicketsStatusModel, id=ticket_id)
        ticket.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@superuser_required
def issue_list(request):
    issues = IssueModel.objects.all()
    return render(request,  'accounts/issue.html', {'issues': issues})
@superuser_required
@csrf_exempt
def create_issue(request):
    if request.method == 'POST':
        issue_name = request.POST.get('issue_name')
        if issue_name:
            IssueModel.objects.create(issue_name=issue_name)
            return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid data'})
@superuser_required
@csrf_exempt
def update_issue(request, issue_id):
    issue = get_object_or_404(IssueModel, id=issue_id)
    if request.method == 'POST':
        issue_name = request.POST.get('issue_name')
        if issue_name:
            issue.issue_name = issue_name
            issue.save()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid data'})
@superuser_required
@csrf_exempt
def delete_issue(request, issue_id):
    issue = get_object_or_404(IssueModel, id=issue_id)
    if request.method == 'DELETE':
        issue.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Error deleting the issue'})

@superuser_required
@csrf_exempt  # Allow AJAX requests without CSRF token verification
def create_ticket(request):
    if request.method == 'POST':
        user_id = request.POST.get('user')
        ticket_number = request.POST.get('ticket_number')
        descrition=request.POST.get('ticket_des')
        try:
            user = get_object_or_404(UserModels, id=user_id)
            ticket = TicketsModel.objects.create(user=user, ticket_number=ticket_number,Description=descrition)
            return JsonResponse({'success': True, 'ticket_id': ticket.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})
@superuser_required
@csrf_exempt
def update_ticket(request, ticket_id):
    if request.method == 'POST':
        ticket = get_object_or_404(TicketsModel, id=ticket_id)
        user_id = request.POST.get('user')
        ticket_number = request.POST.get('ticket_number')
        description=request.POST.get('ticket_des')
        try:
            user = get_object_or_404(UserModels, id=user_id)
            ticket.user = user
            ticket.ticket_number = ticket_number
            ticket.Description=description
            ticket.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})
@superuser_required
@csrf_exempt
def delete_ticket(request, ticket_id):
    if request.method == 'DELETE':
        ticket = get_object_or_404(TicketsModel, id=ticket_id)

        try:
            ticket.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})
from django.shortcuts import render
from .models import TicketsModel, UserModels
@superuser_required
def list_tickets(request):
    tickets = TicketsModel.objects.all()
    users = UserModels.objects.all()  # Assuming this is where your users come from
    return render(request, 'accounts/tickets.html', {'tickets': tickets, 'users': users})
@superuser_required

def adashboard(request):
    # Get total counts for each statistic
    total_users_interacted = ConversationModel.objects.values('user').distinct().count()
    total_ai_hits = ConversationModel.objects.exclude(ai_model_reply__icontains='welcome message').count()

    total_messages_sent = ConversationModel.objects.count()

    # Data for Tenant Interactions
    tenant_names = []
    # Initialize a dictionary to store AI hits per tenant, year, and month
    ai_hits_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    # Iterate through all conversations to populate the ai_hits_counts dictionary
    for conversation in ConversationModel.objects.all():
        if conversation.date_queried:
            tenant = conversation.user.tenant_to.name.username  # Adjust based on your tenant field
            year = conversation.date_queried.year
            month = conversation.date_queried.month
            ai_hits_counts[tenant][year][month] += 1
    print(ai_hits_counts)
    # Prepare the filtered AI hits data for the frontend
    ai_hits_filtered = []
    for tenant, years_data in ai_hits_counts.items():
        if tenant not in tenant_names:
            tenant_names.append(tenant)

        for year, months_data in years_data.items():
                for month, count in months_data.items():
                    ai_hits_filtered.append({
                        'tenant': tenant,
                        'year': year,
                        'month': month,
                        'count': count
                    })
    # Convert QuerySet objects to lists for JSON serialization
    years = list(set(conversation.date_queried.year for conversation in ConversationModel.objects.all()))
    months = list(set(conversation.date_queried.month for conversation in ConversationModel.objects.all()))
    days = list(range(1, 32))  # Static list of days

    context = {
        'total_users_interacted': total_users_interacted,
        'total_ai_hits': total_ai_hits,
        'total_messages_sent': total_messages_sent,
        'tenant_names': tenant_names,
        'ai_hits_filtered': ai_hits_filtered,
        'years': years,  # Unique years for filtering
        'months': months,  # Unique months for filtering
        'days': days,  # Static list of days for filtering
    }

    return render(request, 'accounts/adashboard.html', context)

from django.http import JsonResponse
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

# Get all users
def get_users(request):
    users = User.objects.all()
    return render(request, 'accounts/u.html', {'users': users})

# Create a user
@csrf_exempt
def create_user_(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        is_superuser = request.POST.get('is_superuser') == 'true'
        password=request.POST.get('password')

        user = User.objects.create(username=username, email=email, is_superuser=is_superuser,password=password)
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

# Get user details (for editing)
def get_user(request):
    user_id = request.GET.get('id')
    user = User.objects.get(id=user_id)
    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_superuser': user.is_superuser,
        "password":user.password
    })

# Update user
@csrf_exempt
def update_user_(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        username = request.POST.get('username')
        email = request.POST.get('email')
        is_superuser = request.POST.get('is_superuser') == 'true'

        user = User.objects.get(id=user_id)
        user.username = username
        user.email = email
        user.is_superuser = is_superuser
        user.save()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

# Delete user
@csrf_exempt
def delete_user(request):
    if request.method == 'DELETE':
        user_id = request.GET.get('id')
        User.objects.get(id=user_id).delete()
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid method'})
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import UserModels
from django.views.decorators.csrf import csrf_exempt

def user_list(request):

    tenant=TenantModel.objects.filter(email=request.user.email).first()
    users = UserModels.objects.filter(tenant_to=tenant)
    return render(request, 'accounts/utenant.html', {'users': users})

@csrf_exempt
def create_user_tenant(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        tenant_id = request.POST.get('tenant_id')

        user = UserModels(name=name, phone=phone, email=email, tenant_to_id=tenant_id)
        user.save()
        return JsonResponse({'success': True})

@csrf_exempt
def update_user_tenant(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        tenant_id = request.POST.get('tenant_id')

        user = UserModels.objects.get(id=user_id)
        user.name = name
        user.phone = phone
        user.email = email
        user.tenant_to_id = tenant_id
        user.save()
        return JsonResponse({'success': True})

@csrf_exempt
def delete_user_tenant(request, user_id):
    if request.method == 'DELETE':
        user = UserModels.objects.get(id=user_id)
        user.delete()
        return JsonResponse({'success': True})

