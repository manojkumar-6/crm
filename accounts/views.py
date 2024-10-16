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
def send_onbarding_mail(username,email_,link):
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
    print(tenant)
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
    tenant__=User.objects.filter(username=request.user.username,email=request.user.email).first()
    templates = TemplateModel.objects.filter(name=tenant__)
    print(templates)
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
        for ticket in tickets:
            days_reported = (today - ticket.date_reported).days  # Calculate days reported
            ticket_list_.append({
                'ticket': ticket,
                'days_reported': days_reported,
            })
    else:
        ticket_list_=[]
    users=UserModels.objects.filter(tenant_to=tenant)
    context = {
        'tickets': tickets_,
        'ticket_list': ticket_list_,
        'today': today,
        "total_users":total_users,
        'total_users_interacted': i_count,
        'users':users,
        "i_count":m_count,
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
        'templates': templates,
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


from django.views.decorators.csrf import csrf_protect
@csrf_protect
@login_required
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
            # user_ids = json.loads(json_string.replace("'", '"'))
            for user in UserModels.objects.filter(tenant_to=tenant, id__in=data.get('userIds')):
                message = get_text_message_input(user.phone,message)
                conv=ConversationModel(user=user,ai_model_reply="welcome message",user_query=data)
                conv.save()
                print("sent",message)
                send_message(message,facebookData)

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
    currentCustomer=get_object_or_404(UserModels, id=customer_id)
    currentTickets=TicketsModel.objects.filter(user=currentCustomer)
    currentTicketStatus=TicketsStatusModel.objects.filter(user=currentCustomer)
    currentConverstaion=ConversationModel.objects.filter(user=currentCustomer)
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        customer.name = name
        customer.email = email
        customer.phone = phone
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
    smtp_server = "smtp.hostinger.com"
    smtp_port = 587  # Use 465 if you want SSL
    sender_email = "notifications@fixm8.com"  # Your email address
    receiver_email = email_  # Recipient's email
    password = "Vlookup@2024"  # Your email account password

    # Create the email message
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
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
base_support_keywords = [  "raise", "raise a support request", "support", "assist", "trouble", "can't", "error", "help please",
    "raise a request", "request support", "help me", "assist me"]
SUPPORT_REQUEST_KEYWORDS = get_support_keywords(base_support_keywords)
media_dict=dict()
# Updated function to check if user is requesting support
def check_support_needed(message):
    """
    Check if the user is explicitly asking for support using keywords.
    """
    message_lower = message.lower()
    print("message",message_lower,message)
    if "raise" in message:

        return "request"
    return any(keyword in message_lower for keyword in SUPPORT_REQUEST_KEYWORDS)

# Updated get_gemini_response function
def  get_gemini_response(input_message, recipient,caption, media=None):

    if is_acknowledgment(input_message):
        message_dict[recipient] = []
        return ACKNOWLEDGMENT_RESPONSE

    if(len(caption)):
        input_message=caption
    if recipient not in message_dict:
        message_dict[recipient] = []
        media_dict[recipient]='no path'
    # if (mes)
    print("input message",input_message)
    message_dict[recipient].append(input_message)

    # Check if the user is explicitly asking for support
    support_needed = check_support_needed(input_message)

    # Initialize support count if recipient is not already tracked
    if recipient not in support_count_dict:
        support_count_dict[recipient] = 0
    if "raise" in input_message:
        support_count_dict[recipient]+=3
    if support_needed:
        support_count_dict[recipient] += 1

    if support_count_dict[recipient] >= 3:  # Change the threshold to 1

        support_count_dict[recipient]=0
        full_input = " ".join(message_dict[recipient])
        print(full_input)
        message_dict[recipient] = []
        summary=model.generate_content('''proivde me a brief summary regarding the converstion what issue does the user is facing '''+full_input)

        thread = threading.Thread(target=create_ticket_from_summary(summary.text,recipient,media_dict[recipient]))
        thread.start()
        media_dict[recipient]='no path'
        return ("It looks like you need additional help. I've raised a support request, "
                "and our team will reach out to you soon.")

    full_input = " ".join(message_dict[recipient])

    if media:
        image = Image.open(media['file_path'])
        media_dict[recipient]=media['file_path']
        # media_response = process_media_with_model(media['file_path'])
        response = model.generate_content([full_input, image])

    else:
        response = model.generate_content(full_input)

    message_dict[recipient].append(response.text[:100])
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

    if(response.text =="I've raised a request, and our support team will reach out to you soon."):
        full_input = " ".join(message_dict[recipient])

        summary=model.generate_content('''proivde me a brief summary regarding the converstion what issue does the user is facing '''+full_input)
        message_dict[recipient]=[]

        thread = threading.Thread(target=create_ticket_from_summary(summary.text,recipient,media_dict[recipient]))
        thread.start()
        media_dict[recipient]='no path'
        print("triggered a email")
    user=UserModels.objects.filter(phone=recipient).first()
    con=ConversationModel(user=user,ai_model_reply=response.text,user_query=input_message)
    con.save()
    return response.text
# import phonenumbers
# from phonenumbers import geocoder, carrier, is_valid_number, parse

# def get_phone_number_info(phone_number):
#     try:
#         # Parse the phone number based on the region (e.g., 'US', 'IN', 'GB')
#         region = phonenumbers.region_code_for_number(phonenumbers.parse(phone_number))

#         parsed_number = phonenumbers.parse(phone_number,region)

#         # Get the country code
#         country_code = parsed_number.country_code
#         # Get the national number
#         national_number = parsed_number.national_number
#         # Get the country name
#         country_name = geocoder.country_name_for_number(parsed_number, 'en')
#         # Get the carrier informationTenantModel
#         carrier_name = carrier.name_for_number(parsed_number, 'en')

#         # Check if the number is valid
#         if is_valid_number(parsed_number):
#             return {
#                 "country_code": country_code,
#                 "national_number": national_number,
#                 "country_name": country_name,
#                 "carrier": carrier_name,
#                 "valid": True
#             }
#         else:
#             return {"valid": False, "message": "Invalid phone number"}

#     except phonenumbers.phonenumberutil.NumberParseException as e:
#         return {"valid": False, "message": str(e)}

def create_ticket_from_summary(summary,phonenumber,path):
    user=UserModels.objects.filter(phone=phonenumber).first()
    ticket_created=TicketsModel(user=user,ticket_number=timezone.now().timestamp(),Description=summary)
    ticket_created.save()
    ticket_status=TicketsStatusModel(user=user,tenant_to=user.tenant_to,ticket_number=ticket_created,comments="Ticket created need to be assigned",description=summary)
    ticket_status.save()
    mail_body={'ticket_number':ticket_created.ticket_number,'des':ticket_created.Description,
               'phone':user.phone,'status':ticket_status.ticket_status,'username':user.name}
    print("triggering a email to client and tenant")
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
    print('body',body)
    message_data = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_id = message_data.get("id")
    receipient_number=message_data.get("from")
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

# Function to send messages via WhatsApp
def send_message(data,facebookData):

    url = f"https://graph.facebook.com/{facebookData.version}/{facebookData.phoneNumberId}/messages"
    headers = {
        "Authorization": "Bearer " + facebookData.accessToken,
        "Content-Type": "application/json",
    }

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
        print("received response")
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
        user.save()
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
@login_required
def ticket_status_list(request):
    user=User.objects.filter(username=request.user.username,email=request.user.email)
    tenants = TenantModel.objects.filter(name=user.first())
    tickets = TicketsStatusModel.objects.filter(tenant_to=tenants.first())
    users = UserModels.objects.filter(tenant_to=tenants.first())
    ticket_numbers = TicketsModel.objects.filter(user__tenant_to=tenants.first())
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

@login_required
@csrf_exempt
def update_ticket_status(request):
    print("int his ",request.method)
    if request.method == 'POST':
        print("in post")
        ticket_id = request.POST.get('id')
        print(ticket_id)
        ticket = get_object_or_404(TicketsStatusModel, id=ticket_id)
        form = TicketsStatusForm(request.POST, instance=ticket)
        print("form",form)
        if form.is_valid():
            form.save()
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
    return render(request, 'accounts/u.html', {'users': users})

# Create a user
@csrf_exempt
def create_user_(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        is_superuser = request.POST.get('is_superuser') == 'true'
        password=request.POST.get('password')

        user = User.objects.create(username=username, email=email, is_superuser=is_superuser)
        user.set_password(password)
        user.save()
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
        tenant_update=TenantModel.objects.filter(name=user).first()

        user.username = username
        user.email = email
        user.is_superuser = is_superuser
        user.save()
        tenant_update.name=user
        tenant_update.email=email
        tenant_update.save()


        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

# Delete user
@csrf_exempt
def delete_user_(request):
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
    tenant =User.objects.filter(username=request.user.username,email=request.user.email).first()  # Get the tenant object
    tenant_=TenantModel.objects.filter(name=tenant).first()
    users = UserModels.objects.filter(tenant_to=tenant_)
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
from django.views.decorators.http import require_POST
@csrf_exempt
def delete_user_tenant(request, user_id):
    if request.method == 'DELETE':
        user = UserModels.objects.get(id=user_id)
        user.delete()
        return JsonResponse({'success': True})
@login_required
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
                currentTenantData=TenantModel.objects.filter(name=currentUser).first()
                currentUsersDataToTenant=UserModels.objects.filter(tenant_to=currentTenantData)
                currentTicketsStatusData=TicketsStatusModel.objects.filter(tenant_to=currentTenantData)
                currentFacebookData=FacebookCredentials.objects.filter(user=currentTenantData)
                updatedTenantData=TenantModel.objects.filter(name=currentUser).first()
                updatedTenantData.name=updatedUser
                updatedTenantData.save()
                for userData in currentUsersDataToTenant:
                    userData.tenant_to=updatedTenantData
                    userData.save()
                for ticket in currentTicketsStatusData:
                    ticket.tenant_to=updatedTenantData
                    ticket.save()
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
