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

reslove_dict=dict()

user_data_dict=dict()

user_intiated_chat=dict()

user_issue_dict=dict()

image_media_dict=dict()

global_ticket_number=[1011]

def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            print("user not authenticated")
            return HttpResponseRedirect(reverse('login'))  # Redirect to your login URL
    return _wrapped_view

def client_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            user=User.objects.filter(username=request.user.username,email=request.user.email).first()
            if ((TenantModel.objects.filter(name=user)).first()):
                return view_func(request, *args, **kwargs)
            else:
                print("doesnt have required permissions")
                return HttpResponseRedirect(reverse('login'))
        else:
                print("doesnt have required permissions")
                return HttpResponseRedirect(reverse('login'))  # Redirect to your login URL
    return _wrapped_view

def delete_conversation(request, message_id):
    if request.method == 'POST':
        conversation = get_object_or_404(ConversationModel, id=message_id)
        conversation.delete()
        return redirect('dashboard')  # Adjust as needed
    return HttpResponse(status=405)  # Method not allowed
def send_onbarding_mail(username,email_,link,password=None):
    smtp_server = "smtp.hostinger.com"
    smtp_port = 587  # Use 465 if you want SSL
    sender_email = "notifications@fixm8.com"  # Your email address
    receiver_email = email_  # Recipient's email
    password = "Vlookup@2024"  # Your email account password

    # Create the email message
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "On Boarding Email"

    # Email body with an HTML table
    body = f"""
<html>
    <body>
        <h3>Hello, You are account has been craeted sucessfully</h3>

        <p>you can login with this credentails to the dashboard {link}</p>

        <br>
        <p> username :{username}</p>

        <br>temp password :12345678@A</p>
    Thanks
"""
    message.attach((body, "html"))
    try:
        # Connect to the SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection with TLS

        # Log in to the server
        server.login(sender_email, password)

        # Send the email
        server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close the connection
        server.quit()
@login_required(login_url='/')
def upload_csv(request):
    print("getting loaded")
    if request.method == 'POST':
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            print("valid")
            csv_file = request.FILES['file']
            try:
                # Read the CSV file
                df = pd.read_csv(csv_file)
                home_directory_link = request.build_absolute_uri('/')

                # Validate the required columns
                if not all(col in df.columns for col in ['username', 'phone', 'email']):
                    return JsonResponse({'error': 'CSV file must contain username, phone, and email columns.'}, status=400)
                if (request.user.is_superuser):
                    for index, row in df.iterrows():
                        username = row['username']
                        email = row['email']
                        phone = row['phone']
                        user=User(username=username, email=email)
                        user.set_password("12345678@A")
                        user.save()
                        print("creating tenant")
                        tenant=TenantModel(name=user,email=email)
                        tenant.save()
                        print("sending onbarding mail")
                        send_onbarding_mail(username,email,home_directory_link)
                    return JsonResponse({'message': f'Uploaded {len(df)} users successfully.'})

                else:

                    user_=User.objects.filter(username=request.user.username,email=request.user.email).first()
                    tenant=TenantModel.objects.filter(name=user_).first()
                    # Iterate over the DataFrame and create User instances
                    for index, row in df.iterrows():
                        username = row['username']
                        email = row['email']
                        phone = row['phone']

                        # Create user with default password
                        user = UserModels(name=username, email=email, phone=phone,tenant_to=tenant)
                        user.save()
                        print("user dsaved")
                        # Optionally, you can save phone number if you have a field for it in your user model
                        # user.profile.phone = phone  # assuming you have a related Profile model
                        # user.profile.save()

                    return JsonResponse({'message': f'Uploaded {len(df)} users successfully.'})

            except Exception as e:
                    return JsonResponse({'error': f'There was an error processing the file: {e}'}, status=400)

    return JsonResponse({'error': 'The form was not submitted successfully. Please try again.'}, status=400)


def verify(request):
    # Parse params from the webhook verification request
    print(request,request.method)

    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge")
    print("token",token,mode,challenge,HttpResponse(challenge,content_type="text/plain", status=200))
    # Check if a token and mode were sent
    if mode == "subscribe" and token == '12345':
        # Log the verification success
        print("suvess")
        # Respond with 200 OK and challenge token from the request
        return HttpResponse(challenge,content_type="text/plain",status=200)

    # Handle other cases (optional, depending on your needs)
    return HttpResponse("Verification failed", status=403)

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
    tenant=TenantModel.objects.filter(name=request.user,email=request.user.email)
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
    tenant=TenantModel.objects.filter(name=request.user,email=request.user.email)
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
from django.db.models import Count
import calendar
from django.db.models.functions import TruncDate, TruncHour
from django.db.models import F, Func
from django.db.models import Count, F, ExpressionWrapper, IntegerField
from django.db.models.functions import TruncWeek
from django.db.models.functions import TruncDay
@client_access_required
def dashBoard(request):
    # Fetch all orders and customers (if needed for other parts of your dashboard)

    status_filter = request.GET.get('status', '')
    username_search = request.GET.get('username', '')  # Could be user_name or email, depending on your User model
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    sort_by = request.GET.get('sort_by', '')  # Default sorting by date
    user_logged_in=User.objects.filter(username=request.user,email=request.user.email).first()
    check_user_dashboard_access=DashboardAccessProvidedByClientModel.objects.filter(user=user_logged_in).first()
    # Fetch all tickets for the given issue
    if(check_user_dashboard_access):
        tenant=check_user_dashboard_access.access_provided_by
    else:
        tenant = TenantModel.objects.filter(name=request.user,email=request.user.email).first()
    print(tenant)
    tickets_ = TicketsStatusModel.objects.filter(tenant_to=tenant)
    t_tickets_=TicketsStatusModel.objects.filter(tenant_to=tenant)
    print(tickets_)
    # Apply status filter
    if status_filter:
        tickets_ = tickets_.filter(ticket_status=status_filter)
        print(tickets_)
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
    pending_count = t_tickets_.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.PENDING).count()
    in_progress_count = t_tickets_.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.INPROGRESS).count()
    completed_count = t_tickets_.filter(ticket_status=TicketsStatusModel.TicketStatusChoices.COMPLETED).count()

    user_conversated = ConversationModel.objects.all()
    print("user",request.user.username)
    username=User.objects.filter(username=request.user.username).first()
    tenant__=User.objects.filter(username=request.user.username,email=request.user.email).first()
    templates = TemplateModel.objects.filter(name=tenant__)
    print(templates)
    #

    # Tickets per day (truncated to date)
    # tickets_per_day = tickets_.annotate(
    #     date_reported_truncated=Func(
    #         F('date_reported'), function='DATE', template="%(expressions)s"
    #     )
    # ).values('date_reported_truncated').annotate(count=Count('id')).order_by('date_reported_truncated')

    # tickets_per_day_data = {
    #     'labels': [ticket['date_reported_truncated'] for ticket in tickets_per_day],
    #     'data': [ticket['count'] for ticket in tickets_per_day]
    # }
    # print(tickets_per_day_data)
    today = timezone.now()
    start_of_month = today.replace(day=1)
    end_of_month = today.replace(day=28) + timezone.timedelta(days=4)  # Ensures we get the last day of the month

    # Query tickets raised within the current month and group them by week
    tickets_s = TicketsStatusModel.objects.filter(date_reported__gte=start_of_month, date_reported__lte=end_of_month) \
        .annotate(week_start=TruncWeek('date_reported')) \
        .values('week_start') \
        .annotate(ticket_count=Count('id')) \
        .order_by('week_start')

    # Prepare data for rendering
    week_data = {
        'week_1': 0,
        'week_2': 0,
        'week_3': 0,
        'week_4': 0,
    }
    today = timezone.now()
    current_year = today.year
    current_month = today.month
    # Categorize tickets by week number
    for ticket in tickets_s:
        week_start = ticket['week_start']
        week_number = (week_start.day - 1) // 7 + 1  # Calculate the week number (1, 2, 3, or 4)
        week_key = f'week_{week_number}'
        week_data[week_key] += ticket['ticket_count']
    _, days_in_month = calendar.monthrange(current_year, current_month)

    # Get the start and end date for the current month
    start_of_month = today.replace(day=1)
    end_of_month = today.replace(day=days_in_month)

    # Query tickets raised within the current month and group them by day
    tickets = TicketsStatusModel.objects.filter(date_reported__gte=start_of_month, date_reported__lte=end_of_month) \
        .annotate(day=TruncDay('date_reported')) \
        .values('day') \
        .annotate(ticket_count=Count('id')) \
        .order_by('day')

    # Create a dictionary with days as keys and ticket counts as values
    tickets_per_day = defaultdict(int)  # Defaulting to 0 if no tickets for a day

    # Fill the dictionary with actual ticket data
    for ticket in tickets:
        print("ticket",ticket['day'].day)
        tickets_per_day[ticket['day'].day] = ticket['ticket_count']
    print("ticket",tickets_per_day,"t",tickets_per_day.items())
    # Create a list of days (1 to n) with ticket counts for the chart

    dates = [str(day) for day in range(1, days_in_month + 1)]
    ticket_counts = [int(tickets_per_day[day]) for day in range(1, days_in_month + 1)]
    print('ticket_counts',ticket_counts)
    ticket_range=[int(day) for day in range(1, days_in_month + 1) ]
    print("ticket_range",ticket_range)
    total_users=0
    if tenant :
        total_users =(UserModels.objects.filter(tenant_to=tenant).count())
    # Count interactions per user and order by interaction count
    total_hits = ConversationModel.objects.exclude(ai_model_reply__icontains='welcome message')
    i_count=0
    temp=set()
    a_count=0
    m_count=0
    for data in total_hits:
        if data.user.tenant_to.email==request.user.email and data.user.tenant_to.name.username==request.user.username:
            a_count+=1
    for data in ConversationModel.objects.all():
        if data.user.tenant_to.email==request.user.email and data.user.tenant_to.name.username==request.user.username:
            temp.add(data.user)
            m_count+=1
    i_count=len(list(temp))
    today = timezone.now().date()
    if tenant:
        tickets = TicketsStatusModel.objects.filter(tenant_to=tenant)
        ticket_list_ = []
        for ticket in tickets_:
            days_reported = (today - ticket.date_reported).days  # Calculate days reported
            ticket_list_.append({
                'ticket': ticket,
                'days_reported': days_reported,
            })
    else:
        ticket_list_=[]
    users=UserModels.objects.filter(tenant_to=tenant)
    print("week_data",week_data)
    context = {
        'tickets': tickets_,
        'ticket_list': ticket_list_,
        'today': today,
        "total_users":total_users,
        'total_users_interacted': i_count,
        'users':users,
        "i_count":m_count,
        "a_count":a_count,
        'page_obj': tickets_,
        'status_filter': status_filter,
        'username_search': username_search,
        'start_date': start_date,
        'end_date': end_date,
        'sort_by': sort_by,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'templates': templates,
        "data_for_pie_chart": [pending_count,in_progress_count,completed_count],
        "week_data":[int(week_data['week_1']),int(week_data['week_2']),int(week_data['week_3']),int(week_data["week_4"])],
        "ticket_counts":ticket_counts,
        "ticket_range":ticket_range,

    }


    return render(request, 'accounts/dashboard.html', context)
