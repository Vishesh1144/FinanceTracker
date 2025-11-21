# finance/views.py
import json
import os
import re
import tempfile
import requests
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
import pytesseract

from .models import Expense, LendBorrow

# === GEMINI API (CHANGE THIS) ===
API_KEY = "AIzaSyBnXa2u-UWC2_DfKAt8jAjAxX5JvA-B2-U"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# LANDING PAGE
def landing_page(request):
    return render(request, 'lending_page\landing.html')

# AUTH
def register_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        confirm = request.POST["confirm"]
        if password != confirm:
            messages.error(request, "Passwords do not match!")
            return redirect('register')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken!")
            return redirect('register')
        User.objects.create_user(username=username, password=password)
        messages.success(request, "Account created! Please log in.")
        return redirect('login')
    return render(request, "auth/register.html")

def login_view(request):
    if request.method == "POST":
        user = authenticate(request, username=request.POST["username"], password=request.POST["password"])
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, "Invalid credentials")
    return render(request, "auth/login.html")

def logout_view(request):
    logout(request)
    return redirect('login')

# DASHBOARD
@login_required
def dashboard(request):
    expenses = Expense.objects.filter(user=request.user).order_by("-date")
    return render(request, "finance/dashboard.html", {"expenses": expenses})

# EXPENSE CRUD
@csrf_exempt
@login_required
def add_expense(request):
    if request.method != "POST": return JsonResponse({"status": "error"})
    data = json.loads(request.body)
    date_obj = datetime.today().date()
    raw = data.get("date")
    if raw:
        try: date_obj = datetime.strptime(raw, "%Y-%m-%d").date()
        except: pass

    Expense.objects.create(
        user=request.user,
        item_name=data["item_name"],
        amount=data["amount"],
        type=data["type"],
        category=data["category"],
        date=date_obj
    )
    return JsonResponse({"status": "success"})

@csrf_exempt
@login_required
def edit_expense(request, expense_id):
    exp = get_object_or_404(Expense, id=expense_id, user=request.user)
    if request.method == "POST":
        data = json.loads(request.body)
        exp.item_name = data.get("item_name", exp.item_name)
        exp.amount = data.get("amount", exp.amount)
        exp.type = data.get("type", exp.type)
        exp.category = data.get("category", exp.category)
        raw = data.get("date")
        if raw:
            try: exp.date = datetime.strptime(raw, "%Y-%m-%d").date()
            except: pass
        exp.save()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"})

@require_http_methods(["DELETE"])
@login_required
def delete_expense(request, id):
    get_object_or_404(Expense, id=id, user=request.user).delete()
    return JsonResponse({"status": "success"})

# CHARTS & TOTALS
@login_required
def get_totals(request):
    inc = Expense.objects.filter(user=request.user, type="Income").aggregate(Sum("amount"))["amount__sum"] or 0
    exp = Expense.objects.filter(user=request.user, type="Expense").aggregate(Sum("amount"))["amount__sum"] or 0
    return JsonResponse({
        "total_income": float(inc),
        "total_expense": float(exp),
        "total_savings": float(inc - exp),
    })

@login_required
def get_chart_data(request):
    cats = Expense.objects.filter(user=request.user, type="Expense").values("category").annotate(total=Sum("amount"))
    cat_data = {c["category"]: float(c["total"]) for c in cats}

    months = {}
    for e in Expense.objects.filter(user=request.user):
        m = e.date.strftime("%b")
        months.setdefault(m, {"Income": 0, "Expense": 0})
        months[m][e.type] += float(e.amount)

    ordered = sorted(months.items(), key=lambda x: datetime.strptime(x[0], "%b").month)
    labels = [m[0] for m in ordered]
    income = [m[1]["Income"] for m in ordered]
    expense = [m[1]["Expense"] for m in ordered]

    return JsonResponse({
        "categories": cat_data,
        "months": labels,
        "income": income,
        "expense": expense,
    })

