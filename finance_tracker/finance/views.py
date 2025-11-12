# views.py
from datetime import datetime
import json
from django.http import JsonResponse
import requests
from .models import Expense
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models.functions import TruncMonth
from PIL import Image
import tempfile, os
import pytesseract

from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required



@login_required(login_url='login')
def dashboard(request):
    expenses = Expense.objects.filter(user=request.user).order_by("-date")  # latest first
    return render(request, "finance/dashboard.html", {"expenses": expenses})   # 👈 make sure this file is in templates/

def add_expense(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            raw_date = data.get("date")
            formatted_date = None

            if raw_date:
                try:
                    # Case: "Aug. 31, 2025"
                    formatted_date = datetime.strptime(raw_date, "%b. %d, %Y").date()
                except ValueError:
                    try:
                        # Case: already "2025-08-31"
                        formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    except:
                        # Fallback: today
                        formatted_date = datetime.today().date()
            else:
                formatted_date = datetime.today().date()

            expense = Expense.objects.create(
                user=request.user,
                item_name=data.get("item_name"),
                amount=data.get("amount"),
                type=data.get("type"),
                category=data.get("category"),
                date=formatted_date,
            )

            return JsonResponse({
                "status": "success",
                "id": expense.id,
                "item_name": expense.item_name,
                "amount": str(expense.amount),
                "type": expense.type,
                "category": expense.category,
                # Always send YYYY-MM-DD
                "date": expense.date.strftime("%Y-%m-%d"),
            })

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})


#Edit at the Transaction Table
@login_required
# @csrf_exempt
def edit_expense(request, expense_id):
    if request.method == "POST":
        expense = get_object_or_404(Expense, id=expense_id, user=request.user)
        data = json.loads(request.body)

        expense.item_name = data.get("item_name", expense.item_name)
        expense.amount = data.get("amount", expense.amount)
        expense.type = data.get("type", expense.type)   # 👈 this line is important
        expense.category = data.get("category", expense.category)
        expense.date = data.get("date", expense.date)
        expense.save()

        return JsonResponse({
            "status": "success",
            "item_name": expense.item_name,
            "amount": str(expense.amount),
            "type": expense.type,
            "category": expense.category,
            "date": str(expense.date),
        })
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)
# Get total income, expense, savings
def get_totals(request):
    total_income = Expense.objects.filter(user=request.user, type="Income").aggregate(total=Sum("amount"))["total"] or 0
    total_expense = Expense.objects.filter(user=request.user, type="Expense").aggregate(total=Sum("amount"))["total"] or 0
    total_savings = total_income - total_expense

    return JsonResponse({
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "total_savings": float(total_savings),
    })




@require_http_methods(["DELETE"])
def delete_expense(request, id):
    try:
        expense = Expense.objects.get(id=id, user=request.user)
        expense.delete()
        return JsonResponse({"status": "success"})
    except Expense.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Expense not found"})

#ChartFunctions
def get_chart_data(request):
    user = request.user  # show only current user’s data

    # 📊 Expense categories breakdown
    categories = (
        Expense.objects.filter(user=user, type="Expense")
        .values("category")
        .annotate(total=Sum("amount"))
    )
    category_data = {c["category"]: float(c["total"]) for c in categories}

    # 📈 Monthly trend (income vs expense)
    expenses = Expense.objects.filter(user=user)
    monthly_data = {}

    for e in expenses:
        month = e.date.strftime("%b")  # Jan, Feb, Mar...
        if month not in monthly_data:
            monthly_data[month] = {"Income": 0, "Expense": 0}
        monthly_data[month][e.type] += float(e.amount)

    response = {
        "categories": category_data,
        "months": list(monthly_data.keys()),
        "income": [monthly_data[m]["Income"] for m in monthly_data],
        "expense": [monthly_data[m]["Expense"] for m in monthly_data],
    }

    return JsonResponse(response)

# Image OCR and Categorization (Optional)
API_KEY = "AIzaSyBnXa2u-UWC2_DfKAt8jAjAxX5JvA-B2-U"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

def upload_image(request):
    if request.method == "POST":
        image_file = request.FILES.get("image")
        rectangles_json = request.POST.get("rectangles")
        if not image_file or not rectangles_json:
            return JsonResponse({"error": "Missing image or rectangles"})

        rectangles = json.loads(rectangles_json)

        # Save image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            for chunk in image_file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        img = Image.open(temp_path)

        # OCR outputs (expecting: [items_rect, amounts_rect])
        ocr_texts = []
        for rect in rectangles:
            x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
            roi = img.crop((x, y, x + w, y + h))
            text = pytesseract.image_to_string(roi, config="--psm 6").strip()
            ocr_texts.append(text)

        os.remove(temp_path)

        # Split into lines
        items_list = ocr_texts[0].splitlines() if len(ocr_texts) > 0 else []
        amounts_list = ocr_texts[1].splitlines() if len(ocr_texts) > 1 else []

        # Clean empty lines
        items_list = [i.strip() for i in items_list if i.strip()]
        amounts_list = [a.strip() for a in amounts_list if a.strip()]

        # Convert amounts to float if possible
        clean_amounts = []
        for amt in amounts_list:
            try:
                clean_amounts.append(float(amt.replace(",", "")))
            except:
                clean_amounts.append(0.0)

        # Match items with amounts (zip ensures pairing)
        results = []
        for idx, (item_text, amount) in enumerate(zip(items_list, clean_amounts), start=1):
            # Categorize via Gemini
            prompt = f"Categorize the item: {item_text}. Only output one category (Groceries, Snacks, Household, Entertainment, Other)."
            payload = {"contents":[{"parts":[{"text":prompt}]}]}
            response = requests.post(API_URL, headers={"Content-Type": "application/json"}, json=payload)
            if response.status_code == 200:
                try:
                    category = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                except:
                    category = "Other"
            else:
                category = "Other"

            # Save to DB
            expense = Expense.objects.create(
                user=request.user,
                item_name=item_text,
                type="Expense",
                amount=amount,
                category=category
            )

            results.append({
                "id": expense.id,
                "Item": item_text,
                "Amount": amount,
                "Category": category
            })

        return JsonResponse(results, safe=False)

    return render(request, "finance/upload.html")



def register_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        confirm = request.POST["confirm"]
        
        if password != confirm:
            messages.error(request, "Passwords do not match!")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists!")
            return redirect('register')

        user = User.objects.create_user(username=username, password=password)
        user.save()
        messages.success(request, "Account created successfully! Please log in.")
        return redirect('login')
    
    return render(request, "auth/register.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')  # redirect to main page
        else:
            messages.error(request, "Invalid username or password!")
    
    return render(request, "auth/login.html")


def logout_view(request):
    logout(request)
    return redirect('login')