from bs4 import BeautifulSoup
import re

def html_to_whatsapp_text(html_content):
    # Parse HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Replace <b>, <strong> with WhatsApp-friendly *bold* syntax
    for b_tag in soup.find_all(['b', 'strong']):
        if b_tag.string:  # Ensure there is text inside the tag
            b_tag.string = '*' + b_tag.string + '*'  # Wrap content with *

    # Replace <i>, <em> with WhatsApp-friendly _italic_ syntax
    for i_tag in soup.find_all(['i', 'em']):
        if i_tag.string:  # Ensure there is text inside the tag
            i_tag.string = '_' + i_tag.string + '_'  # Wrap content with _

    # Replace <u> with WhatsApp-friendly ~underline~ syntax
    for u_tag in soup.find_all('u'):
        if u_tag.string:  # Ensure there is text inside the tag
            u_tag.string = '~' + u_tag.string + '~'  # Wrap content with ~

    # Handle links (<a href="URL">link text</a>) and make them clickable
    for a_tag in soup.find_all('a', href=True):
        link = a_tag['href']
        text = a_tag.get_text()

        if text:  # Ensure the link text is not empty
            # If there's text, display the text followed by the URL
            a_tag.string = f"{text} ({link})"
        else:
            # If there is no text, just display the URL itself
            a_tag.string = link  # Remove the <a> tag, keep the URL as plain text

    # Handle <br> and <p> tags to insert newlines
    for br_tag in soup.find_all('br'):
        if br_tag.string:  # Ensure there is text inside the tag
            br_tag.string = '\n' + br_tag.string + '\n'  # Wrap content with *

    for p_tag in soup.find_all('p'):
        if p_tag.string:  # Ensure there is text inside the tag
            p_tag.string = '\n' + p_tag.string + '\n'  # Wrap content with *

    # Now, get the plain text from the HTML (removes remaining HTML tags)
    text_content = soup.get_text(separator=' ', strip=True)

    # Fix unwanted characters (like non-breaking spaces) and extra spaces
    text_content = re.sub(r'\s+', ' ', text_content)  # Replace multiple spaces with a single space
    text_content = text_content.replace('\xa0', ' ')  # Remove non-breaking spaces

    return text_content
import requests
import json

def send_whatsapp_message_using_template(access_token, to, template_name, language_code="en_US"):
    url = "https://graph.facebook.com/v21.0/563853653467023/messages"

    # Define the headers for the request
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Define the payload (data to be sent)
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }

    # Convert the data dictionary to JSON
    json_data = json.dumps(data)

    # Send the POST request to the Facebook API
    response = requests.post(url, headers=headers, data=json_data)

    # Check if the request was successful
    if response.status_code == 200:
        print("Message sent successfully!")
        return response.json()  # Return the response as JSON
    else:
        print(f"Failed to send message. Status Code: {response.status_code}")
        print(response.text)  # Print the error message
        return None


from django.views.decorators.csrf import csrf_protect
@csrf_protect
@login_required
@client_access_required
@csrf_exempt  # You can use CSRF exemption for API-like views if needed
def send_email_view(request):
    if request.method == 'POST':
            print("in method")
            data = json.loads(request.body)
            userData=User.objects.filter(username=request.user.username,email=request.user.email).first()
            tenant=TenantModel.objects.filter(name=userData).first()
            template=TemplateModel.objects.filter(name=userData,templateName=data.get('templateName')).first()
            facebookData=FacebookCredentials.objects.filter(user=tenant).first()
            print(facebookData,data.get('userIds'),data)
            message = html_to_whatsapp_text(template.templateDescription)
            json_string=data.get('userIds')
            check=data.get('check')
            t_name=data.get('templateName')
            if t_name==None:
                t_name="welcome"
            if(check):
                for user_ in UserModels.objects.filter(tenant_to=tenant):
                    message_ = get_text_message_input(user_.phone,message)
                    conv=ConversationModel(user=user_,ai_model_reply="welcome message",user_query=data)
                    conv.save()
                    if "welcome" in t_name.lower():
                        data=create_template(user_.phone,"fixm8",user_.name,'fixm8')
                        send_welcome_temlate(data,facebookData)
                    else:
                        print("sent",message_,user_.name)
                        send_message_template_(message_,facebookData)
            else:

                for user in UserModels.objects.filter(tenant_to=tenant, id__in=data.get('userIds')):
                    message_ = get_text_message_input(user.phone,message)
                    conv=ConversationModel(user=user,ai_model_reply="welcome message",user_query=data)
                    conv.save()
                    if "welcome" in t_name.lower():
                        data=create_template(user.phone,"fixm8",user.name,'fixm8')
                        send_welcome_temlate(data,facebookData)
                    else:
                        print("sent",message_,user.name)
                        send_message_template_(message_,facebookData)

            return JsonResponse({'message': 'messages successfully!','success': True}, status=200)


    return JsonResponse({'error': 'Invalid request method'}, status=405)
from django.contrib.auth.models import User
@method_decorator(csrf_exempt, name='dispatch')
class AutoSaveView(View):
    def post(self, request):
        data = json.loads(request.body)
        print(data)
        email_description = data.get('emailDescription')
        print("email",email_description)
        tenant=User.objects.filter(username=request.user.username,email=request.user.email).first()
        print(tenant)
        k=data.get('templateName')
        o=k.split('emailDescription')[1]
        print(k.split('emailDescription'))
        user_=User.objects.filter(username=request.user.username,email=request.user.email).first()
        temp=TemplateModel.objects.filter(name=user_,templateName=o).first()
        print(temp)
        temp.templateDescription=email_description
        temp.save()
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
        print(login_user,TenantModel.objects.filter(name=login_user).first(),DashboardAccessProvidedByClientModel.objects.filter(user=login_user).first())
        if login_user is not None:
            # user_logout_view = UserLogoutView()
            # user_logout_view.dispatch(request)
            login(request, login_user)

            if request.user.is_superuser:
                return redirect("/adashboard")
            # if TenantModel.objects.filter()
            if  TenantModel.objects.filter(name=login_user).first():
                return redirect("/dashboard")
            if DashboardAccessProvidedByClientModel.objects.filter(user=login_user).first():
                print("user is authenticated")
                print("logging as the client who had provided the access")

                child_client = DashboardAccessProvidedByClientModel.objects.filter(user=login_user).first()
                get_user = child_client.access_provided_by.name
                # print("logging in as parent client",get_user,child_client.access_provided_by,get_user.name.username)
                # Authenticate the parent client
                print(get_user)
                    # Log the parent client in
                login(request, get_user)
    # Set a cookie
                response = redirect("/dashboard")
                response.set_cookie('client', 'child')  # Example cookie

                return response
        error_message = "Invalid username or password."
        return render(request, "accounts/login.html", {'error_message': error_message})

    return render(request, "accounts/login.html")

def update_customer(request, customer_id):
    customer = get_object_or_404(UserModels, id=customer_id)
    currentCustomer=get_object_or_404(UserModels, id=customer_id)
    currentTickets=TicketsModel.objects.filter(user=currentCustomer)
    currentTicketStatus=TicketsStatusModel.objects.filter(user=currentCustomer)
    currentConverstaion=ConversationModel.objects.filter(user=currentCustomer)
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address=request.POST.get("address")
        customer.name = name
        customer.email = email
        customer.phone = phone
        customer.address=address
        customer.save()
        for ticket in currentTickets:
            ticket.user=customer
            ticket.save()
        for ticketStatus in currentTicketStatus:
            ticketStatus.user=customer
            ticketStatus.save()
        for conversation in currentConverstaion:
            conversation.user=customer
            conversation.save()

        messages.success(request, 'Customer updated successfully!')
        return redirect('/customer/' + str(customer.id))

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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import os
def email(ticket,email_,path):

    # Hostinger's SMTP settings
    #
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # Use 465 for SSL, or 587 for TLS
    sender_email = "noreplyplease1230@gmail.com"  # Your Gmail address
    # receiver_email = "receiver-email@example.com"  # Recipient's email address
    password = "srohllfyyugpnuai"  # Use your Gmail App Password (if you have 2FA enabled)
    # Create the email message
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = email_
    message["Subject"] = "Ticket with number " + str(ticket['ticket_number'])+" was created "

    # Email body with an HTML table
    body = f"""
<html>
    <body>
        <h3>Hello, A user has reported an issue. You can get more details here:</h3>

        <table border="4" cellpadding="15" cellspacing="10">
            <tr>
                <td>Username</td>
                <td>{ticket['username']}</td>
            </tr>
            <tr>
                <td>Phone Number</td>
                <td>{ticket['phone']}</td>
            </tr>

            <tr>
                <td>Ticket Number</td>
                <td>{ticket['ticket_number']}</td>
            </tr>
            <tr>
                <td>Ticket Status</td>
                <td>{ticket['status']}</td>
            </tr>
        </table>

        <br>
        <hr>
        <b>Issue Description</b>
        <br>
        <p>Description: {ticket['des']}.</p>

        <br>

"""
    if path!="no path":
        body += f"""
            <p>Provided image:</p>
            <p><img src="cid:image1" alt="Issue Image" />  <!-- Referencing the image by its CID --></p>
        """
    else:
        body += "<p>No image provided.</p>"

    body += "</body></html>"

    # Attach the HTML body to the email message
    message.attach(MIMEText(body, "html"))
    if(path!="no path"):
        # Open and attach the image
        with open(path, 'rb') as img_file:
            img = MIMEImage(img_file.read())
            img.add_header('Content-ID', '<image1>')  # This matches the 'cid:image1' in the HTML body
            img.add_header('Content-Disposition', 'inline', filename=os.path.basename(path))
            message.attach(img)

    # Attach the HTML body to the email message
    message.attach(MIMEText(body, "html"))


    # Sending the email
    try:
        # Connect to the SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection with TLS
        print("started")
        # Log in to the server
        server.login(sender_email, password)
        print("logined")
        # Send the email
        server.sendmail(sender_email, email_, message.as_string())
        print("Email sent successfully!")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close the connection
        server.quit()
@login_required
def updateCredentials(request):
    action = 'credentials'
    user = TenantModel.objects.filter(name=request.user).first()
    data = FacebookCredentials.objects.filter(user=user).first()

    if request.method == "POST":
        form = Credentials(request.POST, instance=data)  # Bind the POST data to the form
        if form.is_valid():
            credentials = form.save(commit=False)
            credentials.user = user
            credentials.save()  # Save the updated credentials
            return redirect("/dashboard")
    else:
        form = Credentials(instance=data)  # Prepopulate the form with existing data

    context = {'action': action, 'form': form, 'data': data}
    return render(request, 'accounts/t.html', context)

def deleteUser(request,pk):
	user=UserModels.objects.get(id=pk)
	user.objects.delete()
	return redirect("/")