# OCR UPLOAD WITH GEMINI
@csrf_exempt
@login_required
# ==================== UPLOAD BILL + OCR + GEMINI SMART CATEGORIZATION ====================
def upload_image(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    image_file = request.FILES.get("image")
    rectangles_json = request.POST.get("rectangles")
    if not image_file or not rectangles_json:
        return JsonResponse({"error": "Missing image or rectangles"}, status=400)

    try:
        rectangles = json.loads(rectangles_json)
    except:
        return JsonResponse({"error": "Invalid rectangles JSON"}, status=400)

    if len(rectangles) < 2:
        return JsonResponse({"error": "Please draw 2 rectangles (items + amounts)"}, status=400)

    # Save image temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
        for chunk in image_file.chunks():
            f.write(chunk)
        temp_path = f.name

    img = Image.open(temp_path)
    ocr_texts = []
    for rect in rectangles:
        x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
        cropped = img.crop((x, y, x + w, y + h))
        text = pytesseract.image_to_string(cropped, config="--psm 6").strip()
        ocr_texts.append(text)

    os.unlink(temp_path)

    # Extract items and amounts
    items_raw = ocr_texts[0].splitlines()
    amounts_raw = ocr_texts[1].splitlines() if len(ocr_texts) > 1 else []

    items = [line.strip() for line in items_raw if line.strip()]
    amounts = []
    for line in amounts_raw:
        match = re.search(r'[₹\$]?[\d,]+\.?\d*', line.replace('₹', '').replace('$', ''))
        if match:
            amounts.append(float(match.group(0).replace(',', '')))
        else:
            amounts.append(0.0)

    results = []

    # NEW OPEN-ENDED SMART PROMPT
    for item_text, amount in zip(items, amounts):
        if amount <= 0:
            continue

        prompt = f'''
You are an expert Indian personal finance assistant.
Item from a bill/receipt: "{item_text.strip()}"
Amount: ₹{amount}

Suggest the SINGLE best category name for this expense.
Rules:
- Use common, natural, short category names (e.g. "Groceries", "Fuel", "Medicines", "Dining Out", "Electricity", "Movie Ticket", "Uber", "Shopping", "Mobile Recharge")
- Prefer specific over generic when clear (e.g. "Petrol" instead of "Travel", "Medicines" instead of "Health")
- Keep category name 1–3 words max
- Capitalize Each Word (Title Case)
- Never make up items — base only on the given text
- If totally unclear → use "Miscellaneous"

Examples:
Item: "PARACETAMOL 650MG TAB" → Medicines
Item: "UBER AUTO RIDE" → Cab Ride
Item: "BESCOM ELECTRICITY" → Electricity Bill
Item: "AMUL BUTTER 500G" → Groceries
Item: "PVR CINEMAS" → Movie

Respond with ONLY the category name. No explanation.
'''

        category = "Miscellaneous"  # fallback
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 50
                }
            }
            response = requests.post(API_URL, json=payload, timeout=20)
            if response.status_code == 200:
                raw = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Clean up response
                clean_category = re.sub(r'^[\W_]+|[\W_]+$','', raw.split('\n')[0]).strip()
                if clean_category and len(clean_category) < 40:
                    category = clean_category
                else:
                    category = "Miscellaneous"
        except Exception as e:
            print("Gemini failed:", e)
            category = "Miscellaneous"

        # Save to DB
        expense = Expense.objects.create(
            user=request.user,
            item_name=item_text[:100],
            type="Expense",
            amount=amount,
            category=category,               # Now dynamic!
            date=datetime.today().date()
        )
        results.append({
            "id": expense.id,
            "Item": item_text,
            "Amount": amount,
            "Category": category
        })

    return JsonResponse(results, safe=False)

# LEND & BORROW
@login_required
def get_lend_borrow(request):
    records = LendBorrow.objects.filter(user=request.user).order_by('-date')
    data = [{
        "id": r.id,
        "person": r.person,
        "amount": float(r.amount),
        "type": r.type,
        "date": str(r.date),
        "dueDate": str(r.due_date) if r.due_date else "",
        "reason": r.reason,
        "status": r.status,
    } for r in records]
    return JsonResponse({"records": data})

@csrf_exempt
@login_required
def add_lend_borrow(request):
    if request.method != "POST": return JsonResponse({"status": "error"})
    data = json.loads(request.body)
    LendBorrow.objects.create(
        user=request.user,
        person=data["person"],
        amount=data["amount"],
        type=data["type"],
        date=data.get("date") or datetime.today().date(),
        due_date=data.get("dueDate") or None,
        reason=data.get("reason", ""),
        status="pending"
    )
    return JsonResponse({"status": "success"})

@csrf_exempt
@login_required
def update_lend_borrow(request, id):
    record = get_object_or_404(LendBorrow, id=id, user=request.user)
    if request.method == "PATCH":
        data = json.loads(request.body)
        record.status = data.get("status", record.status)
        record.save()
        return JsonResponse({"status": "success"})
    elif request.method == "DELETE":
        record.delete()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"})