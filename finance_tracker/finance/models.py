# finance/models.py
from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=100, default="Unknown Item")
    type = models.CharField(
        max_length=20,
        choices=[("Expense", "Expense"), ("Income", "Income")],
        default="Expense"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    category = models.CharField(max_length=50, default="General")
    date = models.DateField(default=date.today)

    def __str__(self):
        return f"{self.item_name} - {self.type} - {self.amount}"

class LendBorrow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    person = models.CharField(max_length=100)
    type = models.CharField(
        max_length=10,
        choices=[("lent", "Lent"), ("borrowed", "Borrowed")],
        default="borrowed"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=date.today)
    due_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("settled", "Settled")],
        default="pending"
    )

    def __str__(self):
        return f"{self.person} - {self.type} - {self.amount}"