import google.generativeai as genai

genai.configure(api_key="AIzaSyDy3FHTLDFr_gUM74_RuVHoOSnF5BEC-No")

model = genai.GenerativeModel('gemini-1.5-flash-latest')

import google.generativeai as genai_

genai_.configure(api_key="AIzaSyA2gOgFJ5KU-XyzsMHhc71H3pEvalbeRzs")

model_ = genai_.GenerativeModel('gemini-1.5-flash-latest')

message_dict = {}



# Download necessary datasets for nltk
# nltk.download('wordnet')
# nltk.download('omw-1.4')

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
base_acknowledgment_words = [ "thanks"]
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
base_support_keywords = [  "raise", "raise a support request", "support", "assist", "trouble", "can't", "error", "help please",
    "raise a request", "request support", "help me", "assist me"]
SUPPORT_REQUEST_KEYWORDS = get_support_keywords(base_support_keywords)
media_dict=dict()
# Updated get_gemini_response function
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from email.mime.image import MIMEImage

import os
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from email.mime.image import MIMEImage

def save_image_to_ticket(path, ticket, image_format='PNG'):
    # Open the image in binary mode
    with open(path, 'rb') as img_file:
        img_data = img_file.read()

        # Use PIL to open the image and convert it to the desired format (PNG or JPEG)
        image = Image.open(BytesIO(img_data))

        # Ensure the image is in the desired format (e.g., PNG or JPEG)
        if image_format == 'PNG':
            output_image = BytesIO()
            image.save(output_image, format='PNG')
            output_image.seek(0)  # Reset pointer to the beginning of the file-like object
        elif image_format == 'JPEG':
            output_image = BytesIO()
            image.save(output_image, format='JPEG')
            output_image.seek(0)
        else:
            raise ValueError("Unsupported image format")

        # Prepare the file name and path
        image_name = f"{ticket.ticket_number}.{image_format.lower()}"  # Example: 'ticket123.png'
        image_path = os.path.join('uploads', image_name)  # Relative path to save the image

        # Save the image data to the Ticket model's image field (or path)
        ticket.image_path.save(image_name, ContentFile(output_image.read()), save=True)

        # Optional: If you are also attaching this image to an email
        img = MIMEImage(output_image.getvalue())
        img.add_header('Content-ID', f'<image{ticket.ticket_number}>')  # Matches 'cid:image1' in HTML body
        img.add_header('Content-Disposition', 'inline', filename=image_name)

        # Optional: Attach the image to your email message
        # message.attach(img)

    return ticket


def  get_gemini_response(input_message, recipient,caption, media=None):

    if is_acknowledgment(input_message):
        print("message",input_message,ACKNOWLEDGMENT_KEYWORDS)
        message_dict[recipient] = []
        return ACKNOWLEDGMENT_RESPONSE

    if(len(caption)):
        input_message=caption
    if recipient not in message_dict:
        message_dict[recipient] = []
        media_dict[recipient]='no path'
    # if (mes)
    print("input message",input_message)
    message_dict[recipient].append("User Query: "+input_message+"\n")

    # Check if the user is explicitly asking for support
    support_needed = check_support_needed(input_message)

    # Initialize support count if recipient is not already tracked
    if recipient not in support_count_dict:
        support_count_dict[recipient] = 0
    # if "raise" in input_message.lower():
    #     support_count_dict[recipient]+=5
    if support_needed:
        support_count_dict[recipient] += 1
    if support_count_dict[recipient] >= 4:  # Change the threshold to 1
        support_count_dict[recipient]=0
        full_input = " ".join(message_dict[recipient])
        message_dict[recipient] = []
        summary=model.generate_content('''proivde me a brief summary regarding the converstion what issue does the user is facing '''+full_input)
        # thread = threading.Thread(target=create_ticket_from_summary(summary.text,recipient,media_dict[recipient]))
        # thread.start()
        # media_dict[recipient]='no path'
        reslove_dict[recipient]="feedback"
        user_data_dict[recipient]=[summary.text,media_dict[recipient]]
        return send_message_interaction(recipient)

    full_input = " ".join(message_dict[recipient])

    if media:
        image = Image.open(media['file_path'])
        # image_media_dict[recipient]=media["media_file_path"]
        media_dict[recipient]=media['file_path']
        response = model.generate_content([full_input , image])
    response=model_.generate_content('''Analyzing Support Need :

***Objectives:
Analyze the provided response  and determine if it needs the additional phrase: "I can raise a request for support for an issue your facing if needed."
If the response already covers support or additional help, return the same text with no changes.
If the response lacks support information, add the phrase to the end of the response text if it is not a grreting or acknowledge message.

**If the ai model had not provided troubleshooting steps to troubleshoot the issue in the conversation for  3 times and user is reporting that issue is not fixed  act as a ai model and return the trouble shooting steps**,
** in the entire conversation provided if the model had provided troubleshooting steps for more 3 times and user reported that issue is not resloved and then only you should return "I've raised a request, and our support team will reach out to you soon." until and unless you analyse that the troubleshooting steps in the convefrsation provided is not more than 3 times provide the trouble shooting steps**
**If the  user asks provides about the issue he is facing try to analyse it and respond with troubleshooting steps and mention in the respone that i can provide some trouble shooting steps**
**If the  user respomds specifying issue is resloved then return "resloved"**
***

User Asking for Support Multiple Times:
**this the interaction between the user and the AI. The user's query is labeled as 'user query', and the AI's response is labeled as 'ai model response'. Ignore case sensitivity in the comparison.** If no AI model response is provided, assume the user has just initiated a conversation, and you act as a ai model and respond accordingly**. Carefully evaluate both strings and get an insightful analysis of the conversation and respond as as ai model to the user for further communication follow the objectives. The full conversation is as follows: "**
''' +  full_input )

    if((response.text =="I've raised a request, and our support team will reach out to you soon.") or  ("support team" in  response.text.lower())):
        full_input = " ".join(message_dict[recipient])

        summary=model_.generate_content('''proivde me a brief summary regarding the converstion what issue does the user is facing '''+full_input)
        message_dict[recipient]=[]

        thread = threading.Thread(target=create_ticket_from_summary(summary.text,recipient,media_dict[recipient]))
        thread.start()
        # media_dict[recipient]='no path'
        print("triggered a email")
        user_data_dict[recipient]=[summary.text,media_dict[recipient]]
        # reslove_dict[recipient]="issue"
        if recipient in message_dict:
            del message_dict[recipient]
        del support_count_dict[recipient]
        return
    # print("reslone",response.text,response.text=="resloved")
    if (response.text.strip().lower() == "resolved"):
        print("here")
        del message_dict[recipient]
        del support_count_dict[recipient]
        print("deleted")
        return "I am happy to hear that the issue is resloved feel free to reach out  to me if you are facing any issue"
    response=model.generate_content('''make the response to a short 100 words if response length exceeds by 120 words with same meaning and add the phrase i can raise a support request on your behalf to the response if you think it is needed to response and  the response is: '''+response.text)
    message_dict[recipient].append("AI model Response:  "+response.text+"\n")
    user=UserModels.objects.filter(phone=recipient).first()
    con=ConversationModel(user=user,ai_model_reply=response.text,user_query=input_message)
    con.save()
    return response.text

def create_ticket_from_summary(summary,phonenumber,path):
    print("path",path)
    user=UserModels.objects.filter(phone=phonenumber).first()
    global_ticket_number[0]=global_ticket_number[0]+1
    ticket_created=TicketsModel(user=user,ticket_number=str(global_ticket_number[0]),Description=summary)
    ticket_created.save()
    ticket_status=TicketsStatusModel(user=user,tenant_to=user.tenant_to,ticket_number=ticket_created,comments="Ticket created need to be assigned",description=summary,issue=user_issue_dict.get(phonenumber, "Not specified in chat") )
    if path.lower()!="no path":
        ticket_status=save_image_to_ticket(path,ticket_status)
    ticket_status.save()
    mail_body={'ticket_number':ticket_created.ticket_number,'des':ticket_created.Description,
               'phone':user.phone,'status':ticket_status.ticket_status,'username':user.name}
    print("triggering a email to client and tenant")

    userData=UserModels.objects.filter(phone=phonenumber).first()
    print(userData)
    name=User.objects.filter(username=userData.tenant_to).first()
    tenant=TenantModel.objects.filter(name=name).first()
    facebookData=FacebookCredentials.objects.filter(user=tenant).first()
    print(facebookData)
    text="A support ticket had been created with ticket id "+str(ticket_created.ticket_number)+" further info will be shared to your email and description of the ticket is as follow\n"+"\n"+str(ticket_status.description)
    data = get_text_message_input(phonenumber, text)
    user_intiated_chat[phonenumber]="create"
    del message_dict[phonenumber]
    send_message(data,facebookData)
    send_message_interaction_get_user_feedback(phonenumber,global_ticket_number[0])
    email(mail_body,user.email,path)
    email(mail_body,user.tenant_to.email,path)
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
            file_path  = save_media_file(media_content, media_type)
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
    deletion_thread = threading.Thread(target=delayed_file_deletion, args=(temp_file_path, 900))
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
    # print('body',body)
    message_data = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_id = message_data.get("id")
    receipient_number=message_data.get("from")
    user_intiated_chat[receipient_number]="received"
    userData=UserModels.objects.filter(phone=receipient_number).first()
    name=User.objects.filter(username=userData.tenant_to).first()
    tenant=TenantModel.objects.filter(name=name).first()
    facebookData=FacebookCredentials.objects.filter(user=tenant).first()
    # data_acknowledge=get_acknowledgment_keywords(["thanks"])
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    user=UserModels.objects.filter(phone=receipient_number).first()
    if user.archived:
        data = get_text_message_input(wa_id, "You dont have requried permission to access the model kindly check with your client")
        send_message(data,facebookData)
        return "No access granted"
    if message_data.get('interactive') and  (message_data.get('interactive').get('button_reply')!=None) and ("helpful" in message_data.get('interactive').get('button_reply').get('id').lower()):
                print(message_data.get('interactive').get('button_reply').get('id').lower(),message_data.get('interactive').get('button_reply').get('id'))

                ticket=message_data.get('interactive').get('button_reply').get('id').split(":")

                ticket_number=ticket[1]
                ticket_=TicketsModel.objects.filter(ticket_number=ticket_number).first()
                ticket_id=TicketsStatusModel.objects.filter(ticket_number=ticket_).first()
                ticket_id.feedback=ticket[0]
                ticket_id.save()
                print("updated the ticket feedback",ticket_id)
                data = get_text_message_input(wa_id, "Thanks For your feedback, we will try to improve based on this")
                send_message(data,facebookData)
                return
    if message_data.get('interactive') and message_data.get('interactive').get('button_reply')!=None  and ((message_data.get('interactive').get('button_reply').get('id')=="Resloved_team" or "No_team" in message_data.get('interactive').get('button_reply').get('id'))):
            selected_option_id = message_data['interactive']['button_reply']['id']
            if "No_team" in selected_option_id:
                print("triggering a mail to team")
                ticket=selected_option_id.split(":")
                ticketStatus=TicketsModel.objects.filter(ticket_number=ticket[1]).first()
                ticket_id=TicketsStatusModel.objects.filter(ticket_number=ticketStatus).first()
                ticket_id.ticket_status="INPROGRESS"
                ticket_id.save()
                data = get_text_message_input(receipient_number, "A mail is sent to the team reagrding the issue they will reach out to you Thanks")
                s=ConversationModel(user=userData,ai_model_reply="A mail is sent to the team reagrding the issue they will reach out to you Thanks",user_query="issue_persist")
                s.save()
                send_message(data,facebookData)
                mail_body={'ticket_number':ticket_id.ticket_number,'des':ticket_id.description,
               'phone':ticket_id.user.phone,'status':"we had marked the ticket as completed but the user reported that the issue is not resloved",'username':ticket_id.user.name}
                email(mail_body,ticket_id.tenant_to.email,"no path")
                return
            elif selected_option_id=="Resloved_team":
                if receipient_number in reslove_dict:
                    del reslove_dict[receipient_number]
                data = get_text_message_input(receipient_number, "I am happy to hear that the issue is resloved feel free to reach out  to me if you are facing any issue")
                s=ConversationModel(user=userData,ai_model_reply="I am happy to hear that the issue is resloved feel free to reach out  to me if you are facing any issue",user_query="resloved")
                s.save()
                send_message(data,facebookData)
                return
    if receipient_number not in message_dict:
        if message_data.get('interactive')and (message_data.get('interactive').get('list_reply')!=None):
            selected_option_id = message_data['interactive']['list_reply']['title']
            print("sele",selected_option_id)
            get_ticket=TicketsModel.objects.filter(ticket_number=selected_option_id)
            print("here",get_ticket)
            if get_ticket:
                status=send_ticket_status(get_ticket[0])
                data = get_text_message_input(wa_id, status)
                send_message(data,facebookData)
                send_message_interaction_check_user_request(receipient_number)
            else:

                issue_text="The user is facing " +selected_option_id
                user_issue_dict[receipient_number]=selected_option_id
                response = get_gemini_response(issue_text+"  "+"if needed ask him more info about the issue ask for image as well and provide trouble shooting steps" , wa_id,"",None)
                data = get_text_message_input(wa_id, response)
                send_message(data,facebookData)

        elif message_data.get('interactive') and (message_data.get('interactive').get('button_reply').get('id')=="m_issue"):
            start_sending_maintainence_issue_interaction(receipient_number)
        elif message_data.get('interactive') and (message_data.get('interactive').get('button_reply').get('id')=="not_required"):
            data = get_text_message_input(wa_id, "Feel free to reach out tome if you are facing any issue havea good day")
            send_message(data,facebookData)
        elif message_data.get('interactive') and (message_data.get('interactive').get('button_reply').get('id')=="request_current_stat"):
            data = get_text_message_input(wa_id, "I Had Notfied the team by sending a email they will get in touch with you soon feel free to reach out regarding any other issue you are facing")
            print("triggering email")
            send_message(data,facebookData)
        elif message_data.get('interactive') and (message_data.get('interactive').get('button_reply').get('id')=="e_status"):
             get_data_about_exiting_tickets(receipient_number)
        else:
            message_body = message_data.get("text", {}).get("body", "")
            if message_body in ACKNOWLEDGMENT_KEYWORDS:
                return ACKNOWLEDGMENT_RESPONSE
            else:
                start_sending_message_interaction(receipient_number)
    else:

        if message_data.get('interactive') and reslove_dict.get(receipient_number)=='feedback':
            selected_option_id = message_data['interactive']['button_reply']['id']
            if selected_option_id=="No_":
                # reslove_dict[receipient_number]="issue"
                data=user_data_dict[receipient_number]
                create_ticket_from_summary(data[0],receipient_number,data[1])
                del user_data_dict[receipient_number]
            elif selected_option_id=="Resloved_":

                del reslove_dict[receipient_number]
                data = get_text_message_input(receipient_number, "I am happy to hear that the issue is resloved feel free to reach out  to me if you are facing any issue")
                send_message(data,facebookData)
        elif receipient_number not in reslove_dict:
                wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
                if message_id in processed_messages:
                    print(f"Message {message_id} already processed.")
                    return
                processed_messages.add(message_id)
                media = None
                caption=""
                if "image" in message_data:
                    media_id = message_data["image"]["id"]
                    if message_data["image"].get("caption"):
                        caption = message_data["image"]["caption"]
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
            # send_message_interaction(receipient_number)
    # else:
    #     message_body = message_data.get("text", {}).get("body", "")
    #     data = get_text_message_input(receipient_number, "A ticket is created on your behalf for the issue you had reported previously our team will reach out to you please let them know if your facing any other issues as well")
    #     s=ConversationModel(user=userData,ai_model_reply="A ticket is created on your behalf for the issue you had reported previously our team will reach out to you please let them know if your facing any other issues as well",user_query=message_body)
    #     s.save()
    #     send_message(data,facebookData)
    #     # Function to send messages via WhatsApp
def send_message(data,facebookData):
            data_dict = json.loads(data)
            print(user_intiated_chat,data_dict["to"])
            if user_intiated_chat[data_dict["to"]]=="received" or user_intiated_chat[data_dict["to"]]=="create":
                print("received call for particular user")
                url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
                headers = {
                    "Authorization": "Bearer " + facebookData.accessToken,
                    "Content-Type": "application/json",
                }
                print(url,data)
                user_intiated_chat[data_dict["to"]]="sent"
                response = requests.post(url, headers=headers, data=data)
                print("sejnfj",response,response.text)
                return response
            return None
import requests
import json

def send_message_template_(data, facebookData):
    print("Received call for particular user",data)

    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"

    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

    # Check the 'data' format to ensure it matches the expected API format
    try:
        # Log the outgoing data
        print("Sending data:", json.dumps(data, indent=4))

        # Sending the request
        if isinstance(data, str):
    # If it's a string, parse it into a dictionary
            data = json.loads(data)

        # Now that 'data' is a dictionary, you can safely modify the 'to' field
        data["to"] = "+" + str(data["to"])
        response = requests.post(url, headers=headers, data=json.dumps(data))

        # Check for the actual response from Facebook API
        if response.status_code == 200:
            print("Response OK:", response.json())
        else:
            print("Response Error:", response.status_code, response.text)

        return response
    except Exception as e:
        print("Error sending message:", e)
        return None

            # return None
def create_template(number, name, user, company):
    # Validate that template name is provided
    if not name:
        raise ValueError("Template name is required")

    # Validate that user and company are provided
    if not user or not company:
        raise ValueError("Both 'user' and 'company' parameters are required")

    # Construct the API payload with correct template structure
    data = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "template",
        "template": {
            "name": name,  # Template name, make sure this matches the registered template name
            "language": {
                "code": "en"  # The language code of your template (e.g., en_US, es_ES)
            },
            "components": [
                {
                    "type": "BODY",
                    "parameters": [
                        {"type": "text", "parameter_name": "user",   "text": user},  # Parameter for {{user}}
                        {"type": "text",  "parameter_name": "company",  "text": company}  # Parameter for {{company}}
                    ]
                }
            ]
        }
    }

    return data

def send_welcome_temlate(data,facebookData):

    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"

    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }
    # Send POST request to the WhatsApp API
    response = requests.post(url, headers=headers, data=json.dumps(data))

    # Check the response status
    if response.status_code == 200:
        print("Template sent successfully!")
        print(response.json())  # Print the response from the API
    else:
        print(f"Error: {response.status_code}")
        print(response.json())  # Print the error message

def send_message_interaction(receipient_number):
    userData=UserModels.objects.filter(phone=receipient_number).first()
    print(userData)
    name=User.objects.filter(username=userData.tenant_to).first()
    tenant=TenantModel.objects.filter(name=name).first()
    facebookData=FacebookCredentials.objects.filter(user=tenant).first()
    print(facebookData)
    options = {
    'header': 'Did The Conversation Helped In Resloving The Issue',
    'button': 'Options',
    'section_title': 'Menu',
    'rows': [
        {'id': 'Resloved_', 'title': 'Issue Resloved'},
        {'id': 'No_', 'title': 'Request Support'},
    ]
}
    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

    data = {
    "messaging_product": "whatsapp",
    "to": receipient_number,
    "type": "interactive",
    "interactive": {
        "type": "button",
        "header": {
            "type": "text",
            "text": options['header']
        },
         "body": {  # Adding the body
            "text": 'Select the button to move forward'  # Ensure 'body' is a key in options
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": opt['id'],
                        "title": opt['title']
                    }
                } for opt in options['rows']  # Adjust the rows to fit button format
            ]
        }
    }
}


    # Send the request
    # con=ConversationModel(user=userData,ai_model_reply="template",user_query="button")
    # con.save()
    response = requests.post(url, headers=headers, json=data)

    # Handle response

    # response.raise_for_status()  # Raises an HTTPError for bad responses
    # return response.text # Return the JSON response if successful
def send_message_interaction_check_user_request(receipient_number):
    userData=UserModels.objects.filter(phone=receipient_number).first()
    print(userData)
    name=User.objects.filter(username=userData.tenant_to).first()
    tenant=TenantModel.objects.filter(name=name).first()
    facebookData=FacebookCredentials.objects.filter(user=tenant).first()
    print(facebookData)
    options = {
    'header': '',
    'button': 'Options',
    'section_title': 'Menu',
    'rows': [
        {'id': 'request_current_stat', 'title': 'Request Current Stat'},
        {'id': 'not_required', 'title': 'Not Required'},
    ]
}
    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

    data = {
    "messaging_product": "whatsapp",
    "to": receipient_number,
    "type": "interactive",
    "interactive": {
        "type": "button",
        "header": {
            "type": "text",
            "text": options['header']
        },
         "body": {  # Adding the body
            "text": 'Do you Want To Raise a Request For The Current Status Of Ticket'  # Ensure 'body' is a key in options
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": opt['id'],
                        "title": opt['title']
                    }
                } for opt in options['rows']  # Adjust the rows to fit button format
            ]
        }
    }
}


    # Send the request
    # con=ConversationModel(user=userData,ai_model_reply="template",user_query="button")
    # con.save()
    response = requests.post(url, headers=headers, json=data)

    # Handle response

    # response.raise_for_status()  # Raises an HTTPError for bad responses
    return response.text # Return the JSON response if successful
def send_message_interaction_get_user_feedback(receipient_number,number):
    userData=UserModels.objects.filter(phone=receipient_number).first()
    print(userData)
    name=User.objects.filter(username=userData.tenant_to).first()
    tenant=TenantModel.objects.filter(name=name).first()
    facebookData=FacebookCredentials.objects.filter(user=tenant).first()
    print(facebookData)
    options = {
    'header': '',
    'button': 'Options',
    'section_title': 'Menu',
    'rows': [
        {'id': 'Helpful :'+str(number), 'title': 'Helpful'},
        {'id': 'Not Helpful :'+str(number), 'title': 'Not Helpful'},
    ]
}
    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

    data = {
    "messaging_product": "whatsapp",
    "to": receipient_number,
    "type": "interactive",
    "interactive": {
        "type": "button",
        "header": {
            "type": "text",
            "text": options['header']
        },
         "body": {  # Adding the body
            "text": 'Do the conversation and ticket raised are helpful to you. please provide feedback to us for improvization'  # Ensure 'body' is a key in options
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": opt['id'],
                        "title": opt['title']
                    }
                } for opt in options['rows']  # Adjust the rows to fit button format
            ]
        }
    }
}


    # Send the request
    # con=ConversationModel(user=userData,ai_model_reply="template",user_query="button")
    # con.save()
    response = requests.post(url, headers=headers, json=data)

    # Handle response

    # response.raise_for_status()  # Raises an HTTPError for bad responses
    return response.text # Return the JSON response if successful
import requests
def start_sending_message_interaction(receipient_number):
    print("sending interaction", receipient_number)
    userData = UserModels.objects.filter(phone=receipient_number).first()

    name = User.objects.filter(username=userData.tenant_to).first()
    tenant = TenantModel.objects.filter(name=name).first()
    facebookData = FacebookCredentials.objects.filter(user=tenant).first()

    # Welcome message content
    welcome_text = "Hi there! 👋 Welcome to"+ " "+userData.tenant_to.name.username+ " 's  property maintenance assistant. I'm here to help you with any issues in your property. To get started, please choose a main category from the menu below:"

    options = {
        'header': " ",
        'section_title': "Choose a Category",
        'rows': [
            {'id': 'm_issue', 'title': '⬅️ Report An Issue'},  # Added back arrow
            {'id': 'e_status', 'title': '✅ Check Existing Ticket'},  # Added checkmark emoji
        ]
    }

    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": receipient_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "text",
                "text": options['header']
            },
            "body": {
                "text": welcome_text
            },
            "footer": {
                "text": "Main Menu"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "m_issue",
                            "title": "⬅️ Report An Issue"  # Back arrow here
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "e_status",
                            "title": "✅ Check Existing"  # Checkmark emoji
                        }
                    }
                ]
            }
        }
    }

    # Save the conversation model
    # con = ConversationModel(user=userData, ai_model_reply="template", user_query="card")
    # con.save()

    # Send the request
    response = requests.post(url, headers=headers, json=data)
    print(response, response.text)
    return response.json()


import requests

def start_sending_maintainence_issue_interaction(receipient_number):
    print("sending interaction menu ", receipient_number)
    userData = UserModels.objects.filter(phone=receipient_number).first()

    name = User.objects.filter(username=userData.tenant_to).first()
    tenant = TenantModel.objects.filter(name=name).first()
    facebookData = FacebookCredentials.objects.filter(user=tenant).first()
    row=[]
    chatOption=ChatOptionsToTenant.objects.filter(user=name)
    # Prepare the options for the list
    for chat in chatOption:
        temp={}
        temp['id']=chat.options
        temp['title']=chat.options
        row.append(temp)
    options = {
        'header': " ",
        'section_title': 'Menu',
        'rows': row
    }

    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

    # Construct the data for the list message
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": receipient_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": options['header']
            },
            "body": {
                "text": "Thanks! Please select the type of issue you’re facing from the list below:"
            },
            "footer": {
                "text": "Sub-Menu for Maintenance Issues:"  # Footer text
            },
            "action": {
                "button": "Select The Issue",  # **THIS IS THE REQUIRED BUTTON LABEL**
                "sections": [
                    {
                        "title": options['section_title'],
                        "rows": [
                            {"id": opt['id'], "title": opt['title'], "description": " "} for opt in options['rows']
                        ]
                    }
                ]
            }
        }
    }

    # Save the conversation model
    # con = ConversationModel(user=userData, ai_model_reply="template", user_query="list")
    # con.save()

    # Send the request
    response = requests.post(url, headers=headers, json=data)
    print(response, response.text)
    return response.json()

def get_data_about_exiting_tickets(receipient_number):
    print('in getiing data')
    userData = UserModels.objects.filter(phone=receipient_number).first()
    name = User.objects.filter(username=userData.tenant_to).first()
    tenant = TenantModel.objects.filter(name=name).first()
    facebookData = FacebookCredentials.objects.filter(user=tenant).first()
    user_instance = UserModels.objects.get(id=userData.id)
    tickets = TicketsStatusModel.objects.filter(user=user_instance).order_by('-date_reported')[:10]

    row=[]
    for ticket in tickets:
        temp={}
        temp["id"]=str(ticket.ticket_number)
        temp["title"]=str(ticket.ticket_number)
        row.append(temp)
    if len(row)>0:
        options = {
            'header': " ",
            'section_title': 'Menu',
            'rows': row
        }

        url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
        headers = {
            "Authorization": "Bearer " + facebookData.accessToken,
            "Content-Type": "application/json",
        }

        # Construct the data for the list message
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": receipient_number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": options['header']
                },
                "body": {
                    "text": " List Of Tickets Raised By"+" "+userData.name
                },
                "footer": {
                    "text": "Tap below to choose an ticket to get info about"  # Footer text
                },
                "action": {
                    "button": "Select Ticket",  # **THIS IS THE REQUIRED BUTTON LABEL**
                    "sections": [
                        {
                            "title": options['section_title'],
                            "rows": [
                                {"id": opt['id'], "title": opt['title'], "description": " "} for opt in options['rows']
                            ]
                        }
                    ]
                }
            }
        }
        response = requests.post(url, headers=headers, json=data)
        print(response,response.text,response.json())
        return response.json()
    else:
        data=get_text_message_input(receipient_number,"No tickets were raised on your behalf if ypur facing any issue you can raise a support ticket")
        send_whatsapp_message(data,facebookData)
def send_ticket_status(ticketNumber):
    ticket=TicketsStatusModel.objects.get(ticket_number=ticketNumber)
    temp="Hi User"+"\n"+"The Ticket Number you choosed is "+ " "+str(ticket.ticket_number)+"\n"+"The status of the ticket is "+" "+str(ticket.ticket_status)+"\n"+" "+"The comments are"+str(ticket.commentHistory)
    return temp

def send_message_interaction_by_team(receipient_number,ticket_number):
    print("here i n interatcion by team",receipient_number)
    userData=UserModels.objects.filter(phone=receipient_number).first()
    name=User.objects.filter(username=userData.tenant_to).first()
    tenant=TenantModel.objects.filter(name=name).first()
    facebookData=FacebookCredentials.objects.filter(user=tenant).first()

    options = {
    'header': 'Our team has closed your ticket. Please confirm if resolved',
    'button': 'Options',
    'section_title': 'Menu',
    'rows': [
        {'id': 'Resloved_team', 'title': 'Yes , Issue resloved'},
        {'id': 'No_team :'+str(ticket_number), 'title': 'No, need support'},
    ]
}
    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

    data = {
    "messaging_product": "whatsapp",
    "to": receipient_number,
    "type": "interactive",
    "interactive": {
        "type": "button",
        "header": {
            "type": "text",
            "text": options['header']
        },
         "body": {  # Adding the body
            "text": 'Select the button to move forward'  # Ensure 'body' is a key in options
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": opt['id'],
                        "title": opt['title']
                    }
                } for opt in options['rows']  # Adjust the rows to fit button format
            ]
        }
    }
}

    # con=ConversationModel(user=userData,ai_model_reply="template",user_query="button")
    # con.save()
    # Send the request
    response = requests.post(url, headers=headers, json=data)
    print(response,response.text,response.json())
    return response.json()

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
    print("inloop",request.method)
    if request.method == 'POST':
        print("here")


        handle_message(request)
        return JsonResponse({'status': 'Message sent successfully'}, status=200)
    elif request.method == 'GET':
        print("received response")
        return verify(request)
        # return JsonResponse({'status': 'Verification successful'}, status=200)

    # return JsonResponse({'error': 'Invalid request method'}, status=400)

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

        data = json.loads(request.body)  # Parse the JSON body
        email = data.get('email')  # Get the email from the parsed data
        user_=User.objects.filter(email=email).first()
        print(email,user_)
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
        return JsonResponse({'success': True, 'message': 'Tenant updated successfully!'})

    return JsonResponse({'error': 'Invalid request method'}, status=400)


# Delete tenant
@superuser_required
@csrf_exempt
def delete_tenant(request, tenant_id):
    print(request)
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

@csrf_exempt
def create_user_tenant_(request):
    print("yed",request,request.method)
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        address=request.POST.get("address")
        print(name,email,phone,address)
        user=User.objects.filter(username=request.user.username,email=request.user.email).first()
        print(user)
        tenant =TenantModel.objects.filter(name=user).first()
        print(tenant)
        facebookData=FacebookCredentials.objects.filter(user=tenant).first()

        data=create_template(phone,"fixm8",name,'fixm8')
        user = UserModels.objects.create(name=name, phone=phone, email=email, tenant_to=tenant,address=address)
        user.save()
        send_welcome_temlate(data,facebookData)
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
@login_required

@csrf_exempt  # Only if you aren't using CSRF tokens; otherwise, ensure it's handled correctly.
def delete_user(request, user_id):
    if request.method == 'DELETE':
        try:
            # Load the JSON body
            data = json.loads(request.body)
            print(data)
            ids = data.get('ids', [])
            print(data)
            # Delete users based on the provided IDs
            UserModels.objects.filter(id__in=ids).delete()  # Assuming UserModels is your user model

            return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)


# Create a new ticket
@login_required
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
def delete_facebook_credentials(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ids = data.get('ids', [])
            # Delete credentials with the given IDs
            FacebookCredentials.objects.filter(id__in=ids).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def ticket_status_list(request):
    user=User.objects.filter(username=request.user.username,email=request.user.email)
    tenants = TenantModel.objects.filter(name=user.first())
    tickets = TicketsStatusModel.objects.filter(tenant_to=tenants.first())
    users = UserModels.objects.filter(tenant_to=tenants.first())
    ticket_numbers = TicketsModel.objects.filter(user__tenant_to=tenants.first())
    assignes=AssigneModel.objects.filter(client=tenants.first())
    print(ticket_numbers)
    issues=IssueModel.objects.all()
    print(issues)
    return render(request, 'accounts/m.html', {
        'tickets': tickets,
        'users': users,
        'tenants': tenants,
        'ticket_numbers': ticket_numbers,
        'issues':issues,
        "assignes":assignes
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

@login_required
@csrf_exempt
def update_ticket_status(request):
    print("int his ",request.method)
    if request.method == 'POST':
        print("in post")
        ticket_id = request.POST.get('id')

        print(ticket_id)
        ticket = get_object_or_404(TicketsStatusModel, id=ticket_id)
        userData=UserModels.objects.filter(phone=ticket.user.phone).first()
        print(userData)
        name=User.objects.filter(username=userData.tenant_to).first()
        tenant=TenantModel.objects.filter(name=name).first()
        history=ticket.commentHistory+"\n"+"Ticket status is: "+request.POST.get('ticket_status')+"\n"+"comments :"+request.POST.get('comments')+"\n"+"updated at: "+str(datetime.now())+"\n"+"   "+"\n"
        ticket.issue=request.POST.get('issue')
        ticket.assigne=AssigneModel.objects.filter(name=request.POST.get("assigne"),client=tenant).first()
        ticket.commentHistory=history
        ticket.user=userData
        ticket.tenant_to=tenant
        ticket.comments=request.POST.get('comments')
        ticket.ticket_status=request.POST.get('ticket_status') #updated
        ticket.save()
        facebookData=FacebookCredentials.objects.filter(user=tenant).first()
        print(facebookData)
        data = get_text_message_input(ticket.user.phone, "The Ticket with id  "+str(ticket.ticket_number)+" had been updated by our team you can track the status here      "+ticket.commentHistory)
        user_intiated_chat[ticket.user.phone]="create"
        send_message(data,facebookData)
        if request.POST.get('ticket_status')=="COMPLETED":
            send_message_interaction_by_team(ticket.user.phone,ticket.ticket_number)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid data'})
@login_required
@csrf_exempt
def delete_ticket_status(request, ticket_id):
    if request.method == 'DELETE':
        ticket = get_object_or_404(TicketsStatusModel, id=ticket_id)
        ticket.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@csrf_exempt
def delete_ticket_status_tenant(request):
    if request.method == 'POST':
        try:
            # Load the JSON data from the request body
            data = json.loads(request.body)
            ticket_ids = data.get('ids', [])

            # Ensure ticket_ids is a list
            if isinstance(ticket_ids, list):
                # Delete all tickets with the provided IDs
                TicketsStatusModel.objects.filter(id__in=ticket_ids).delete()
                return JsonResponse({'success': True, 'deleted_count': len(ticket_ids)})

            return JsonResponse({'success': False, 'error': 'Invalid ticket IDs format'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

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

@login_required
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
@login_required
@csrf_exempt
def delete_ticket(request):
    if request.method == 'DELETE':
        try:
            data = json.loads(request.body)  # Parse the JSON body
            ticket_ids = data.get('ids', [])  # Get the list of ticket IDs

            if not ticket_ids:
                return JsonResponse({'success': False, 'error': 'No ticket IDs provided'})

            # Delete tickets with the provided IDs
            TicketsModel.objects.filter(id__in=ticket_ids).delete()

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

from django.shortcuts import render
from .models import TicketsModel, UserModels
@login_required
def list_tickets(request):
    user=User.objects.filter(username=request.user.username,email=request.user.email).first()
    tenant=TenantModel.objects.filter(name=user).first()
    tickets = TicketsModel.objects.filter(user__tenant_to=tenant)
    users = UserModels.objects.filter(tenant_to=tenant) # Assuming this is where your users come from
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
    conversations = ConversationModel.objects.all()

# Get distinct years and months
    years = list(set(conversation.date_queried.year for conversation in conversations if conversation.date_queried))
    months = list(set(conversation.date_queried.month for conversation in conversations if conversation.date_queried))
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
    user_to_tenant_ids = {tenant.name.id: tenant.id for tenant in TenantModel.objects.all()}
    user_to_tenant_email = {tenant.id: tenant.email for tenant in User.objects.all()}

    return render(request, 'accounts/u.html', {
        'users': users,
        'user_to_tenant_ids': user_to_tenant_ids,
        'user_to_tenant_email':user_to_tenant_email
    })

@csrf_exempt
def client_dashboard_access(request):
    user_logged_in=User.objects.filter(username=request.user,email=request.user.email).first()
    check_user_dashboard_access=DashboardAccessProvidedByClientModel.objects.filter(user=user_logged_in).first()
    if(check_user_dashboard_access):
        tenant=check_user_dashboard_access.access_provided_by
    else:
        tenant=TenantModel.objects.filter(name=user_logged_in,email=request.user.email).first()
    users = DashboardAccessProvidedByClientModel.objects.filter(access_provided_by=tenant)
    # user_to_tenant_ids = {tenant.name.id: tenant.id for tenant in TenantModel.objects.all()}
    # user_to_tenant_email = {tenant.id: tenant.email for tenant in User.objects.all()}

    return render(request, 'accounts/cleint_access_provided.html', {
        'users': users,
        # 'user_to_tenant_ids': user_to_tenant_ids,
        # 'user_to_tenant_email':user_to_tenant_email
    })
# Create a user
@csrf_exempt
def create_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        is_superuser = request.POST.get('is_superuser') == 'true'
        password=request.POST.get('password')
        is_tenant=request.POST.get('is_tenant') =='true'
        user = User.objects.create(username=username, email=email, is_superuser=is_superuser)
        user.set_password(password)
        print(user,password)
        user.save()
        if(is_tenant):
            make_tenant=TenantModel(name=user,email=email,email_template='hello')
            make_tenant.save()
            home_directory_link = request.build_absolute_uri('/')
            send_onbarding_mail(username,email,home_directory_link)
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
        password=request.POST.get('password')
        if password!="" or password!=None or password!=" ":
            print(password)
            user.set_password(password)
        user.save()
        tenant_update=TenantModel.objects.filter(name=user).first()
        print(tenant_update)
        print(user,password)
        user.username = username
        user.email = email
        user.is_superuser = is_superuser
        user.save()
        if tenant_update!=None:
            tenant_update.name=user
            tenant_update.email=email
            tenant_update.save()


        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

# Delete user
@csrf_exempt
def delete_user_(request):
    print("here in thsi")
    if request.method == 'DELETE':
        try:
            body = json.loads(request.body)  # Load the JSON body
            print("body",request.body,body)
            user_ids = body.get('ids', [])  # Get a list of user IDs from the body
            print(user_ids)
            deleted_count = 0
            for user_id in user_ids:
                print(user_id)  # Debugging: print the user ID being processed
                try:
                    user = get_object_or_404(User, id=user_id)  # Get the user
                    print(user)  # Debugging: print the user object
                    user.delete()  # Delete the user
                    deleted_count += 1
                except User.DoesNotExist:
                    continue  # If user does not exist, continue with the next ID

            return JsonResponse({'success': True, 'deleted_count': deleted_count})
        except (ValueError, json.JSONDecodeError):
            return JsonResponse({'success': False, 'error': 'Invalid request body.'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import UserModels
from django.views.decorators.csrf import csrf_exempt

def user_list(request):
    tenant =User.objects.filter(username=request.user.username,email=request.user.email).first()  # Get the tenant object
    tenant_=TenantModel.objects.filter(name=tenant).first()
    users = UserModels.objects.filter(tenant_to=tenant_)
    active_users = users.filter(id__in=users.values('id'), archived=False)
    archived_users = users.filter(id__in=users.values('id'), archived=True)
    return render(request, 'accounts/utenant.html', {'users': users,'active_users':active_users, 'archived_users':archived_users,"a_user_length":len(archived_users)})

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
from django.views.decorators.http import require_POST
@csrf_exempt
def delete_user_tenant(request, user_id):
    if request.method == 'DELETE':
        user = UserModels.objects.get(id=user_id)
        user.delete()
        return JsonResponse({'success': True})
@login_required
@client_access_required
def add_template(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        # Access the templateName and templateContent
        template_name = body_data.get('templateName')
        template_content = body_data.get('templateContent')
        # You can now use template_name and template_content as needed
        print(f'Template Name: {template_name}')
        print(f'Template Content: {template_content}')
        tenant =User.objects.filter(username=request.user.username,email=request.user.email).first()  # Get the tenant object
        # Create a new template object and save it
        new_template = TemplateModel(name=tenant,templateName=template_name, templateDescription=template_content)
        new_template.save()
        print("template saved")

        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import json

@csrf_exempt  # Only use this for testing purposes; CSRF protection should be enabled in production
def save_template(request):
    if request.method == 'POST':
        try:
            # Get the JSON data from the request
            data = json.loads(request.body)

            template_name = data.get('templateName')
            temp=template_name.split(" ")
            template_name="_".join(temp)
            template_content = data.get('templateContent')

            if not template_name or not template_content:
                return JsonResponse({'error': 'Both fields are required'}, status=400)

            # Save the template to the database
            tenant =User.objects.filter(username=request.user.username,email=request.user.email).first()  # Get the tenant object
            new_template = TemplateModel(name=tenant,templateName=template_name, templateDescription=template_content)
            new_template.save()
            # Return a success response
            print("saved")
            return JsonResponse({'message': 'Template saved successfully!'}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)
def check_template_name(request):
    if request.method == "GET":
        template_name = request.GET.get('templateName', '').strip()
        tenant =User.objects.filter(username=request.user.username,email=request.user.email).first()
        # Check if the template name already exists in the database
        if TemplateModel.objects.filter(name=tenant,templateName=template_name).exists():
            return JsonResponse({'exists': True}, status=400)  # Template name exists
        return JsonResponse({'exists': False}, status=200)
from django.http import JsonResponse, HttpResponseNotAllowed
@login_required
def delete_template(request, template_name):

    if request.method == "DELETE":
        # Get the template by name
        tenant =User.objects.filter(username=request.user.username,email=request.user.email).first()
        template = get_object_or_404(TemplateModel, templateName=template_name,name=tenant)

        # Delete the template
        template.delete()

        return JsonResponse({'success': True}, status=200)

    # If method is not DELETE, return an error
    return HttpResponseNotAllowed(['DELETE'])

from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render
from django.http import JsonResponse
from .forms import UserProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render
from django.http import JsonResponse
from .forms import UserProfileForm

@login_required
def update_user_profile(request):
    if request.method == "POST" :
        # Initialize the form with the POST data and the current user's data
        form = UserProfileForm(request.POST, instance=request.user)

        if form.is_valid():
            # Save profile fields (first name, last name, email)
            user = form.save()
            username=form.cleaned_data.get('username')
            email=form.cleaned_data.get('email')
            new_password = form.cleaned_data.get('new_password')
            print(username,email,new_password)
            if username!=request.user.username  or email!=request.user.email:
                currentUser=User.objects.filter(username=request.user.username,email=request.user.email).first()
                updatedUser=User.objects.filter(username=request.user.username,email=request.user.email).first()
                updatedUser.username=username
                updatedUser.email=email
                updatedUser.save()
                currentTemplatedata=TemplateModel.objects.filter(user=currentUser)
                currentDashboardClient=DashboardAccessProvidedByClientModel.objects.filter(access_provided_by=currentUser)
                currentTenantData=TenantModel.objects.filter(name=currentUser).first()
                currentUsersDataToTenant=UserModels.objects.filter(tenant_to=currentTenantData)
                currentTicketsStatusData=TicketsStatusModel.objects.filter(tenant_to=currentTenantData)
                currentFacebookData=FacebookCredentials.objects.filter(user=currentTenantData)
                updatedTenantData=TenantModel.objects.filter(name=currentUser).first()
                updatedTenantData.name=updatedUser
                updatedTenantData.save()
                for template in currentTemplatedata:
                    template.user=updatedUser
                    template.save()
                for userData in currentUsersDataToTenant:
                    userData.tenant_to=updatedTenantData
                    userData.save()
                for ticket in currentTicketsStatusData:
                    ticket.tenant_to=updatedTenantData
                    ticket.save()
                for access in currentDashboardClient:
                    access.access_provided_by=updatedUser
                    access.save()
                currentFacebookData.user=updatedTenantData
                currentFacebookData.save()
            if new_password:
                current_password = form.cleaned_data.get('current_password')

                # Validate the current password
                if not request.user.check_password(current_password):
                    return JsonResponse({'status': 'error', 'message': 'Current password is incorrect.'})

                # Set the new password

                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)  # Keep the user logged in after password change

            return JsonResponse({'status': 'success', 'message': 'Profile updated successfully!'})

        return JsonResponse({'status': 'error', 'message': form.errors})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import DashboardAccessProvidedByClientModel
import json

@csrf_exempt
def create_access(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_id = data.get('user')
        access_provided_by_id = data.get('access_provided_by')
        access = DashboardAccessProvidedByClientModel.objects.create(
            user_id=user_id,
            access_provided_by_id=access_provided_by_id
        )
        return JsonResponse({'success': True, 'id': access.id})

@csrf_exempt
def get_access(request):
    access_id = request.GET.get('id')
    access = DashboardAccessProvidedByClientModel.objects.get(id=access_id)
    return JsonResponse({
        'id': access.id,
        'user': {'id': access.user.id, 'username': access.user.username},
        'access_provided_by': {'id': access.access_provided_by.id, 'name': access.access_provided_by.name}
    })

@csrf_exempt
def update_access(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        access_id = data.get('id')
        user_id = data.get('user')
        access_provided_by_id = data.get('access_provided_by')
        access = DashboardAccessProvidedByClientModel.objects.get(id=access_id)
        access.user_id = user_id
        access.access_provided_by_id = access_provided_by_id
        access.save()
        return JsonResponse({'success': True})

@csrf_exempt
def delete_access(request):
    if request.method == 'DELETE':
        data = json.loads(request.body)
        access_id = data.get('id')
        access = DashboardAccessProvidedByClientModel.objects.get(id=access_id)
        access.delete()
        return JsonResponse({'success': True})
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

def get_user_data(request):
        usernames = list(User.objects.values_list('username', flat=True))  # Get all existing usernames
        return JsonResponse({'usernames': usernames})
@method_decorator(csrf_exempt, name='dispatch')
class DashboardAccessView( View):
    def get(self, request):
        # Filter entries where access_provided_by is the current user
        user=User.objects.filter(username=request.user.username,email=request.user.email).first()
        tenant=TenantModel.objects.filter(name=user,email=request.user.email).first()
        entries = DashboardAccessProvidedByClientModel.objects.filter(access_provided_by=tenant).select_related('access_provided_by')
        data = []
        total_users_=User.objects.all()
        total_user=[]
        for user_ in total_users_:
            total_user.append(user_.username)

        for entry in entries:
            user_data = {
                'id': entry.user.id,
                'username': entry.user.username,
                'email': entry.user.email,  # Include email if needed
            }

            data.append({
                'user': user_data,

            })

        return JsonResponse({'entries': data,'user_name_check':total_user})

    @csrf_exempt
    def post(self, request):
        body = json.loads(request.body)
        user= body.get('user_id')
        password = body.get('password')
        email=body.get('email')
        print("here iurehtwkjrhjds")
        user_=User(username=user,email=email)
        user_.set_password(password)
        user_.save()
        user=User.objects.filter(username=request.user.username,email=request.user.email).first()
        tenant=TenantModel.objects.filter(name=user,email=request.user.email).first()
        create_client=DashboardAccessProvidedByClientModel(user=user_,access_provided_by=tenant)
        create_client.save()
        print("triggering a email to created client")
        # Create a new entry with the provided user and the logged-in user as access provided by

        return JsonResponse({'success': True,'id': "2"})

    @csrf_exempt
    def delete(self, request):
        body = json.loads(request.body)
        ids = body.get('ids', [])
        if not ids:
            return JsonResponse({'success': False, 'error': 'No IDs provided.'}, status=400)

        # Delete users with the provided IDs
        User.objects.filter(id__in=ids).delete()
        return JsonResponse({'success': True})

@csrf_exempt
def archive_user(request):

    data = json.loads(request.body)
    user_id=data.get('userId')
    archived=data.get('archived')
    user=UserModels.objects.filter(id=user_id).first()
    if user:
        user.archived=archived
        user.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'User not found.'}, status=404)

class DashboardAccessUpdateView(View):
    @csrf_exempt
    def post(self,request,entry_id):
        body = json.loads(request.body)
        print(body)

        # Fetch the user based on entry_id
        user = User.objects.filter(id=entry_id).first()  # Use .first() to avoid multiple results

        if not user:
            return JsonResponse({'success': False, 'error': 'User not found.'}, status=404)

        # Update user fields
        user.username = body.get("user", user.username)  # Default to current username if not provided
        user.email = body.get("email", user.email)  # Default to current email if not provided

        # Update password only if provided
        if body.get("password"):
            user.set_password(body.get("password"))  # Correct way to set the password

        user.save()
        return JsonResponse({'success': True})

from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect

class UserLogoutView(LogoutView):
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Delete all cookies
        for cookie in request.COOKIES:
            print(cookie)
            response.delete_cookie(cookie)

        return response
def chat(request):
    return render(request,"accounts/whatsapp.html")

from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import  ChatOptionsToTenant as ChatOption
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# View for managing chat options
def manage_chat_options(request):
    chat_options = ChatOption.objects.all()
    users = User.objects.all()  # Assuming you have a User model or tenant model
    username=User.objects.filter(username=request.user.username,email=request.user.email).first()
    templates = TemplateModel.objects.filter(name=username)
    print(templates)
    return render(request, 'accounts/template.html', {
        'chat_options': chat_options,
        'users': users,
        'templates': templates,
    })

# View for creating a new chat option
@csrf_exempt
@require_POST
def create_chat_option(request):
    data = json.loads(request.body.decode('utf-8'))
    chat_option = data.get('key')
    name=User.objects.filter(username=request.user.username,email=request.user.email).first()
    tenant=TenantModel.objects.filter(name=name).first()
    print("data",data,name,tenant)
    try:
        option=ChatOptionsToTenant(user=name,options=chat_option)
        option.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# View for updating an existing chat option
@csrf_exempt
@require_POST
def update_chat_option(request):
    data = json.loads(request.body.decode('utf-8'))
    chat_option = data.get('options')
    prev=data.get('id')
    print(data,chat_option,prev)
    try:
        name=User.objects.filter(username=request.user.username,email=request.user.email).first()
        chat_option_ = ChatOption.objects.filter(user=name,options=prev).first()
        chat_option_.options = chat_option
        chat_option_.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# View for deleting a single chat option
@csrf_exempt
def delete_chat_option(request):
    data = json.loads(request.body.decode('utf-8'))
    chat_option = data.get('options')
    try:
        name=User.objects.filter(username=request.user.username,email=request.user.email).first()
        chat_option = ChatOption.objects.get(user=name,options=chat_option)
        chat_option.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# View for deleting selected chat options
@csrf_exempt
def delete_selected_chat_options(request):
    try:
        name=User.objects.filter(username=request.user.username,email=request.user.email).first()
        data = json.loads(request.body)
        ids = data.get('ids', [])
        ChatOption.objects.filter(user=name,options__in=ids).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def showTemplate(request):
    chat_options = ChatOption.objects.all()
      # Assuming you have a User model or tenant model
    username=User.objects.filter(username=request.user.username,email=request.user.email).first()
    tenant=TenantModel.objects.filter(name=username).first()
    users=UserModels.objects.filter(tenant_to=tenant)
    templates = TemplateModel.objects.filter(name=username)
    print(templates)
    return render(request, 'accounts/template.html', {
        'chat_options': chat_options,
        'users':users,
        'templates': templates
    })
from django.http import JsonResponse

def getContacts(request):
    login_user = User.objects.filter(username=request.user.username, email=request.user.email).first()
    tenant = TenantModel.objects.filter(name=login_user).first()

    # users = UserModels.objects.filter(tenant_to=tenant)
    # user_data = []
    # for user in users:
    #     # Count the number of unseen messages for each user
    #     unseen_count = ConversationModel.objects.filter(
    #         user=user, is_seen=False).count()

    #     # Get the latest message time for sorting (optional, based on latest activity)
    #     latest_message = ConversationModel.objects.filter(user=user).order_by('-date_queried').first()
    #     latest_message_time = latest_message.date_queried if latest_message else None

    #     user_data.append({
    #         'user': user.name,
    #         'phone': user.phone,
    #         'unseen_count': unseen_count,
    #         'latest_message_time': latest_message_time,
    #     })
    data = ConversationModel.objects.all()
    number_list = []

    for userData in data:
        # Check if the user is related to the tenant
        if userData.user.tenant_to.id == tenant.id:
            # Avoid duplicates by checking if the phone number is already in the list
            if not any(contact["phone"] == userData.user.phone for contact in number_list):
                number_list.append({"phone": userData.user.phone, "user": str(userData.user)})
    user_data=[]
    for contact in number_list:
        phone = contact["phone"]
        user = UserModels.objects.filter(phone=phone).first()

        if user:
            # Count the number of unseen messages for the user
            unseen_count = ConversationModel.objects.filter(
                user=user, is_seen=False).count()

            # Get the latest message time for the user
            latest_message = ConversationModel.objects.filter(user=user).order_by('-date_queried').first()
            latest_message_time = latest_message.date_queried if latest_message else None

            # Append the user details including unseen count and latest message time
            user_data.append({
                'user': user.name,
                'phone': user.phone,
                'unseen_count': unseen_count,
                'latest_message_time': latest_message_time,
            })

    # Sort user_data by unseen message count (descending) and latest message time
    user_data.sort(key=lambda x: (x['unseen_count'], x['latest_message_time']), reverse=True)

    return JsonResponse(user_data, safe=False)

from django.http import JsonResponse
from django.core.serializers import serialize
from django.utils.dateformat import DateFormat

def getChat(request, number):
    # Filter conversation data based on the provided phone number
    data = ConversationModel.objects.filter(user__phone=number).order_by('date_queried')
    chat_data = []

    # Format the chat data
    for userData in data:
        chat_data.append({
            "date_queried": DateFormat(userData.date_queried).format('Y-m-d H:i:s'),
            "ai_model_reply": userData.ai_model_reply,
            "user_query": userData.user_query
        })
    print((chat_data))
    return JsonResponse(chat_data, safe=False)

# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    print("received")
    async def connect(self):
        self.phone = self.scope['url_route']['kwargs']['phone']
        self.room_group_name = f'chat_{self.phone}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        print("kjoined")
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        phone = text_data_json['phone']

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'phone': phone,
                'message': message,
                'date_queried': text_data_json['date_queried'],
                'ai_model_reply': text_data_json['ai_model_reply'],
            }
        )

    # Receive message from room group
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))


def send_message_from_socket(request):
    if request.method == "POST":
        try:
            # Get the JSON data from the request body
            data = json.loads(request.body)
            print("data",data,request.body)
            phone_number = data.get('phone_number')
            message_content = data.get('message')
            userData=UserModels.objects.filter(phone=phone_number).first()
            data_ = get_text_message_input(phone_number,message_content)
            name=User.objects.filter(username=request.user.username,email=request.user.email).first()
            tenant=TenantModel.objects.filter(name=name).first()
            facebookData=FacebookCredentials.objects.filter(user=tenant).first()
            print("sending message from template")
            send_message_template_(data_,facebookData)
            s=ConversationModel(user=userData,ai_model_reply=message_content)
            s.save()
            # Respond back with a success message
            return JsonResponse({'status': 'success', 'message': message_content})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

from .models import ConversationModel

# Function to mark all conversations for a user as seen
def mark_messages_as_seen(request,phone):
    users = UserModels.objects.filter(phone=phone).first()

    if not users:
        # If no user is found with the provided phone number, return an error response
        return JsonResponse({'error': 'User not found'}, status=404)

    # Fetch conversations related to this user
    conversations = ConversationModel.objects.filter(user=users)

    if not conversations.exists():
        # If no conversations exist for the user, return a message
        return JsonResponse({'message': 'No conversations found for this user'}, status=200)

    # Mark all conversations as seen
    updated_count = 0
    for c in conversations:
        if not c.is_seen:  # Update only if the message is not already marked as seen
            c.is_seen = True
            c.save()
            updated_count += 1

    # Return a success response with the count of messages marked as seen
    return JsonResponse({'message': f'{updated_count} messages marked as seen'}, status=200)

# Function to mark a specific conversation as seen
def mark_single_message_as_seen(conversation_id):
    try:
        conversation = ConversationModel.objects.get(id=conversation_id)
        conversation.is_seen = True
        conversation.save()
        return True
    except ConversationModel.DoesNotExist:
        return False

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class VideoChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'video_chat_{self.room_name}'

        # Join the WebSocket group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the WebSocket group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Receive a message from the WebSocket
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Send the message to the WebSocket group (broadcasting)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'video_chat_message',
                'message': message
            }
        )

    async def video_chat_message(self, event):
        # Send the message to WebSocket
        message = event['message']
        await self.send(text_data=json.dumps({
            'message': message
        }))
import os
import requests
from django.conf import settings
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import mimetypes


def upload_media(request):
    """ Handle the media file upload, validate size, and send via WhatsApp. """

    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        number=request.POST.get('number')
        print("number",number)

        # Check file size (max 16MB for video/audio)
        max_size = 16 * 1024 * 1024  # 16MB
        if file.size > max_size:
            return JsonResponse({'status': 'error', 'message': 'File size exceeds the limit of 16MB.'}, status=400)

        # Get file type
        file_type, _ = mimetypes.guess_type(file.name)


        print(file_type)
        # Check if file is image, video, or audio
        if file_type :
            # Save the file to the media directory temporarily
            file_name = os.path.join('uploads', file.name)
            file_path = default_storage.save(file_name, ContentFile(file.read()))
            print("in loop",file_path)
            name=User.objects.filter(username=request.user.username,email=request.user.email).first()
            tenant=TenantModel.objects.filter(name=name).first()
            facebookData=FacebookCredentials.objects.filter(user=tenant).first()
            # Upload the media to WhatsApp
            media_id = upload_and_send_to_whatsapp(file_path, file_type,number,facebookData)

            if media_id:
                # Send media to a specified user via WhatsApp
                # phone_number = request.POST.get('phone_number')
                send_media_to_user(number, media_id,facebookData,file_type)

                return JsonResponse({'status': 'success', 'media_url': file_path, 'media_id': 'media_id'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Failed to upload media to WhatsApp.'}, status=500)
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid file type. Only images, videos, and audios are allowed.'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'No file uploaded.'}, status=400)

import requests

def upload_and_send_to_whatsapp(file_path, file_type, phone_number, facebookData):
    """ Upload file to WhatsApp and send it to a user """

    # Step 1: Upload Media to WhatsApp API
    upload_url = f"https://graph.facebook.com/v21.0/{facebookData.phoneNumberId}/media"

    headers = {
        "Authorization": f"Bearer {facebookData.accessToken}"
    }

    # Open the file and prepare it for uploading
    with open(file_path, 'rb') as file:
        files = {
            'file': (file_path, file, file_type)  # The file to upload
        }

        # Include the required messaging_product parameter
        data = {
            "messaging_product": "whatsapp",  # Specify the product (WhatsApp)
        }

        print(f"Uploading file {file_path} to WhatsApp...")

        try:
            # Send POST request to upload the media file
            response = requests.post(upload_url, headers=headers, files=files, data=data)
            response.raise_for_status()  # Raise an error for non-2xx status codes

            # Step 2: Extract Media ID from the response and send the media to the user
            media_id = response.json().get('id')
            if not media_id:
                print("Error: No media ID returned from upload.")
                return None

            print(f"Media uploaded successfully. Media ID: {media_id}")

            # Send media to the user
            # send_media_to_user(phone_number, media_id, facebookData, file_type)
            return media_id

        except requests.exceptions.RequestException as e:
            print(f"Error uploading media: {e}")
            print("Response:", response.text)
            return "Error uploading media."

def send_media_to_user(phone_number, media_id, facebookData, file_type):
    """ Send media to a specified user via WhatsApp """

    # Send Media API endpoint
    send_url = f"https://graph.facebook.com/v21.0/{facebookData.phoneNumberId}/messages"

    headers = {
        "Authorization": f"Bearer {facebookData.accessToken}"
    }

    # Construct the message data with the media ID
    message_data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
    }
    print("medis",media_id,file_type)
    # Determine the correct type based on the file_type
    if file_type.startswith('image'):
        message_data["type"] = "IMAGE"  # Set the correct type
        message_data["image"] = {
            "id": media_id,
            "caption": "Here is your requested media."  # Optional caption
        }
    elif file_type.startswith('text') or file_type == 'application/pdf' or file_type == 'text/plain':
            print("here in message")


            message_data["type"] = "DOCUMENT"
            message_data["document"] = {
                "id": media_id,
                "caption": "Here is your requested file."  # Optional caption
            }


    elif file_type.startswith('video'):
        message_data["type"] = "VIDEO"  # Set the correct type
        message_data["video"] = {
            "id": media_id,
            "caption": "Here is your requested media."
        }
    elif file_type.startswith('audio'):
        message_data["type"] = "AUDIO"  # Set the correct type
        message_data["audio"] = {
            "id": media_id
        }
    else:
        message_data["type"] = "FILE"
        message_data["file"] = {
                "id": media_id,
                "caption": "Here is your requested file."  # Optional caption
            }

        print("Error: Unsupported file type.")
        print("sendtyhg")
        return False

    print(f"Sending media to {phone_number}...")

    try:
        # Send the POST request to send the media
        response = requests.post(send_url, headers=headers, json=message_data)
        print("respone",response.json(),response,"respomse")
        # response.raise_for_status()  # Raise an error for non-2xx status codes

        if response.status_code == 200:
            print(f"Media sent successfully to {phone_number}")
            return True
        else:
            print(f"Error sending media: {response.status_code}")
            print("Response:", response.text)
            return False

    except requests.exceptions.RequestException as e:
        print(f"Error sending media: {e}")
        print("Response:", response.text)
        return False
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import AssigneModel, TenantModel
from .forms import AssigneForm

def assigne_list(request):
    assignes = AssigneModel.objects.all()
    tenants = TenantModel.objects.all()
    return render(request, 'accounts/assigne_list.html', {'assignes': assignes, 'tenants': tenants})

def create_assigne(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        client_id = request.POST.get('client_id')
        print(name)
        user=User.objects.filter(username=request.user.username,email=request.user.email).first()
        Tenant=TenantModel.objects.filter(name=user).first()
        client = TenantModel.objects.get(id=client_id)
        assigne = AssigneModel.objects.create(name=name, client=Tenant)
        # Assuming assigne.client is a User model or related to User
        return JsonResponse({
    'status': 'success'
})

from django.http import JsonResponse
from .models import AssigneModel, TenantModel, User  # Import models if not done already

def update_assigne(request):
    if request.method == 'POST':
        # Get the assignee by id passed in the request data
        user=User.objects.filter(username=request.user.username,email=request.user.email).first()
        tenant=TenantModel.objects.filter(name=user).first()
        assigne_id = request.POST.get('id')  # This should match the ID you send via AJAX
        assigne = AssigneModel.objects.filter(name=assigne_id,client=tenant).first()
        print("in call", assigne_id, request.POST.get('id'))  # Optional print to debug

        if assigne:
            assigne.name = request.POST.get('name')
            assigne.email = request.POST.get('email')
            user = User.objects.filter(username=request.user.username, email=request.user.email).first()
            tenant = TenantModel.objects.filter(name=user).first()
            assigne.client = tenant
            assigne.save()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Assignee not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid method'})


def delete_assigne(request, id):
    assigne = get_object_or_404(AssigneModel, id=id)
    assigne.delete()
    return JsonResponse({'status': 'success'})
from django.shortcuts import render
from django.http import JsonResponse
from .models import TicketsModel
# from rest_framework.response import Response
def filter_tickets(request):
    # Collect query parameters
    status = request.GET.get('status', '')
    ticket_number = request.GET.get('ticket_number', '')
    assignee = request.GET.get('assignee', '')
    issue = request.GET.get('issue', '')
    tenant = request.GET.get('tenant', '')
    print(status,ticket_number,assignee,issue,tenant)
    # Build the query based on provided filters
    tickets = TicketsStatusModel.objects.all()

    if status:
        tickets = tickets.filter(ticket_status__icontains=status)
    if ticket_number:
        tickets = tickets.filter(ticket_number__icontains=ticket_number)
    if assignee:
        tickets = tickets.filter(assigne__name__icontains=assignee)
    if issue:
        tickets = tickets.filter(issue__icontains=issue)
    if tenant:
        tickets = tickets.filter(tenant_to__icontains=tenant)

    tickets_data = []
    for ticket in tickets:
        tickets_data.append({

            'username': ticket.user.name,
            "user":ticket.user.id,
            "ticket_id":ticket.ticket_number.id,
            'ticket_number': ticket.ticket_number.ticket_number,
            'ticket_status': ticket.ticket_status,
            'assigne': ticket.assigne.name,
            'issue': ticket.issue,
            'comments': ticket.comments,
            'description': ticket.description,
            "history":ticket.commentHistory,
            "days": ticket.date_reported
            # Include any other relevant fields here
        })
    print(tickets_data)
    return JsonResponse({'tickets': tickets_data})



